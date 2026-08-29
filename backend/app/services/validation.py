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
    StationCheckIn,
    Student,
    StudentResponse,
    User,
)
from app.models.enums import ECOEStatus, RoleCode, SessionMode, StationStatus
from app.utils.helpers import normalize_email

# Etiquetas legibles de los estados internos, para textos visibles al usuario.
ECOE_STATUS_LABELS: dict[str, str] = {
    ECOEStatus.borrador.value: "Borrador",
    ECOEStatus.en_configuracion.value: "En configuración",
    ECOEStatus.listo_para_pilotaje.value: "Listo para pilotaje",
    ECOEStatus.en_pilotaje.value: "En pilotaje",
    ECOEStatus.pilotaje_validado.value: "Pilotaje validado",
    ECOEStatus.publicado.value: "Publicado",
    ECOEStatus.en_ejecucion.value: "En ejecución",
    ECOEStatus.cerrado.value: "Cerrado",
    ECOEStatus.archivado.value: "Archivado",
}

# Re-export for backward compatibility
__all__ = ["compute_ecoe_validation", "update_ecoe_status"]


def _question_points(question: dict) -> float:
    try:
        return float(question.get("points") or 0)
    except (TypeError, ValueError):
        return 0.0


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
    corrector_assignments = db.scalars(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event.id,
            StaffAssignment.role_code == RoleCode.corrector.value,
        )
    ).all()
    corrector_station_ids = {
        int(station_id)
        for assignment in corrector_assignments
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
            blockers.append("Falta nombre de la estación.")
        if not station.expected_outcomes.strip():
            blockers.append("Faltan aprendizajes o desempeños esperados.")
        if not station.student_activity.strip():
            blockers.append("Falta actividad específica del estudiante.")
        if not station.pre_entry_instruction.strip():
            blockers.append("Falta instrucción previa de ingreso.")
        if not station.student_station_instruction.strip():
            blockers.append("Faltan instrucciones dentro de la estación para el estudiante.")
        if station.requires_evaluator and not station.evaluator_instruction.strip():
            blockers.append("Falta guía para el evaluador.")
        if station.requires_evaluator and station.id not in assigned_station_ids:
            blockers.append("No tiene evaluador principal asignado.")
        if station.requires_evaluator and not station.assessment_tool_id:
            blockers.append("No tiene instrumento de evaluación asignado.")
        if station.requires_evaluator and assessment_tool and not assessment_tool.items:
            blockers.append("La pauta asignada no tiene criterios evaluables.")
        if station.requires_student_form and question_count == 0:
            blockers.append("Requiere formulario del estudiante, pero no tiene preguntas guardadas.")
        manual_scored_questions = sum(
            1
            for q in (station.student_form_definition or {}).get("questions", [])
            if isinstance(q, dict)
            and str(q.get("type") or "") not in {"single_choice", "multiple_choice"}
            and _question_points(q) > 0
        )
        if station.requires_deferred_grading:
            if not station.requires_student_form or manual_scored_questions == 0:
                blockers.append(
                    "Marca corrección diferida, pero no tiene preguntas de corrección manual con puntaje."
                )
            if station.id not in corrector_station_ids:
                blockers.append("No tiene corrector asignado para la evaluación diferida.")
        if station.uses_multimedia and media_count == 0:
            blockers.append("Declara uso de multimedia, pero no tiene archivos cargados.")
        if station.uses_simulated_patient and not station.simulated_patient_id:
            blockers.append("Declara paciente simulado, pero no tiene personaje asociado.")
        if station.max_score <= 0:
            blockers.append("El puntaje máximo de la estación debe ser mayor que cero.")

        if not station.materials.strip():
            warnings.append("No se han detallado materiales o recursos físicos.")
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
    # Estaciones de corrección diferida: cada una debe tener un corrector
    # asignado que la cubra (ver docs/architecture/EVALUACION_DIFERIDA_FASE1.md).
    deferred_grading_stations = [s for s in stations if s.requires_deferred_grading]
    deferred_grading_ready = all(
        station.id in corrector_station_ids for station in deferred_grading_stations
    )
    # Respuestas enviadas en estaciones de corrección diferida que aún no
    # tienen puntaje definitivo: quedan fuera del consolidado. No bloquea el
    # cierre, pero el modal de cierre lo advierte.
    pending_deferred_grading_station_numbers: list[int] = []
    if deferred_grading_stations:
        deferred_ids = [s.id for s in deferred_grading_stations]
        pending_station_ids = {
            row[0]
            for row in db.execute(
                select(StudentResponse.station_id)
                .where(
                    StudentResponse.ecoe_event_id == ecoe_event.id,
                    StudentResponse.station_id.in_(deferred_ids),
                    # Solo la ejecución real dispara la advertencia de cierre:
                    # una respuesta de pilotaje sin puntuar no es trabajo
                    # pendiente del corrector del evento real.
                    StudentResponse.mode == SessionMode.ejecucion.value,
                    StudentResponse.score_obtained.is_(None),
                    StudentResponse.max_score.is_not(None),
                )
                .distinct()
            ).all()
        }
        pending_deferred_grading_station_numbers = sorted(
            s.station_number for s in deferred_grading_stations if s.id in pending_station_ids
        )
    # Evaluadores asignados cuyo correo no tiene cuenta activa: el dia del
    # examen no podran iniciar sesion, pero la asignacion "se ve" completa.
    evaluator_emails = {
        normalize_email(assignment.email)
        for assignment in evaluator_assignments
        if assignment.email
    }
    active_account_emails: set[str] = set()
    if evaluator_emails:
        active_account_emails = {
            normalize_email(email)
            for (email,) in db.execute(
                select(User.email).where(
                    func.lower(User.email).in_(evaluator_emails),
                    User.is_active.is_(True),
                    User.account_status == "active",
                )
            ).all()
        }
    evaluators_without_account = sorted(evaluator_emails - active_account_emails)

    # Evaluadores dados de alta sin estación principal (permitido al invitar
    # desde OPT-5): la asignación se completa en /evaluators. Si llega el día
    # del examen sin estación, ese evaluador no puede hacer check-in.
    evaluators_without_station = sorted(
        normalize_email(assignment.email)
        for assignment in evaluator_assignments
        if assignment.email
        and not [station_id for station_id in (assignment.station_ids or []) if station_id]
    )

    # Formularios del estudiante sin puntaje: registran respuestas que no
    # suman al consolidado; debe ser una decision consciente, no un olvido.
    unscored_form_stations = sorted(
        station.station_number
        for station in stations
        if station.requires_student_form
        and (station.student_form_definition or {}).get("questions")
        and not any(
            isinstance(question, dict) and float(question.get("points") or 0) > 0
            for question in (station.student_form_definition or {}).get("questions", [])
        )
    )

    timer_ready = ecoe_event.station_time_minutes > 0 and ecoe_event.transition_time_minutes >= 0
    metadata_ready = bool(
        ecoe_event.name and ecoe_event.course_name and ecoe_event.school_name
        and ecoe_event.responsible_teacher and ecoe_event.contact_email
    )
    all_stations_ready = station_count > 0 and complete_stations == station_count

    can_pilot = metadata_ready and students_count > 0 and station_count > 0 and timer_ready and all_stations_ready
    can_publish = (
        metadata_ready and all_stations_ready and tools_ready and forms_ready
        and multimedia_ready and assignments_ready and deferred_grading_ready
        and timer_ready and pilot_count > 0
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
                None if tools_ready else "Hay estaciones con evaluación sin instrumento o con pauta incompleta.",
                None if forms_ready else "Hay estaciones que requieren formulario del estudiante y aún no tienen preguntas guardadas.",
                None if multimedia_ready else "Hay estaciones multimedia sin archivos cargados.",
                None if assignments_ready else "Hay estaciones con evaluador requerido, pero sin asignación principal.",
                None if deferred_grading_ready else "Hay estaciones de corrección diferida sin corrector asignado.",
                None if not pending_deferred_grading_station_numbers else (
                    "Estaciones de corrección diferida con respuestas sin puntuar (no sumarán a Resultados hasta corregirse): "
                    + ", ".join(str(number) for number in pending_deferred_grading_station_numbers)
                ),
                None if not evaluators_without_account else (
                    "Evaluadores asignados sin cuenta de usuario activa (no podrán iniciar sesión): "
                    + ", ".join(evaluators_without_account)
                ),
                None if not evaluators_without_station else (
                    "Evaluadores sin estación principal asignada (no podrán hacer check-in): "
                    + ", ".join(evaluators_without_station)
                ),
                None if not unscored_form_stations else (
                    "Estaciones con formulario sin puntaje definido (las respuestas no sumarán a Resultados): "
                    + ", ".join(str(number) for number in unscored_form_stations)
                ),
            ] if item
        ],
        "blockers": [
            item for item in [
                None if metadata_ready else "Faltan datos base del ECOE.",
                None if students_count > 0 else "No hay estudiantes activos cargados.",
                None if station_count > 0 else "No hay estaciones creadas.",
                None if timer_ready else "Los tiempos oficiales del ECOE no son validos.",
                None if all_stations_ready else "Hay estaciones con faltantes operativos que impiden pilotar o publicar.",
                None if pilot_count > 0 else "Aún no se ha registrado ningún pilotaje.",
                # La LiveSession solo se crea en la transición a `publicado`,
                # así que antes de publicar SIEMPRE falta y este bloqueo era
                # irresoluble para el usuario (aparecía junto a "Listo para
                # publicar"). El gate real de la ejecución en vivo lo cubre
                # `can_start_live` + el ítem "Sesión en vivo creada" de
                # `live_checks`; aquí solo se reporta una vez publicado.
                None if (
                    has_live_session > 0
                    or ecoe_event.status not in {
                        ECOEStatus.publicado.value,
                        ECOEStatus.en_ejecucion.value,
                    }
                ) else "No existe una sesión en vivo creada para la ejecución real.",
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
             "detail": f"{ecoe_event.station_time_minutes} min por estación y {ecoe_event.transition_time_minutes} min de transición."},
            {"label": "Estaciones listas para pilotaje", "ok": all_stations_ready,
             "detail": f"{complete_stations} de {station_count} estaciones cumplen el mínimo operativo."},
        ],
        "publication_checks": [
            {"label": "Estructura operativa completa", "ok": all_stations_ready and metadata_ready and timer_ready,
             "detail": f"{complete_stations} de {station_count} estaciones están completas."},
            {"label": "Instrumentos y formularios resueltos", "ok": tools_ready and forms_ready,
             "detail": "Todas las estaciones con evaluador o formulario deben tener su configuración guardada."},
            {"label": "Recursos y asignaciones resueltos", "ok": multimedia_ready and assignments_ready,
             "detail": "Multimedia declarada y asignación principal de evaluadores deben estar completos."},
            {"label": "Correctores de evaluación diferida asignados", "ok": deferred_grading_ready,
             "detail": (
                 f"{len(deferred_grading_stations)} estación(es) marcadas como corrección diferida; "
                 "cada una necesita un corrector asignado."
             )},
            {"label": "Pilotajes registrados", "ok": pilot_count > 0,
             "detail": f"Se han registrado {pilot_count} pilotajes."},
        ],
        "live_checks": [
            {"label": "ECOE publicado", "ok": ecoe_event.status == ECOEStatus.publicado.value,
             "detail": f"Estado actual: {ECOE_STATUS_LABELS.get(str(ecoe_event.status), ecoe_event.status)}."},
            {"label": "Publicación válida", "ok": can_publish,
             "detail": "No debe haber bloqueos estructurales pendientes antes de iniciar la ejecución real."},
            {"label": "Sesión en vivo creada", "ok": has_live_session > 0,
             "detail": f"Sesiones en vivo registradas: {has_live_session}."},
            {"label": "Grupos configurados", "ok": ecoe_event.total_groups > 0,
             "detail": f"Grupos configurados: {ecoe_event.total_groups}."},
        ],
        "station_issues": station_issues,
        "assignments_ready": assignments_ready,
        "deferred_grading_ready": deferred_grading_ready,
        "deferred_grading_station_count": len(deferred_grading_stations),
        "pending_deferred_grading_stations": pending_deferred_grading_station_numbers,
        "metadata_ready": metadata_ready,
        "timer_ready": timer_ready,
    }


