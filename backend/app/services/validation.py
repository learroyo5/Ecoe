"""ECOE validation and status management."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssessmentTool,
    ECOEEvent,
    LiveSession,
    MediaAsset,
    PilotRun,
    StaffAssignment,
    Station,
    Student,
)
from app.models.enums import ECOEStatus, RoleCode, StationStatus

# Re-export for backward compatibility
__all__ = ["compute_ecoe_validation", "update_ecoe_status"]


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

    # Preload assessment tools to avoid N+1
    tool_ids = [s.assessment_tool_id for s in stations if s.assessment_tool_id]
    tools_by_id: dict[int, AssessmentTool] = {}
    if tool_ids:
        tools_by_id = {
            t.id: t
            for t in db.scalars(
                select(AssessmentTool).where(AssessmentTool.id.in_(tool_ids))
            ).all()
        }

    # Preload media counts per station to avoid N+1
    media_counts: dict[int, int] = {}
    if stations:
        media_rows = db.execute(
            select(MediaAsset.station_id, func.count(MediaAsset.id))
            .where(MediaAsset.station_id.in_([s.id for s in stations]))
            .group_by(MediaAsset.station_id)
        ).all()
        media_counts = {row[0]: row[1] for row in media_rows}

    station_issues: list[dict] = []
    complete_stations = 0

    for station in stations:
        blockers: list[str] = []
        warnings: list[str] = []
        assessment_tool = tools_by_id.get(station.assessment_tool_id) if station.assessment_tool_id else None
        question_count = len((station.student_form_definition or {}).get("questions", []))
        media_count = media_counts.get(station.id, 0)

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

        station_issues.append({
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
        })

    forms_ready = all(
        issue["question_count"] > 0 or not next(
            s for s in stations if s.id == issue["station_id"]
        ).requires_student_form
        for issue in station_issues
    ) if station_issues else True
    tools_ready = all(
        issue["has_instrument"] or not next(
            s for s in stations if s.id == issue["station_id"]
        ).requires_evaluator
        for issue in station_issues
    ) if station_issues else True
    multimedia_ready = all(
        issue["media_count"] > 0 or not next(
            s for s in stations if s.id == issue["station_id"]
        ).uses_multimedia
        for issue in station_issues
    ) if station_issues else True
    assignments_ready = all(
        issue["has_evaluator_assignment"] or not next(
            s for s in stations if s.id == issue["station_id"]
        ).requires_evaluator
        for issue in station_issues
    ) if station_issues else True
    timer_ready = ecoe_event.station_time_minutes > 0 and ecoe_event.transition_time_minutes >= 0
    metadata_ready = bool(
        ecoe_event.name and ecoe_event.course_name and ecoe_event.school_name
        and ecoe_event.responsible_teacher and ecoe_event.contact_email
    )
    all_stations_ready = station_count > 0 and complete_stations == station_count

    can_pilot = metadata_ready and students_count > 0 and station_count > 0 and timer_ready and all_stations_ready
    can_publish = (
        metadata_ready and all_stations_ready and tools_ready and forms_ready
        and multimedia_ready and assignments_ready and timer_ready and pilot_count > 0
    )
    has_live_session = db.scalar(
        select(func.count(LiveSession.id)).where(LiveSession.ecoe_event_id == ecoe_event.id)
    )
    can_start_live = (
        ecoe_event.status == ECOEStatus.publicado.value
        and can_publish and has_live_session > 0 and ecoe_event.total_groups > 0
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
            item for item in [
                None if tools_ready else "Hay estaciones con evaluacion sin instrumento o con pauta incompleta.",
                None if forms_ready else "Hay estaciones que requieren formulario del estudiante y aun no tienen preguntas guardadas.",
                None if multimedia_ready else "Hay estaciones multimedia sin archivos cargados.",
                None if assignments_ready else "Hay estaciones con evaluador requerido, pero sin asignacion principal.",
            ] if item
        ],
        "blockers": [
            item for item in [
                None if metadata_ready else "Faltan datos base del ECOE.",
                None if students_count > 0 else "No hay estudiantes activos cargados.",
                None if station_count > 0 else "No hay estaciones creadas.",
                None if timer_ready else "Los tiempos oficiales del ECOE no son validos.",
                None if all_stations_ready else "Hay estaciones con faltantes operativos que impiden pilotar o publicar.",
                None if pilot_count > 0 else "Aun no se ha registrado ningun pilotaje.",
                None if has_live_session > 0 else "No existe una sesion en vivo creada para la ejecucion real.",
            ] if item
        ],
        "pilot_checks": [
            {"label": "Datos base del ECOE", "ok": metadata_ready,
             "detail": "Nombre, curso, escuela, docente responsable y correo de contacto deben estar completos."},
            {"label": "Estudiantes activos cargados", "ok": students_count > 0,
             "detail": f"Hay {students_count} estudiantes activos registrados."},
            {"label": "Estaciones construidas", "ok": station_count > 0,
             "detail": f"Hay {station_count} estaciones creadas en este ECOE."},
            {"label": "Tiempos oficiales configurados", "ok": timer_ready,
             "detail": f"{ecoe_event.station_time_minutes} min por estacion y {ecoe_event.transition_time_minutes} min de transicion."},
            {"label": "Estaciones listas para pilotaje", "ok": all_stations_ready,
             "detail": f"{complete_stations} de {station_count} estaciones cumplen el minimo operativo."},
        ],
        "publication_checks": [
            {"label": "Estructura operativa completa", "ok": all_stations_ready and metadata_ready and timer_ready,
             "detail": f"{complete_stations} de {station_count} estaciones estan completas."},
            {"label": "Instrumentos y formularios resueltos", "ok": tools_ready and forms_ready,
             "detail": "Todas las estaciones con evaluador o formulario deben tener su configuracion guardada."},
            {"label": "Recursos y asignaciones resueltos", "ok": multimedia_ready and assignments_ready,
             "detail": "Multimedia declarada y asignacion principal de evaluadores deben estar completos."},
            {"label": "Pilotajes registrados", "ok": pilot_count > 0,
             "detail": f"Se han registrado {pilot_count} pilotajes."},
        ],
        "live_checks": [
            {"label": "ECOE publicado", "ok": ecoe_event.status == ECOEStatus.publicado.value,
             "detail": f"Estado actual: {ecoe_event.status}."},
            {"label": "Publicacion valida", "ok": can_publish,
             "detail": "No debe haber bloqueos estructurales pendientes antes de iniciar la ejecucion real."},
            {"label": "Sesion en vivo creada", "ok": has_live_session > 0,
             "detail": f"Sesiones en vivo registradas: {has_live_session}."},
            {"label": "Grupos configurados", "ok": ecoe_event.total_groups > 0,
             "detail": f"Grupos configurados: {ecoe_event.total_groups}."},
        ],
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
            db.add(LiveSession(
                ecoe_event_id=ecoe_event.id,
                station_time_seconds=max(1, round(ecoe_event.station_time_minutes * 60)),
                transition_time_seconds=max(0, round(ecoe_event.transition_time_minutes * 60)),
                remaining_seconds=max(1, round(ecoe_event.station_time_minutes * 60)),
                status="ready",
            ))
        stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event.id)).all()
        for station in stations:
            if station.status not in {
                StationStatus.activa.value, StationStatus.finalizada.value, StationStatus.cerrada.value,
            }:
                station.status = StationStatus.publicada.value
                db.add(station)

    ecoe_event.status = target_status
    db.add(ecoe_event)
    db.commit()
    db.refresh(ecoe_event)
    return ecoe_event
