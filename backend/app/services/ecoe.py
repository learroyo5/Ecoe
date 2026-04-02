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
    MediaAsset,
    PilotRun,
    StaffAssignment,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, RoleCode, SessionMode


def compute_ecoe_validation(db: Session, ecoe_event: ECOEEvent) -> dict:
    students_count = db.scalar(
        select(func.count(Student.id)).where(
            Student.ecoe_event_id == ecoe_event.id,
            Student.is_active.is_(True),
        )
    )
    station_count = db.scalar(
        select(func.count(Station.id)).where(Station.ecoe_event_id == ecoe_event.id)
    )
    pilot_count = db.scalar(
        select(func.count(PilotRun.id)).where(PilotRun.ecoe_event_id == ecoe_event.id)
    )
    stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event.id)).all()

    evaluator_assignments = db.scalars(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event.id,
            StaffAssignment.role_code == RoleCode.evaluador.value,
        )
    ).all()
    assigned_station_ids = {
        int(station_id)
        for assignment in evaluator_assignments
        for station_id in (assignment.station_ids or [])
        if station_id
    }

    station_issues: list[dict] = []
    complete_stations = 0

    for station in stations:
        blockers: list[str] = []
        warnings: list[str] = []
        assessment_tool = db.get(AssessmentTool, station.assessment_tool_id) if station.assessment_tool_id else None
        question_count = len((station.student_form_definition or {}).get("questions", []))
        media_count = db.scalar(
            select(func.count(MediaAsset.id)).where(MediaAsset.station_id == station.id)
        ) or 0

        if not station.name.strip():
            blockers.append("Falta nombre de la estacion.")
        if not station.expected_outcomes.strip():
            blockers.append("Faltan aprendizajes o desempenos esperados.")
        if not station.student_activity.strip():
            blockers.append("Falta actividad especifica del estudiante.")
        if not station.pre_entry_instruction.strip():
            blockers.append("Falta instruccion previa de ingreso.")
        if not station.student_station_instruction.strip():
            blockers.append("Faltan instrucciones dentro de la estacion para el estudiante.")
        if station.requires_evaluator and not station.evaluator_instruction.strip():
            blockers.append("Falta guia para el evaluador.")
        if station.requires_evaluator and station.id not in assigned_station_ids:
            blockers.append("No tiene evaluador principal asignado.")
        if station.requires_evaluator and not station.assessment_tool_id:
            blockers.append("No tiene instrumento de evaluacion asignado.")
        if station.requires_evaluator and assessment_tool and not assessment_tool.items:
            blockers.append("La pauta asignada no tiene criterios evaluables.")
        if station.requires_student_form and question_count == 0:
            blockers.append("Requiere formulario del estudiante, pero no tiene preguntas guardadas.")
        if station.uses_multimedia and media_count == 0:
            blockers.append("Declara uso de multimedia, pero no tiene archivos cargados.")
        if station.uses_simulated_patient and not station.simulated_patient_id:
            blockers.append("Declara paciente simulado, pero no tiene personaje asociado.")
        if station.max_score <= 0:
            blockers.append("El puntaje maximo de la estacion debe ser mayor que cero.")

        if not station.materials.strip():
            warnings.append("No se han detallado materiales o recursos fisicos.")
        if station.uses_multimedia and not station.multimedia_notes.strip():
            warnings.append("Hay multimedia cargada o declarada, pero faltan indicaciones operativas.")
        if not station.template_id:
            warnings.append("No tiene plantilla de referencia asociada.")

        ready_for_pilot = len(blockers) == 0
        if ready_for_pilot:
            complete_stations += 1

        station_issues.append(
            {
                "station_id": station.id,
                "station_number": station.station_number,
                "station_name": station.name,
                "circuit_name": station.circuit_name,
                "ready_for_pilot": ready_for_pilot,
                "ready_for_publication": ready_for_pilot,
                "blockers": blockers,
                "warnings": warnings,
                "question_count": question_count,
                "media_count": media_count,
                "has_instrument": bool(station.assessment_tool_id),
                "has_evaluator_assignment": station.id in assigned_station_ids,
            }
        )

    forms_ready = all(issue["question_count"] > 0 or not next(
        station for station in stations if station.id == issue["station_id"]
    ).requires_student_form for issue in station_issues) if station_issues else True
    tools_ready = all(issue["has_instrument"] or not next(
        station for station in stations if station.id == issue["station_id"]
    ).requires_evaluator for issue in station_issues) if station_issues else True
    multimedia_ready = all(
        issue["media_count"] > 0 or not next(
            station for station in stations if station.id == issue["station_id"]
        ).uses_multimedia for issue in station_issues
    ) if station_issues else True
    assignments_ready = all(
        issue["has_evaluator_assignment"] or not next(
            station for station in stations if station.id == issue["station_id"]
        ).requires_evaluator for issue in station_issues
    ) if station_issues else True
    timer_ready = ecoe_event.station_time_minutes > 0 and ecoe_event.transition_time_minutes >= 0
    metadata_ready = bool(
        ecoe_event.name
        and ecoe_event.course_name
        and ecoe_event.school_name
        and ecoe_event.responsible_teacher
        and ecoe_event.contact_email
    )
    all_stations_ready = station_count > 0 and complete_stations == station_count

    can_pilot = (
        metadata_ready
        and students_count > 0
        and station_count > 0
        and timer_ready
        and all_stations_ready
    )
    can_publish = (
        metadata_ready
        and all_stations_ready
        and tools_ready
        and forms_ready
        and multimedia_ready
        and assignments_ready
        and timer_ready
        and pilot_count > 0
    )
    has_live_session = db.scalar(
        select(func.count(LiveSession.id)).where(LiveSession.ecoe_event_id == ecoe_event.id)
    )
    can_start_live = (
        ecoe_event.status == ECOEStatus.publicado.value
        and can_publish
        and has_live_session > 0
        and ecoe_event.total_groups > 0
    )

    pilot_checks = [
        {
            "label": "Datos base del ECOE",
            "ok": metadata_ready,
            "detail": "Nombre, curso, escuela, docente responsable y correo de contacto deben estar completos.",
        },
        {
            "label": "Estudiantes activos cargados",
            "ok": students_count > 0,
            "detail": f"Hay {students_count} estudiantes activos registrados.",
        },
        {
            "label": "Estaciones construidas",
            "ok": station_count > 0,
            "detail": f"Hay {station_count} estaciones creadas en este ECOE.",
        },
        {
            "label": "Tiempos oficiales configurados",
            "ok": timer_ready,
            "detail": f"{ecoe_event.station_time_minutes} min por estacion y {ecoe_event.transition_time_minutes} min de transicion.",
        },
        {
            "label": "Estaciones listas para pilotaje",
            "ok": all_stations_ready,
            "detail": f"{complete_stations} de {station_count} estaciones cumplen el minimo operativo.",
        },
    ]

    publication_checks = [
        {
            "label": "Estructura operativa completa",
            "ok": all_stations_ready and metadata_ready and timer_ready,
            "detail": f"{complete_stations} de {station_count} estaciones estan completas.",
        },
        {
            "label": "Instrumentos y formularios resueltos",
            "ok": tools_ready and forms_ready,
            "detail": "Todas las estaciones con evaluador o formulario deben tener su configuracion guardada.",
        },
        {
            "label": "Recursos y asignaciones resueltos",
            "ok": multimedia_ready and assignments_ready,
            "detail": "Multimedia declarada y asignacion principal de evaluadores deben estar completos.",
        },
        {
            "label": "Pilotajes registrados",
            "ok": pilot_count > 0,
            "detail": f"Se han registrado {pilot_count} pilotajes.",
        },
    ]

    live_checks = [
        {
            "label": "ECOE publicado",
            "ok": ecoe_event.status == ECOEStatus.publicado.value,
            "detail": f"Estado actual: {ecoe_event.status}.",
        },
        {
            "label": "Publicacion valida",
            "ok": can_publish,
            "detail": "No debe haber bloqueos estructurales pendientes antes de iniciar la ejecucion real.",
        },
        {
            "label": "Sesion en vivo creada",
            "ok": has_live_session > 0,
            "detail": f"Sesiones en vivo registradas: {has_live_session}.",
        },
        {
            "label": "Grupos configurados",
            "ok": ecoe_event.total_groups > 0,
            "detail": f"Grupos configurados: {ecoe_event.total_groups}.",
        },
    ]

    warnings = [
        item
        for item in [
            None if tools_ready else "Hay estaciones con evaluacion sin instrumento o con pauta incompleta.",
            None if forms_ready else "Hay estaciones que requieren formulario del estudiante y aun no tienen preguntas guardadas.",
            None if multimedia_ready else "Hay estaciones multimedia sin archivos cargados.",
            None if assignments_ready else "Hay estaciones con evaluador requerido, pero sin asignacion principal.",
        ]
        if item
    ]

    blockers = [
        item
        for item in [
            None if metadata_ready else "Faltan datos base del ECOE.",
            None if students_count > 0 else "No hay estudiantes activos cargados.",
            None if station_count > 0 else "No hay estaciones creadas.",
            None if timer_ready else "Los tiempos oficiales del ECOE no son validos.",
            None if all_stations_ready else "Hay estaciones con faltantes operativos que impiden pilotar o publicar.",
            None if pilot_count > 0 else "Aun no se ha registrado ningun pilotaje.",
            None if has_live_session > 0 else "No existe una sesion en vivo creada para la ejecucion real.",
        ]
        if item
    ]

    return {
        "students_count": students_count,
        "station_count": station_count,
        "pilot_count": pilot_count,
        "complete_stations": complete_stations,
        "can_pilot": can_pilot,
        "can_publish": can_publish,
        "can_start_live": can_start_live,
        "warnings": warnings,
        "blockers": blockers,
        "pilot_checks": pilot_checks,
        "publication_checks": publication_checks,
        "live_checks": live_checks,
        "station_issues": station_issues,
        "assignments_ready": assignments_ready,
        "metadata_ready": metadata_ready,
        "timer_ready": timer_ready,
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

    if target_status == ECOEStatus.publicado.value:
        live_session = db.scalar(
            select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event.id).limit(1)
        )
        if not live_session:
            db.add(
                LiveSession(
                    ecoe_event_id=ecoe_event.id,
                    station_time_seconds=max(1, round(ecoe_event.station_time_minutes * 60)),
                    transition_time_seconds=max(0, round(ecoe_event.transition_time_minutes * 60)),
                    remaining_seconds=max(1, round(ecoe_event.station_time_minutes * 60)),
                    status="ready",
                )
            )

        stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event.id)).all()
        for station in stations:
            if station.status not in {
                StationStatus.activa.value,
                StationStatus.finalizada.value,
                StationStatus.cerrada.value,
            }:
                station.status = StationStatus.publicada.value
                db.add(station)

    ecoe_event.status = target_status
    db.add(ecoe_event)
    db.commit()
    db.refresh(ecoe_event)
    return ecoe_event