# State machine for the ECOE lifecycle. Mirrors the transitions the UI
# offers (frontend/src/components/ecoe-form.tsx); the backend is the
# authority: any jump outside this graph is rejected even if a client
# crafts the request by hand. Keeping the target equal to the current
# status is always a no-op (full-form PUTs resend the status unchanged).
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    ECOEStatus.borrador.value: {ECOEStatus.en_configuracion.value},
    ECOEStatus.en_configuracion.value: {
        ECOEStatus.borrador.value,
        ECOEStatus.listo_para_pilotaje.value,
    },
    ECOEStatus.listo_para_pilotaje.value: {
        ECOEStatus.en_configuracion.value,
        ECOEStatus.en_pilotaje.value,
    },
    ECOEStatus.en_pilotaje.value: {
        ECOEStatus.listo_para_pilotaje.value,
        ECOEStatus.pilotaje_validado.value,
    },
    ECOEStatus.pilotaje_validado.value: {
        ECOEStatus.en_pilotaje.value,
        ECOEStatus.publicado.value,
    },
    ECOEStatus.publicado.value: {
        ECOEStatus.pilotaje_validado.value,
        ECOEStatus.en_ejecucion.value,
    },
    ECOEStatus.en_ejecucion.value: {ECOEStatus.cerrado.value},
    ECOEStatus.cerrado.value: {ECOEStatus.archivado.value},
    ECOEStatus.archivado.value: {ECOEStatus.borrador.value},
}


