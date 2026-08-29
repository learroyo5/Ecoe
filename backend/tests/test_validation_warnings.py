"""Operational warnings the Validation screen must surface before the exam."""

from datetime import date

from app.models.entities import (
    ECOEEvent,
    LiveSession,
    PilotRun,
    StaffAssignment,
    Station,
    Student,
)
from app.models.enums import ECOEStatus, RoleCode
from app.services.validation import compute_ecoe_validation
from conftest import TestingSessionLocal


def _build_event(db, *, form_questions: list[dict]) -> tuple[ECOEEvent, Station]:
    event = ECOEEvent(
        name="Advertencias",
        date=date(2026, 12, 20),
        course_name="Curso",
        school_name="Escuela",
        responsible_teacher="Docente",
        contact_email="docente@example.edu",
        circuit_mode="paralelo_espejo",
        total_stations=1,
        station_time_minutes=8,
        transition_time_minutes=2,
        total_students=0,
        total_groups=1,
        passing_reference_percent=60,
        status=ECOEStatus.en_configuracion.value,
    )
    db.add(event)
    db.flush()
    station = Station(
        ecoe_event_id=event.id,
        station_number=1,
        name="Estacion",
        station_type="procedimental",
        circuit_name="Circuito A",
        station_time_minutes=8,
        transition_time_minutes=2,
        expected_outcomes="Resultado",
        student_activity="Actividad",
        pre_entry_instruction="Ingreso",
        student_station_instruction="Dentro",
        evaluator_instruction="Evaluar",
        requires_evaluator=True,
        requires_student_form=bool(form_questions),
        max_score=10,
        student_form_definition={"questions": form_questions} if form_questions else {},
    )
    db.add(station)
    db.flush()
    return event, station


def test_warns_when_assigned_evaluator_has_no_active_account():
    with TestingSessionLocal() as db:
        event, station = _build_event(db, form_questions=[])
        db.add(StaffAssignment(
            ecoe_event_id=event.id,
            name="Sin", last_name="Cuenta",
            email="fantasma@example.edu",
            role_code=RoleCode.evaluador.value,
            station_ids=[station.id],
        ))
        db.commit()
        validation = compute_ecoe_validation(db, event)
    assert any(
        "sin cuenta de usuario activa" in warning and "fantasma@example.edu" in warning
        for warning in validation["warnings"]
    )


def test_no_account_warning_for_seeded_evaluator_with_account():
    with TestingSessionLocal() as db:
        event, station = _build_event(db, form_questions=[])
        db.add(StaffAssignment(
            ecoe_event_id=event.id,
            name="Camila", last_name="Soto",
            email="eval1@ecoe.cl",  # cuenta sembrada y activa
            role_code=RoleCode.evaluador.value,
            station_ids=[station.id],
        ))
        db.commit()
        validation = compute_ecoe_validation(db, event)
    assert not any("sin cuenta de usuario activa" in w for w in validation["warnings"])


def test_warns_when_evaluator_assigned_without_primary_station():
    """OPT-5: el alta de evaluador sin estación es válida al invitar; la
    compuerta de publicación debe advertirlo para que no pase silenciosa."""
    with TestingSessionLocal() as db:
        event, _station = _build_event(db, form_questions=[])
        db.add(StaffAssignment(
            ecoe_event_id=event.id,
            name="Sin", last_name="Estacion",
            email="sinestacion@example.edu",
            role_code=RoleCode.evaluador.value,
            station_ids=[],
        ))
        db.commit()
        validation = compute_ecoe_validation(db, event)
    assert any(
        "sin estación principal asignada" in warning and "sinestacion@example.edu" in warning
        for warning in validation["warnings"]
    )


def test_no_station_warning_for_evaluator_with_primary_station():
    with TestingSessionLocal() as db:
        event, station = _build_event(db, form_questions=[])
        db.add(StaffAssignment(
            ecoe_event_id=event.id,
            name="Con", last_name="Estacion",
            email="conestacion@example.edu",
            role_code=RoleCode.evaluador.value,
            station_ids=[station.id],
        ))
        db.commit()
        validation = compute_ecoe_validation(db, event)
    assert not any("sin estación principal asignada" in w for w in validation["warnings"])