def compute_results(db: Session, ecoe_event_id: int) -> list[dict]:
    students = db.scalars(
        select(Student).where(Student.ecoe_event_id == ecoe_event_id, Student.is_active.is_(True))
    ).all()
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


def build_traceability_report(
    db: Session,
    ecoe_event_id: int,
    consolidated_results: list[dict] | None = None,
) -> dict:
    students = db.scalars(
        select(Student).where(Student.ecoe_event_id == ecoe_event_id, Student.is_active.is_(True))
    ).all()
    stations = db.scalars(
        select(Station)
        .where(Station.ecoe_event_id == ecoe_event_id)
        .order_by(Station.station_number.asc(), Station.id.asc())
    ).all()
    checkins = db.scalars(
        select(StationCheckIn)
        .where(StationCheckIn.ecoe_event_id == ecoe_event_id)
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    ).all()
    evaluator_records = db.scalars(
        select(EvaluatorRecord)
        .where(EvaluatorRecord.ecoe_event_id == ecoe_event_id)
        .order_by(EvaluatorRecord.created_at.desc(), EvaluatorRecord.id.desc())
    ).all()
    student_responses = db.scalars(
        select(StudentResponse)
        .where(StudentResponse.ecoe_event_id == ecoe_event_id)
        .order_by(StudentResponse.submitted_at.desc(), StudentResponse.id.desc())
    ).all()
    pilot_runs = db.scalars(
        select(PilotRun)
        .where(PilotRun.ecoe_event_id == ecoe_event_id)
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

    required_evaluator_station_count = sum(1 for station in stations if station.requires_evaluator)
    required_student_form_station_count = sum(1 for station in stations if station.requires_student_form)

    student_traceability: list[dict] = []
    for student in students:
        student_checkins = [item for item in checkins if item.student_id == student.id]
        student_evaluations = [item for item in evaluator_records if item.student_id == student.id]
        student_form_responses = [item for item in student_responses if item.student_id == student.id]
        latest_checkin = student_checkins[0].confirmed_at if student_checkins else None
        latest_evaluation = student_evaluations[0].created_at if student_evaluations else None
        latest_student_response = (
            student_form_responses[0].submitted_at if student_form_responses else None
        )
        last_activity = max(
            [item for item in [latest_checkin, latest_evaluation, latest_student_response] if item],
            default=None,
        )

        has_expected_evaluations = len(student_evaluations) >= required_evaluator_station_count
        has_expected_student_responses = (
            len(student_form_responses) >= required_student_form_station_count
        )
        if not student_checkins and not student_evaluations and not student_form_responses:
            completion_status = "sin actividad"
        elif has_expected_evaluations and has_expected_student_responses:
            completion_status = "completo"
        else:
            completion_status = "parcial"

        result_item = results_by_student.get(student.id, {})
        student_traceability.append(
            {
                "id": student.id,
                "student_id": student.id,
                "ecoe_number": student.ecoe_number,
                "student_name": f"{student.name} {student.last_name}",
                "checkins_confirmed": len(student_checkins),
                "evaluator_submissions": len(student_evaluations),
                "student_submissions": len(student_form_responses),
                "missing_evaluations": max(0, required_evaluator_station_count - len(student_evaluations)),
                "missing_student_submissions": max(
                    0, required_student_form_station_count - len(student_form_responses)
                ),
                "completion_status": completion_status,
                "last_checkin_at": latest_checkin.isoformat() if latest_checkin else None,
                "last_evaluation_at": latest_evaluation.isoformat() if latest_evaluation else None,
                "last_student_submission_at": (
                    latest_student_response.isoformat() if latest_student_response else None
                ),
                "last_activity_at": last_activity.isoformat() if last_activity else None,
                "total_score": result_item.get("total_score", 0),
                "percentage": result_item.get("percentage", 0),
                "equivalent_grade": result_item.get("equivalent_grade", 0),
            }
        )

    station_traceability: list[dict] = []
    for station in stations:
        station_checkins = [item for item in checkins if item.station_id == station.id]
        station_evaluations = [item for item in evaluator_records if item.station_id == station.id]
        station_form_responses = [item for item in student_responses if item.station_id == station.id]
        latest_station_activity = max(
            [
                item
                for item in [
                    station_checkins[0].confirmed_at if station_checkins else None,
                    station_evaluations[0].created_at if station_evaluations else None,
                    station_form_responses[0].submitted_at if station_form_responses else None,
                ]
                if item
            ],
            default=None,
        )
        if not station_checkins and not station_evaluations and not station_form_responses:
            station_status = "sin registros"
        elif station_evaluations or station_form_responses:
            station_status = "con evidencia"
        else:
            station_status = "con check-in"

        station_traceability.append(
            {
                "id": station.id,
                "station_id": station.id,
                "station_number": station.station_number,
                "station_name": station.name,
                "circuit_name": station.circuit_name,
                "status": station_status,
                "assigned_evaluator": station_primary_evaluator.get(station.id, "Sin asignar"),
                "checkins_count": len(station_checkins),
                "evaluations_count": len(station_evaluations),
                "student_submissions_count": len(station_form_responses),
                "last_activity_at": latest_station_activity.isoformat() if latest_station_activity else None,
            }
        )

    activity_log: list[dict] = []
    for pilot_run in pilot_runs:
        activity_log.append(
            {
                "timestamp": pilot_run.created_at.isoformat(),
                "type": "pilotaje",
                "label": pilot_run.name,
                "detail": f"Pilotaje {pilot_run.scope.replace('_', ' ')} registrado.",
                "actor": "Coordinacion ECOE",
                "mode": "pilotaje",
            }
        )
    for checkin in checkins:
        student = students_by_id.get(checkin.student_id)
        station = stations_by_id.get(checkin.station_id)
        if not student or not station:
            continue
        activity_log.append(
            {
                "timestamp": checkin.confirmed_at.isoformat(),
                "type": "checkin",
                "label": "Ingreso confirmado",
                "detail": (
                    f"{student.ecoe_number} - {student.name} {student.last_name} "
                    f"en estacion {station.station_number}: {station.name}."
                ),
                "actor": checkin.evaluator_name,
                "mode": "ejecucion",
            }
        )
    for record in evaluator_records:
        student = students_by_id.get(record.student_id)
        station = stations_by_id.get(record.station_id)
        if not student or not station:
            continue
        activity_log.append(
            {
                "timestamp": record.created_at.isoformat(),
                "type": "evaluacion",
                "label": "Evaluacion enviada",
                "detail": (
                    f"{student.ecoe_number} - {student.name} {student.last_name} "
                    f"evaluado en estacion {station.station_number}: {station.name}."
                ),
                "actor": record.evaluator_name,
                "mode": record.mode,
            }
        )
    for response in student_responses:
        student = students_by_id.get(response.student_id)
        station = stations_by_id.get(response.station_id)
        if not student or not station:
            continue
        activity_log.append(
            {
                "timestamp": response.submitted_at.isoformat(),
                "type": "respuesta_estudiante",
                "label": "Respuesta del estudiante",
                "detail": (
                    f"{student.ecoe_number} - {student.name} {student.last_name} "
                    f"respondio en estacion {station.station_number}: {station.name}."
                ),
                "actor": f"{student.name} {student.last_name}",
                "mode": response.mode,
            }
        )
    activity_log.sort(key=lambda item: item["timestamp"], reverse=True)

    return {
        "summary": {
            "active_students": len(students),
            "stations": len(stations),
            "expected_evaluations": len(students) * required_evaluator_station_count,
            "expected_student_submissions": len(students) * required_student_form_station_count,
            "confirmed_checkins": len(checkins),
            "evaluator_submissions": len(evaluator_records),
            "student_submissions": len(student_responses),
            "pilot_runs": len(pilot_runs),
        },
        "student_traceability": student_traceability,
        "station_traceability": station_traceability,
        "activity_log": activity_log[:25],
    }


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
