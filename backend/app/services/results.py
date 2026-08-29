"""Results computation, persistence, traceability, and export services."""

from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datetime import datetime

from app.core.config import get_settings
from app.models.entities import (
    AuditLog,
    ContingencyExport,
    ECOEEvent,
    ECOEResult,
    EvaluatorRecord,
    PilotRun,
    StaffAssignment,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, RoleCode, SessionMode

# Una vez cerrado/archivado el evento, los resultados oficiales son el snapshot
# `ECOEResult` escrito al cierre: ninguna edición posterior de respuestas o
# registros debe mover el número que sirve `/results` o el export.
FROZEN_RESULT_STATUSES = {ECOEStatus.cerrado.value, ECOEStatus.archivado.value}


def compute_equivalent_grade(percentage: float, passing_reference_percent: float) -> float:
    """Chilean 1.0-7.0 grading scale ("escala de exigencia").

    `passing_reference_percent` maps to exactly 4.0 (the minimum passing
    grade); the scale is piecewise-linear below and above that point, so a
    stricter or looser passing threshold per ECOE actually changes grades
    instead of being decorative.
    """
    passing = min(max(passing_reference_percent, 0.01), 99.99)
    if percentage >= passing:
        return 4.0 + (percentage - passing) / (100 - passing) * 3.0
    return 1.0 + (percentage / passing) * 3.0


def compute_results(db: Session, ecoe_event_id: int) -> list[dict]:
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    passing_reference_percent = ecoe_event.passing_reference_percent if ecoe_event else 60.0
    students = db.scalars(
        select(Student).where(Student.ecoe_event_id == ecoe_event_id, Student.is_active.is_(True))
    ).all()
    # Single aggregated query instead of one query per student.
    totals_by_student: dict[int, tuple[float, float]] = {
        row[0]: (row[1] or 0, row[2] or 0)
        for row in db.execute(
            select(
                EvaluatorRecord.student_id,
                func.sum(EvaluatorRecord.score_obtained),
                func.sum(EvaluatorRecord.max_score),
            )
            .where(
                EvaluatorRecord.ecoe_event_id == ecoe_event_id,
                EvaluatorRecord.mode == SessionMode.ejecucion.value,
            )
            .group_by(EvaluatorRecord.student_id)
        ).all()
    }
    # Formularios de estudiante con puntaje definitivo (autocorregidos o ya
    # corregidos manualmente); los pendientes de correccion no entran aun.
    form_totals_by_student: dict[int, tuple[float, float]] = {
        row[0]: (row[1] or 0, row[2] or 0)
        for row in db.execute(
            select(
                StudentResponse.student_id,
                func.sum(StudentResponse.score_obtained),
                func.sum(StudentResponse.max_score),
            )
            .where(
                StudentResponse.ecoe_event_id == ecoe_event_id,
                StudentResponse.mode == SessionMode.ejecucion.value,
                StudentResponse.score_obtained.is_not(None),
            )
            .group_by(StudentResponse.student_id)
        ).all()
    }
    results = []
    for student in students:
        eval_score, eval_max = totals_by_student.get(student.id, (0, 0))
        form_score, form_max = form_totals_by_student.get(student.id, (0, 0))
        total_score = eval_score + form_score
        max_score = eval_max + form_max
        percentage = (total_score / max_score * 100) if max_score else 0
        grade = compute_equivalent_grade(percentage, passing_reference_percent)
        results.append({
            "student_id": student.id,
            "student_name": f"{student.name} {student.last_name}",
            "ecoe_number": student.ecoe_number,
            "total_score": round(total_score, 2),
            "max_score": round(max_score, 2),
            "percentage": round(percentage, 2),
            "equivalent_grade": round(grade, 2),
        })
    return results


def read_results(
    db: Session, ecoe_event_id: int
) -> tuple[list[dict], bool, datetime | None]:
    """Vista de resultados para lectura (`/results`, export).

    Si el evento está `cerrado`/`archivado` **y** existe snapshot `ECOEResult`,
    devuelve el snapshot congelado (misma forma que `compute_results`) junto con
    `frozen=True` y la fecha de consolidación (`ECOEResult.updated_at`). En
    cualquier otro estado —o si el cierre no dejó snapshot— recalcula en vivo con
    `compute_results` y `frozen=False`.
    """
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if ecoe_event is not None and str(ecoe_event.status) in FROZEN_RESULT_STATUSES:
        snapshots = db.scalars(
            select(ECOEResult)
            .where(ECOEResult.ecoe_event_id == ecoe_event_id)
            .order_by(ECOEResult.student_id.asc())
        ).all()
        if snapshots:
            students = {
                student.id: student
                for student in db.scalars(
                    select(Student).where(Student.ecoe_event_id == ecoe_event_id)
                ).all()
            }
            consolidated_at = max(
                (snap.updated_at for snap in snapshots if snap.updated_at is not None),
                default=None,
            )
            results = []
            for snap in snapshots:
                student = students.get(snap.student_id)
                results.append({
                    "student_id": snap.student_id,
                    "student_name": (
                        f"{student.name} {student.last_name}" if student else ""
                    ),
                    "ecoe_number": student.ecoe_number if student else None,
                    "total_score": round(snap.total_score, 2),
                    "max_score": round(snap.max_score, 2),
                    "percentage": round(snap.percentage, 2),
                    "equivalent_grade": round(snap.equivalent_grade, 2),
                })
            return results, True, consolidated_at
    return compute_results(db, ecoe_event_id), False, None


def persist_results(
    db: Session,
    ecoe_event_id: int,
    *,
    commit: bool = True,
    actor_email: str | None = None,
) -> list[dict]:
    results = compute_results(db, ecoe_event_id)
    db.query(ECOEResult).filter(ECOEResult.ecoe_event_id == ecoe_event_id).delete()
    for item in results:
        db.add(ECOEResult(
            ecoe_event_id=ecoe_event_id,
            student_id=item["student_id"],
            total_score=item["total_score"],
            max_score=item["max_score"],
            percentage=item["percentage"],
            equivalent_grade=item["equivalent_grade"],
        ))
    if actor_email:
        db.add(AuditLog(
            user_email=actor_email,
            action="consolidate_results",
            target_type="ECOEEvent",
            target_id=str(ecoe_event_id),
            payload={"student_count": len(results)},
        ))
    if commit:
        db.commit()
    return results


def build_traceability_report(
    db: Session,
    ecoe_event_id: int,
    consolidated_results: list[dict] | None = None,
) -> dict:
    students = db.scalars(
        select(Student).where(Student.ecoe_event_id == ecoe_event_id, Student.is_active.is_(True))
    ).all()
    stations = db.scalars(
        select(Station).where(Station.ecoe_event_id == ecoe_event_id)
        .order_by(Station.station_number.asc(), Station.id.asc())
    ).all()
    checkins = db.scalars(
        select(StationCheckIn).where(
            StationCheckIn.ecoe_event_id == ecoe_event_id,
            StationCheckIn.mode == SessionMode.ejecucion.value,
        )
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    ).all()
    # Trazabilidad y checklist de cierre son sobre la EJECUCIÓN REAL: los
    # registros de pilotaje no cuentan para completitud, faltantes ni el
    # consolidado (mismo criterio que `compute_results`). Un estudiante que
    # solo pilotó y faltó a la ejecución debe verse como "sin actividad".
    evaluator_records = db.scalars(
        select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == ecoe_event_id,
            EvaluatorRecord.mode == SessionMode.ejecucion.value,
        )
        .order_by(EvaluatorRecord.created_at.desc(), EvaluatorRecord.id.desc())
    ).all()
    student_responses = db.scalars(
        select(StudentResponse).where(
            StudentResponse.ecoe_event_id == ecoe_event_id,
            StudentResponse.mode == SessionMode.ejecucion.value,
        )
        .order_by(StudentResponse.submitted_at.desc(), StudentResponse.id.desc())
    ).all()
    pilot_runs = db.scalars(
        select(PilotRun).where(PilotRun.ecoe_event_id == ecoe_event_id)
        .order_by(PilotRun.created_at.desc(), PilotRun.id.desc())
    ).all()
    evaluator_assignments = db.scalars(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.role_code == RoleCode.evaluador.value,
        )
    ).all()

    results = consolidated_results if consolidated_results is not None else compute_results(db, ecoe_event_id)
    results_by_student = {int(item["student_id"]): item for item in results}
    students_by_id = {student.id: student for student in students}
    stations_by_id = {station.id: station for station in stations}

    station_primary_evaluator: dict[int, str] = {}
    for assignment in evaluator_assignments:
        full_name = " ".join(part for part in [assignment.name, assignment.last_name] if part).strip()
        for station_id in assignment.station_ids or []:
            if station_id and station_id not in station_primary_evaluator:
                station_primary_evaluator[int(station_id)] = full_name or assignment.email

    # Expected counts are per CIRCUIT: in mirrored circuits each student only
    # visits their own circuit's stations, so counting every station of the
    # event would inflate "missing" metrics and completion would never close.
    def _circuit_key(value: str | None) -> str:
        return str(value or "").strip().lower()

    evaluator_required_by_circuit: dict[str, int] = {}
    student_form_required_by_circuit: dict[str, int] = {}
    for station in stations:
        key = _circuit_key(station.circuit_name)
        if station.requires_evaluator:
            evaluator_required_by_circuit[key] = evaluator_required_by_circuit.get(key, 0) + 1
        if station.requires_student_form:
            student_form_required_by_circuit[key] = student_form_required_by_circuit.get(key, 0) + 1
    total_evaluator_required = sum(evaluator_required_by_circuit.values())
    total_student_form_required = sum(student_form_required_by_circuit.values())
    station_circuit_keys = {_circuit_key(station.circuit_name) for station in stations}

    def _required_for_student(student: Student) -> tuple[int, int]:
        key = _circuit_key(student.circuit_name)
        if key not in station_circuit_keys:
            # Circuito sin correspondencia textual con las estaciones:
            # fallback conservador al total del evento.
            return total_evaluator_required, total_student_form_required
        return (
            evaluator_required_by_circuit.get(key, 0),
            student_form_required_by_circuit.get(key, 0),
        )

    expected_evaluations_total = 0
    expected_student_submissions_total = 0

    deferred_grading_station_ids = {
        station.id for station in stations if station.requires_deferred_grading
    }

    student_traceability: list[dict] = []
    for student in students:
        required_evaluator_station_count, required_student_form_station_count = (
            _required_for_student(student)
        )
        expected_evaluations_total += required_evaluator_station_count
        expected_student_submissions_total += required_student_form_station_count
        student_checkins = [item for item in checkins if item.student_id == student.id]
        student_evaluations = [item for item in evaluator_records if item.student_id == student.id]
        student_form_responses = [item for item in student_responses if item.student_id == student.id]
        latest_checkin = student_checkins[0].confirmed_at if student_checkins else None
        latest_evaluation = student_evaluations[0].created_at if student_evaluations else None
        latest_student_response = student_form_responses[0].submitted_at if student_form_responses else None
        last_activity = max(
            [item for item in [latest_checkin, latest_evaluation, latest_student_response] if item],
            default=None,
        )
        has_expected_evaluations = len(student_evaluations) >= required_evaluator_station_count
        has_expected_student_responses = len(student_form_responses) >= required_student_form_station_count
        # Respuestas en estaciones de corrección diferida aún sin puntaje
        # definitivo: el estudiante no está "completo" hasta que se corrijan.
        pending_deferred_gradings = sum(
            1
            for item in student_form_responses
            if item.station_id in deferred_grading_station_ids
            and item.max_score is not None
            and item.score_obtained is None
        )
        if not student_checkins and not student_evaluations and not student_form_responses:
            completion_status = "sin actividad"
        elif (
            has_expected_evaluations
            and has_expected_student_responses
            and pending_deferred_gradings == 0
        ):
            completion_status = "completo"
        else:
            completion_status = "parcial"

        result_item = results_by_student.get(student.id, {})
        student_traceability.append({
            "id": student.id, "student_id": student.id,
            "ecoe_number": student.ecoe_number,
            "student_name": f"{student.name} {student.last_name}",
            "checkins_confirmed": len(student_checkins),
            "evaluator_submissions": len(student_evaluations),
            "student_submissions": len(student_form_responses),
            "missing_evaluations": max(0, required_evaluator_station_count - len(student_evaluations)),
            "missing_student_submissions": max(0, required_student_form_station_count - len(student_form_responses)),
            "pending_deferred_gradings": pending_deferred_gradings,
            "completion_status": completion_status,
            "last_checkin_at": latest_checkin.isoformat() if latest_checkin else None,
            "last_evaluation_at": latest_evaluation.isoformat() if latest_evaluation else None,
            "last_student_submission_at": latest_student_response.isoformat() if latest_student_response else None,
            "last_activity_at": last_activity.isoformat() if last_activity else None,
            "total_score": result_item.get("total_score", 0),
            "percentage": result_item.get("percentage", 0),
            "equivalent_grade": result_item.get("equivalent_grade", 0),
        })

    station_traceability: list[dict] = []
    for station in stations:
        station_checkins = [item for item in checkins if item.station_id == station.id]
        station_evaluations = [item for item in evaluator_records if item.station_id == station.id]
        station_form_responses = [item for item in student_responses if item.station_id == station.id]
        latest_station_activity = max(
            [item for item in [
                station_checkins[0].confirmed_at if station_checkins else None,
                station_evaluations[0].created_at if station_evaluations else None,
                station_form_responses[0].submitted_at if station_form_responses else None,
            ] if item],
            default=None,
        )
        if not station_checkins and not station_evaluations and not station_form_responses:
            station_status = "sin registros"
        elif station_evaluations or station_form_responses:
            station_status = "con evidencia"
        else:
            station_status = "con check-in"

        station_traceability.append({
            "id": station.id, "station_id": station.id,
            "station_number": station.station_number,
            "station_name": station.name,
            "circuit_name": station.circuit_name,
            "status": station_status,
            "assigned_evaluator": station_primary_evaluator.get(station.id, "Sin asignar"),
            "checkins_count": len(station_checkins),
            "evaluations_count": len(station_evaluations),
            "student_submissions_count": len(station_form_responses),
            "last_activity_at": latest_station_activity.isoformat() if latest_station_activity else None,
        })

    activity_log: list[dict] = []
    for pilot_run in pilot_runs:
        activity_log.append({
            "timestamp": pilot_run.created_at.isoformat(),
            "type": "pilotaje", "label": pilot_run.name,
            "detail": f"Pilotaje {pilot_run.scope.replace('_', ' ')} registrado.",
            "actor": "Coordinación ECOE", "mode": "pilotaje",
        })
    for checkin in checkins:
        student = students_by_id.get(checkin.student_id)
        station = stations_by_id.get(checkin.station_id)
        if not student or not station:
            continue
        activity_log.append({
            "timestamp": checkin.confirmed_at.isoformat(), "type": "checkin",
            "label": "Ingreso confirmado",
            "detail": f"{student.ecoe_number} - {student.name} {student.last_name} en estación {station.station_number}: {station.name}.",
            "actor": checkin.evaluator_name, "mode": checkin.mode,
        })
    for record in evaluator_records:
        student = students_by_id.get(record.student_id)
        station = stations_by_id.get(record.station_id)
        if not student or not station:
            continue
        activity_log.append({
            "timestamp": record.created_at.isoformat(), "type": "evaluacion",
            "label": "Evaluación enviada",
            "detail": f"{student.ecoe_number} - {student.name} {student.last_name} evaluado en estación {station.station_number}: {station.name}.",
            "actor": record.evaluator_name, "mode": record.mode,
        })
    for response in student_responses:
        student = students_by_id.get(response.student_id)
        station = stations_by_id.get(response.station_id)
        if not student or not station:
            continue
        activity_log.append({
            "timestamp": response.submitted_at.isoformat(), "type": "respuesta_estudiante",
            "label": "Respuesta del estudiante",
            "detail": f"{student.ecoe_number} - {student.name} {student.last_name} respondió en estación {station.station_number}: {station.name}.",
            "actor": f"{student.name} {student.last_name}", "mode": response.mode,
        })
    activity_log.sort(key=lambda item: item["timestamp"], reverse=True)

    return {
        "summary": {
            "active_students": len(students),
            "stations": len(stations),
            "expected_evaluations": expected_evaluations_total,
            "expected_student_submissions": expected_student_submissions_total,
            "confirmed_checkins": len(checkins),
            "evaluator_submissions": len(evaluator_records),
            "student_submissions": len(student_responses),
            "pilot_runs": len(pilot_runs),
        },
        "student_traceability": student_traceability,
        "station_traceability": station_traceability,
        "activity_log": activity_log[:25],
    }


def export_results_excel(db: Session, ecoe_event_id: int, *, persist: bool = False) -> bytes:
    if persist:
        data = persist_results(db, ecoe_event_id)
    else:
        data, _, _ = read_results(db, ecoe_event_id)
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
        text.textLine(f"Estación: {station.station_number} - {station.name}")
        text.textLine(f"Instrucción estudiante: {station.pre_entry_instruction}")
        text.textLine(f"Instrucción evaluador: {station.evaluator_instruction}")
        text.textLine(f"Materiales: {station.materials}")
    else:
        stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()
        text.textLine("Resumen general de estaciones")
        for station in stations:
            text.textLine(f"{station.station_number}. {station.name} [{station.status}] {station.circuit_name}")
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
    db.add(ContingencyExport(
        ecoe_event_id=ecoe_event_id,
        export_type=export_type,
        file_path=str(path),
    ))
    db.commit()
    return str(path)
