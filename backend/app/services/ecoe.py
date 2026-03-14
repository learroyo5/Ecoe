from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    AssessmentTool,
    ContingencyExport,
    ECOEEvent,
    ECOEResult,
    EvaluatorRecord,
    Incident,
    LiveSession,
    PilotRun,
    StaffAssignment,
    Station,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, SessionMode, StationStatus


def compute_ecoe_validation(db: Session, ecoe_event: ECOEEvent) -> dict:
    students_count = db.scalar(
        select(func.count(Student.id)).where(Student.ecoe_event_id == ecoe_event.id)
    )
    station_count = db.scalar(
        select(func.count(Station.id)).where(Station.ecoe_event_id == ecoe_event.id)
    )
    pilot_count = db.scalar(
        select(func.count(PilotRun.id)).where(PilotRun.ecoe_event_id == ecoe_event.id)
    )
    complete_stations = db.scalar(
        select(func.count(Station.id)).where(
            Station.ecoe_event_id == ecoe_event.id,
            Station.status.in_(
                [
                    StationStatus.lista_para_pilotaje.value,
                    StationStatus.en_pilotaje.value,
                    StationStatus.validada.value,
                    StationStatus.publicada.value,
                    StationStatus.activa.value,
                    StationStatus.finalizada.value,
                    StationStatus.cerrada.value,
                ]
            ),
        )
    )
    stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event.id)).all()
    forms_ready = all(
        (not station.requires_student_form) or bool(station.student_form_definition.get("questions"))
        for station in stations
    )
    tools_ready = all(
        (station.assessment_tool_id is not None) or (not station.requires_evaluator)
        for station in stations
    )
    multimedia_ready = all(
        (not station.uses_multimedia) or bool(station.multimedia_notes)
        for station in stations
    )
    timer_ready = ecoe_event.station_time_minutes > 0 and ecoe_event.transition_time_minutes >= 0

    can_pilot = (
        ecoe_event.name
        and ecoe_event.course_name
        and ecoe_event.school_name
        and students_count > 0
        and station_count > 0
        and timer_ready
    )
    can_publish = (
        complete_stations == station_count
        and tools_ready
        and forms_ready
        and multimedia_ready
        and timer_ready
        and pilot_count > 0
    )
    has_live_session = db.scalar(
        select(func.count(LiveSession.id)).where(LiveSession.ecoe_event_id == ecoe_event.id)
    )
    can_start_live = (
        ecoe_event.status == ECOEStatus.publicado.value
        and has_live_session > 0
        and station_count > 0
        and ecoe_event.total_groups > 0
    )
    return {
        "students_count": students_count,
        "station_count": station_count,
        "pilot_count": pilot_count,
        "complete_stations": complete_stations,
        "can_pilot": can_pilot,
        "can_publish": can_publish,
        "can_start_live": can_start_live,
        "warnings": [
            item
            for item in [
                None if tools_ready else "Hay estaciones con evaluacion sin instrumento.",
                None if forms_ready else "Hay estaciones cognitivas sin formulario cargado.",
                None if multimedia_ready else "Hay estaciones multimedia sin recurso validado.",
            ]
            if item
        ],
    }


def update_ecoe_status(db: Session, ecoe_event: ECOEEvent, target_status: str) -> ECOEEvent:
    validation = compute_ecoe_validation(db, ecoe_event)
    allowed = {
        ECOEStatus.borrador.value,
        ECOEStatus.en_configuracion.value,
        ECOEStatus.listo_para_pilotaje.value,
        ECOEStatus.en_pilotaje.value,
        ECOEStatus.pilotaje_validado.value,
        ECOEStatus.publicado.value,
        ECOEStatus.en_ejecucion.value,
        ECOEStatus.cerrado.value,
        ECOEStatus.archivado.value,
    }
    if target_status not in allowed:
        raise ValueError("Estado no permitido")
    if target_status == ECOEStatus.listo_para_pilotaje.value and not validation["can_pilot"]:
        raise ValueError("El ECOE aun no cumple condiciones para pilotaje")
    if target_status == ECOEStatus.publicado.value and not validation["can_publish"]:
        raise ValueError("El ECOE aun no cumple condiciones para publicacion")
    if target_status == ECOEStatus.en_ejecucion.value and not validation["can_start_live"]:
        raise ValueError("El ECOE aun no esta listo para ejecucion real")
    ecoe_event.status = target_status
    db.add(ecoe_event)
    db.commit()
    db.refresh(ecoe_event)
    return ecoe_event


