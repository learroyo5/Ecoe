"""F0.1 (H03 de la auditoría SaaS): ingreso activo único, con y sin concurrencia."""

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models.entities import Station, StationCheckIn, Student, StudentResponse
from app.models.enums import SessionMode
from conftest import ADMIN, IS_SQLITE, TestingSessionLocal, login
from test_opt20_f2_deadline_and_sweep import CHOICE_FORM, _add_checkin, _build_event


def _confirm(client, ctx: dict, number: str = "001", station_id: int | None = None):
    return client.post("/api/station-checkins/confirm", json={
        "ecoe_event_id": ctx["event_id"],
        "station_id": station_id or ctx["station_id"],
        "ecoe_number": number,
    })


def _active(ctx: dict) -> list[StationCheckIn]:
    with TestingSessionLocal() as db:
        return list(db.scalars(select(StationCheckIn).where(
            StationCheckIn.ecoe_event_id == ctx["event_id"],
            StationCheckIn.status == "confirmado",
        )))


def _add_student(ctx: dict, number: str) -> int:
    with TestingSessionLocal() as db:
        student = Student(
            ecoe_event_id=ctx["event_id"], name=f"Alumno{number}", last_name="X",
            rut=f"c{ctx['event_id']}-{number}", email=f"c{ctx['event_id']}-{number}@e.edu",
            ecoe_number=number, group_name="G1", circuit_name="Circuito A", is_active=True,
        )
        db.add(student)
        db.commit()
        return student.id


def test_confirming_the_same_student_twice_returns_the_same_checkin(auth_client):
    """Doble clic / reintento: ni un segundo ingreso ni una respuesta en blanco."""
    ctx = _build_event()
    first = _confirm(auth_client, ctx)
    second = _confirm(auth_client, ctx)
    assert first.status_code == 200 and second.status_code == 200, second.text
    assert second.json()["checkin_id"] == first.json()["checkin_id"]
    assert len(_active(ctx)) == 1
    with TestingSessionLocal() as db:
        assert db.scalars(select(StudentResponse).where(
            StudentResponse.ecoe_event_id == ctx["event_id"])).all() == []
        assert len(db.scalars(select(StationCheckIn).where(
            StationCheckIn.ecoe_event_id == ctx["event_id"])).all()) == 1


def test_retry_reports_what_is_already_registered(auth_client):
    ctx = _build_event()
    _confirm(auth_client, ctx)
    with TestingSessionLocal() as db:
        db.add(StudentResponse(
            ecoe_event_id=ctx["event_id"], station_id=ctx["station_id"],
            student_id=ctx["student_id"], mode=SessionMode.ejecucion.value,
            answers={"question_1": "SCA"}, locked=True, submission_kind="manual",
        ))
        db.commit()
    again = _confirm(auth_client, ctx)
    assert again.status_code == 200, again.text
    assert again.json()["student_response_exists"] is True
    assert again.json()["evaluator_submission_exists"] is False


def test_database_refuses_two_active_checkins_in_a_station():
    ctx = _build_event()
    other = _add_student(ctx, "002")
    _add_checkin(ctx, minutes_ago=1)
    with pytest.raises(IntegrityError):
        with TestingSessionLocal() as db:
            db.add(StationCheckIn(
                ecoe_event_id=ctx["event_id"], station_id=ctx["station_id"], student_id=other,
                evaluator_email="e@e.edu", evaluator_name="E", status="confirmado",
                mode=SessionMode.ejecucion.value,
            ))
            db.commit()


def test_database_refuses_the_same_student_active_in_two_stations():
    ctx = _build_event()
    with TestingSessionLocal() as db:
        second = Station(
            ecoe_event_id=ctx["event_id"], station_number=2, name="E2",
            station_type="formulario_estudiante", circuit_name="Circuito A",
            station_time_minutes=8, transition_time_minutes=2, expected_outcomes="r",
            student_activity="a", pre_entry_instruction="i", student_station_instruction="d",
            evaluator_instruction="e", requires_evaluator=True, requires_student_form=True,
            max_score=4, student_form_definition=CHOICE_FORM,
        )
        db.add(second)
        db.commit()
        second_id = second.id
    _add_checkin(ctx, minutes_ago=1)
    with pytest.raises(IntegrityError):
        with TestingSessionLocal() as db:
            db.add(StationCheckIn(
                ecoe_event_id=ctx["event_id"], station_id=second_id,
                student_id=ctx["student_id"], evaluator_email="e@e.edu",
                evaluator_name="E", status="confirmado", mode=SessionMode.ejecucion.value,
            ))
            db.commit()


def test_closed_and_annulled_checkins_do_not_count_against_the_invariant():
    ctx = _build_event()
    _add_checkin(ctx, minutes_ago=5, status="cerrado")
    _add_checkin(ctx, minutes_ago=4, status="anulado")
    _add_checkin(ctx, minutes_ago=0)
    assert len(_active(ctx)) == 1


def test_a_surviving_pilot_checkin_is_not_reused_for_the_real_exam(auth_client):
    """Negativo de la idempotencia: mismo estudiante y estación, otro modo."""
    ctx = _build_event()
    with TestingSessionLocal() as db:
        db.add(StationCheckIn(
            ecoe_event_id=ctx["event_id"], station_id=ctx["station_id"],
            student_id=ctx["student_id"], evaluator_email="e@e.edu", evaluator_name="E",
            status="confirmado", mode=SessionMode.pilotaje.value,
        ))
        db.commit()
    response = _confirm(auth_client, ctx)
    assert response.status_code == 200, response.text
    active = _active(ctx)
    assert len(active) == 1 and str(active[0].mode) == SessionMode.ejecucion.value


@pytest.mark.skipif(IS_SQLITE, reason="la carrera real necesita PostgreSQL y conexiones separadas")
def test_simultaneous_confirmations_leave_exactly_one_active_checkin():
    """Dos evaluadores confirman a estudiantes distintos en la MISMA estación a
    la vez, muchas veces. Nunca quedan dos ingresos activos ni un 500."""
    ctx = _build_event()
    _add_student(ctx, "002")
    statuses: list[int] = []
    lock = threading.Lock()

    def worker(number: str, start: threading.Barrier) -> None:
        with TestClient(app) as client:
            login(client, ADMIN)
            start.wait()
            for _ in range(8):
                code = _confirm(client, ctx, number).status_code
                with lock:
                    statuses.append(code)

    barrier = threading.Barrier(2)
    threads = [threading.Thread(target=worker, args=(n, barrier)) for n in ("001", "002")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert 500 not in statuses, statuses
    assert set(statuses) <= {200, 409}, statuses
    assert len(_active(ctx)) == 1