def update_ecoe_status(
    db: Session,
    ecoe_event: ECOEEvent,
    target_status: str,
    *,
    commit: bool = True,
    actor_email: str | None = None,
) -> ECOEEvent:
    """Aplica una transición del grafo `ALLOWED_STATUS_TRANSITIONS` y sus
    efectos colaterales dentro de la misma transacción:

    - `→ publicado`: crea la `LiveSession` inicial y pasa las estaciones a
      `publicada`.
    - `→ en_ejecucion`: cierra todos los `StationCheckIn` `confirmado` que
      queden (son residuos del pilotaje — el gate de envíos no permite
      check-ins reales antes de este punto), así el panel del evaluador y el
      kiosco no muestran un estudiante viejo como "activo" y esos check-ins
      no cuentan en la trazabilidad de la ejecución real.
    - `→ cerrado`: consolida resultados (`persist_results`) y fuerza el cierre
      de todos los check-ins abiertos, congelando la operación.
    """
    validation = compute_ecoe_validation(db, ecoe_event)
    current_status = str(ecoe_event.status)
    if target_status not in ALLOWED_STATUS_TRANSITIONS:
        raise ValueError("Estado no permitido")
    if target_status != current_status:
        if target_status not in ALLOWED_STATUS_TRANSITIONS.get(current_status, set()):
            raise ValueError(
                f"Transición de estado no permitida: {current_status} → {target_status}"
            )
        # Readiness gates guard the transition itself; staying in the same
        # state (full-form PUTs) must not re-run them, otherwise an event in
        # ejecucion could never be edited (can_start_live requires publicado).
        if target_status == ECOEStatus.listo_para_pilotaje.value and not validation["can_pilot"]:
            raise ValueError("El ECOE aún no cumple condiciones para pilotaje")
        if target_status == ECOEStatus.publicado.value and not validation["can_publish"]:
            raise ValueError("El ECOE aún no cumple condiciones para publicación")
        if target_status == ECOEStatus.en_ejecucion.value and not validation["can_start_live"]:
            raise ValueError("El ECOE aún no está listo para ejecución real")

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

    if (
        target_status == ECOEStatus.en_ejecucion.value
        and current_status != ECOEStatus.en_ejecucion.value
    ):
        # Al entrar a la ejecución real, cualquier check-in `confirmado` que
        # sobreviva es residuo del pilotaje: ciérralo para que no aparezca
        # como sesión activa ni sume a los conteos de la ejecución.
        residual_checkins = db.scalars(
            select(StationCheckIn).where(
                StationCheckIn.ecoe_event_id == ecoe_event.id,
                StationCheckIn.status == "confirmado",
            )
        ).all()
        for checkin in residual_checkins:
            checkin.status = "cerrado"
            db.add(checkin)

    if target_status == ECOEStatus.cerrado.value and current_status != ECOEStatus.cerrado.value:
        # Closing freezes the event: consolidate results in the same
        # transaction and close every check-in still open, so no submission
        # window survives the closure (the stage gate rejects new records).
        from app.services.results import persist_results

        persist_results(db, ecoe_event.id, commit=False, actor_email=actor_email)
        open_checkins = db.scalars(
            select(StationCheckIn).where(
                StationCheckIn.ecoe_event_id == ecoe_event.id,
                StationCheckIn.status == "confirmado",
            )
        ).all()
        for checkin in open_checkins:
            checkin.status = "cerrado"
            db.add(checkin)

    ecoe_event.status = target_status
    db.add(ecoe_event)
    if commit:
        db.commit()
        db.refresh(ecoe_event)
    return ecoe_event