def compute_results(db: Session, ecoe_event_id: int) -> list[dict]:
    students = db.scalars(select(Student).where(Student.ecoe_event_id == ecoe_event_id)).all()
    results = []
    for student in students:
        records = db.scalars(
            select(EvaluatorRecord).where(
                EvaluatorRecord.ecoe_event_id == ecoe_event_id,
                EvaluatorRecord.student_id == student.id,
                EvaluatorRecord.mode == SessionMode.ejecucion.value,
            )
        ).all()
        total_score = sum(record.score_obtained for record in records)
        max_score = sum(record.max_score for record in records)
        percentage = (total_score / max_score * 100) if max_score else 0
        grade = 1.0 + (percentage / 100) * 6.0
        results.append(
            {
                "student_id": student.id,
                "student_name": f"{student.name} {student.last_name}",
                "ecoe_number": student.ecoe_number,
                "total_score": round(total_score, 2),
                "max_score": round(max_score, 2),
                "percentage": round(percentage, 2),
                "equivalent_grade": round(grade, 2),
            }
        )
    return results


def persist_results(db: Session, ecoe_event_id: int) -> list[dict]:
    results = compute_results(db, ecoe_event_id)
    db.query(ECOEResult).filter(ECOEResult.ecoe_event_id == ecoe_event_id).delete()
    for item in results:
        db.add(
            ECOEResult(
                ecoe_event_id=ecoe_event_id,
                student_id=item["student_id"],
                total_score=item["total_score"],
                max_score=item["max_score"],
                percentage=item["percentage"],
                equivalent_grade=item["equivalent_grade"],
            )
        )
    db.commit()
    return results


def build_dashboard(db: Session, ecoe_event: ECOEEvent) -> dict:
    validation = compute_ecoe_validation(db, ecoe_event)
    stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event.id)).all()
    live_session = db.scalar(
        select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event.id).limit(1)
    )
    evaluator_records = db.scalar(
        select(func.count(EvaluatorRecord.id)).where(EvaluatorRecord.ecoe_event_id == ecoe_event.id)
    )
    student_responses = db.scalar(
        select(func.count(StudentResponse.id)).where(StudentResponse.ecoe_event_id == ecoe_event.id)
    )
    incidents = db.scalar(
        select(func.count(Incident.id)).where(Incident.ecoe_event_id == ecoe_event.id)
    )
    return {
        "active_ecoe": {
            "id": ecoe_event.id,
            "name": ecoe_event.name,
            "status": ecoe_event.status,
            "date": ecoe_event.date.isoformat(),
            "course_name": ecoe_event.course_name,
        },
        "totals": {
            "students": validation["students_count"],
            "stations": validation["station_count"],
            "pilot_runs": validation["pilot_count"],
            "evaluations": evaluator_records,
            "student_submissions": student_responses,
            "incidents": incidents,
        },
        "validation": validation,
        "timeline": [
            {"label": station.name, "status": station.status, "circuit": station.circuit_name}
            for station in stations
        ],
        "live_panel": {
            "status": live_session.status if live_session else "sin_sesion",
            "current_station_index": live_session.current_station_index if live_session else 0,
            "remaining_seconds": live_session.remaining_seconds if live_session else 0,
        },
    }


def export_results_excel(db: Session, ecoe_event_id: int) -> bytes:
    data = persist_results(db, ecoe_event_id)
    df = pd.DataFrame(data)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="consolidado")
    return buffer.getvalue()


def export_contingency_pdf(db: Session, ecoe_event_id: int, station_id: int | None = None) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle("Contingencia ECOE")
    text = pdf.beginText(40, 800)
    text.setFont("Helvetica-Bold", 14)
    text.textLine("Proyecto Tecnologico ECOE - Respaldo imprimible")
    text.setFont("Helvetica", 11)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    text.textLine(f"ECOE: {ecoe_event.name}")
    if station_id:
        station = db.get(Station, station_id)
        text.textLine(f"Estacion: {station.station_number} - {station.name}")
        text.textLine(f"Instruccion estudiante: {station.pre_entry_instruction}")
        text.textLine(f"Instruccion evaluador: {station.evaluator_instruction}")
        text.textLine(f"Materiales: {station.materials}")
    else:
        stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()
        text.textLine("Resumen general de estaciones")
        for station in stations:
            text.textLine(
                f"{station.station_number}. {station.name} [{station.status}] {station.circuit_name}"
            )
    pdf.drawText(text)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def store_contingency_export(db: Session, ecoe_event_id: int, export_type: str, content: bytes) -> str:
    settings = get_settings()
    output_dir = Path(settings.storage_path) / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{export_type}-{ecoe_event_id}.bin"
    path.write_bytes(content)
    db.add(
        ContingencyExport(
            ecoe_event_id=ecoe_event_id,
            export_type=export_type,
            file_path=str(path),
        )
    )
    db.commit()
    return str(path)
