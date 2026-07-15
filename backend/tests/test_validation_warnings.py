"""Operational warnings the Validation screen must surface before the exam."""

from datetime import date

from app.models.entities import ECOEEvent, StaffAssignment, Station
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