def test_warns_when_form_has_questions_but_no_points():
    with TestingSessionLocal() as db:
        event, _station = _build_event(db, form_questions=[
            {"type": "single_choice", "label": "P1", "options": ["A", "B"]},
        ])
        db.commit()
        validation = compute_ecoe_validation(db, event)
    assert any("formulario sin puntaje definido" in w for w in validation["warnings"])


def test_scored_form_does_not_warn():
    with TestingSessionLocal() as db:
        event, _station = _build_event(db, form_questions=[
            {"type": "single_choice", "label": "P1", "options": ["A", "B"],
             "points": 5, "correct_option": "A"},
        ])
        db.commit()
        validation = compute_ecoe_validation(db, event)
    assert not any("formulario sin puntaje definido" in w for w in validation["warnings"])


# ── OPT-4: blocker fantasma "No existe sesión en vivo" antes de publicar ──

_LIVE_SESSION_BLOCKER = "No existe una sesión en vivo creada para la ejecución real."


def _build_publishable_event(db, *, status: str) -> ECOEEvent:
    """Evento con una estación mínima completa y un pilotaje: can_publish True."""
    event = ECOEEvent(
        name="Publicable",
        date=date(2026, 12, 21),
        course_name="Curso",
        school_name="Escuela",
        responsible_teacher="Docente",
        contact_email="docente@example.edu",
        circuit_mode="paralelo_espejo",
        total_stations=1,
        station_time_minutes=8,
        transition_time_minutes=2,
        total_students=1,
        total_groups=1,
        passing_reference_percent=60,
        status=status,
    )
    db.add(event)
    db.flush()
    db.add(Station(
        ecoe_event_id=event.id,
        station_number=1,
        name="Estacion completa",
        station_type="procedimental",
        circuit_name="Circuito A",
        station_time_minutes=8,
        transition_time_minutes=2,
        expected_outcomes="Resultado",
        student_activity="Actividad",
        pre_entry_instruction="Ingreso",
        student_station_instruction="Dentro",
        evaluator_instruction="",
        requires_evaluator=False,
        requires_student_form=False,
        requires_deferred_grading=False,
        max_score=10,
        student_form_definition={},
    ))
    db.add(PilotRun(ecoe_event_id=event.id, name="Pilotaje 1", scope="circuito_completo"))
    db.add(Student(
        ecoe_event_id=event.id,
        name="Alumna", last_name="Activa",
        rut=f"55{event.id}00-1",
        email=f"pub{event.id}@example.edu",
        ecoe_number="001", group_name="G1", circuit_name="Circuito A",
        is_active=True,
    ))
    db.flush()
    return event


def test_no_phantom_live_session_blocker_before_publish():
    with TestingSessionLocal() as db:
        event = _build_publishable_event(db, status=ECOEStatus.pilotaje_validado.value)
        db.commit()
        validation = compute_ecoe_validation(db, event)
    assert validation["can_publish"] is True
    assert _LIVE_SESSION_BLOCKER not in validation["blockers"]
    assert validation["blockers"] == []


def test_can_start_live_still_requires_live_session():
    with TestingSessionLocal() as db:
        event = _build_publishable_event(db, status=ECOEStatus.publicado.value)
        db.commit()
        validation = compute_ecoe_validation(db, event)
    # Publicado sin LiveSession: el gate real de la ejecución sigue cerrado
    # y AHORA sí se reporta el faltante (no antes de publicar).
    assert validation["can_start_live"] is False
    live_check = next(c for c in validation["live_checks"] if c["label"] == "Sesión en vivo creada")
    assert live_check["ok"] is False
    assert _LIVE_SESSION_BLOCKER in validation["blockers"]


def test_live_session_blocker_clears_once_session_exists():
    with TestingSessionLocal() as db:
        event = _build_publishable_event(db, status=ECOEStatus.publicado.value)
        db.add(LiveSession(ecoe_event_id=event.id))
        db.commit()
        validation = compute_ecoe_validation(db, event)
    assert _LIVE_SESSION_BLOCKER not in validation["blockers"]
    assert validation["can_start_live"] is True
