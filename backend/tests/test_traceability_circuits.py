"""Traceability expectations are scoped to each student's circuit (M2)."""

from datetime import date

from app.models.entities import ECOEEvent, Station, Student
from app.models.enums import ECOEStatus
from app.services.results import build_traceability_report
from conftest import TestingSessionLocal


def _station(event_id: int, number: int, circuit: str, *, evaluator: bool, form: bool) -> Station:
    return Station(
        ecoe_event_id=event_id,
        station_number=number,
        name=f"Estación {number}",
        station_type="procedimental",
        circuit_name=circuit,
        station_time_minutes=8,
        transition_time_minutes=2,
        expected_outcomes="Resultado",
        student_activity="Actividad",
        pre_entry_instruction="Ingreso",
        evaluator_instruction="Evaluar",
        requires_evaluator=evaluator,
        requires_student_form=form,
        max_score=10,
    )


def _student(event_id: int, number: str, circuit: str) -> Student:
    return Student(
        ecoe_event_id=event_id,
        name=f"Estudiante {number}",
        last_name="Circuito",
        rut=f"30{number}00-{number[-1]}",
        email=f"circ{number}@example.edu",
        ecoe_number=number,
        group_name="G1",
        circuit_name=circuit,
        is_active=True,
    )


def test_expected_counts_follow_each_students_circuit():
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Espejo",
            date=date(2026, 12, 1),
            course_name="Curso",
            school_name="Escuela",
            responsible_teacher="Docente",
            contact_email="docente@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=3,
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=3,
            total_groups=2,
            passing_reference_percent=60,
            status=ECOEStatus.en_ejecucion.value,
        )
        db.add(event)
        db.flush()
        # Circuito A: 2 estaciones con evaluador, 0 con formulario.
        # Circuito B: 1 con evaluador, 1 con formulario (la misma estacion).
        db.add_all([
            _station(event.id, 1, "Circuito A", evaluator=True, form=False),
            _station(event.id, 2, "Circuito A", evaluator=True, form=False),
            _station(event.id, 3, "Circuito B", evaluator=True, form=True),
        ])
        db.add_all([
            _student(event.id, "101", "Circuito A"),
            _student(event.id, "102", "Circuito B"),
            # Circuito sin match con estaciones: fallback al total del evento.
            _student(event.id, "103", "Circuito Fantasma"),
        ])
        db.commit()

        report = build_traceability_report(db, event.id)

    rows = {row["ecoe_number"]: row for row in report["student_traceability"]}
    assert rows["101"]["missing_evaluations"] == 2
    assert rows["101"]["missing_student_submissions"] == 0
    assert rows["102"]["missing_evaluations"] == 1
    assert rows["102"]["missing_student_submissions"] == 1
    # Fallback conservador: exige el total del evento (3 evaluador, 1 form).
    assert rows["103"]["missing_evaluations"] == 3
    assert rows["103"]["missing_student_submissions"] == 1

    summary = report["summary"]
    assert summary["expected_evaluations"] == 2 + 1 + 3
    assert summary["expected_student_submissions"] == 0 + 1 + 1
