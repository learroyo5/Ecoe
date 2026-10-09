"""PROC-6 / PROC-7 / PROC-8 (auditoría de proceso 2026-10-09).

- PROC-6: el cierre se bloquea si hay estudiantes con estaciones esperadas sin
  nota; el director puede forzarlo y esas estaciones entran al acta con 0.
- PROC-7: reapertura `cerrado → en_ejecucion` (admin, con motivo, auditada);
  `archivado → borrador` ("Reactivar") deja de existir.
- PROC-8: el acta congela identidad y cobertura.
"""

from datetime import date

from sqlalchemy import select

from app.models.entities import (
    AuditLog,
    ECOEEvent,
    ECOEResult,
    EvaluatorRecord,
    Station,
    StationResult,
    Student,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.results import (
    compute_missing_station_scores,
    compute_results,
    expected_stations_by_student,
)
from conftest import ADMIN, COEDITOR, TestingSessionLocal, login


def _build(*, circuits=("Circuito A",), stations_per_circuit=2, students=1) -> dict:
    """Evento en ejecución con estaciones de evaluador (máx 10) por circuito."""
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Cierre", date=date(2026, 12, 20), course_name="C", school_name="E",
            responsible_teacher="D", contact_email="d@example.edu",
            circuit_mode="paralelo_espejo", total_stations=1, station_time_minutes=8,
            transition_time_minutes=2, total_students=1, total_groups=1,
            passing_reference_percent=60, status=ECOEStatus.en_ejecucion.value,
        )
        db.add(event)
        db.flush()
        station_ids: dict[str, list[int]] = {}
        number = 0
        for circuit in circuits:
            for _ in range(stations_per_circuit):
                number += 1
                station = Station(
                    ecoe_event_id=event.id, station_number=number, name=f"E{number}",
                    station_type="procedimental", circuit_name=circuit,
                    station_time_minutes=8, transition_time_minutes=2,
                    expected_outcomes="r", student_activity="a", pre_entry_instruction="i",
                    student_station_instruction="d", evaluator_instruction="e",
                    requires_evaluator=True, requires_student_form=False, max_score=10,
                )
                db.add(station)
                db.flush()
                station_ids.setdefault(circuit, []).append(station.id)
        student_ids: list[int] = []
        for index in range(students):
            circuit = circuits[index % len(circuits)]
            student = Student(
                ecoe_event_id=event.id, name=f"Alumno{index + 1}", last_name="X",
                rut=f"{event.id}-{index}", email=f"a{event.id}-{index}@e.edu",
                ecoe_number=f"E{index + 1:03d}", group_name="G1", circuit_name=circuit,
                is_active=True,
            )
            db.add(student)
            db.flush()
            student_ids.append(student.id)
        db.commit()
        return {"event_id": event.id, "stations": station_ids, "students": student_ids}


def _score(ctx: dict, student_id: int, station_id: int, obtained: float) -> None:
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=ctx["event_id"], station_id=station_id, student_id=student_id,
            mode=SessionMode.ejecucion.value, evaluator_name="Eval",
            score_obtained=obtained, max_score=10, is_draft=False,
        ))
        db.commit()


def _payload(event_id: int, status: str, **extra) -> dict:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        payload = {
            "name": event.name, "date": str(event.date), "course_name": event.course_name,
            "school_name": event.school_name, "responsible_teacher": event.responsible_teacher,
            "contact_email": event.contact_email, "circuit_mode": event.circuit_mode,
            "station_time_minutes": event.station_time_minutes,
            "transition_time_minutes": event.transition_time_minutes,
            "inter_round_pause_minutes": event.inter_round_pause_minutes,
            "total_groups": event.total_groups,
            "passing_reference_percent": event.passing_reference_percent,
            "status": status,
        }
    payload.update(extra)
    return payload


def _status(event_id: int) -> str:
    with TestingSessionLocal() as db:
        return str(db.get(ECOEEvent, event_id).status)


# ── PROC-6 ────────────────────────────────────────────────────────────


def test_expected_stations_follow_the_students_circuit():
    ctx = _build(circuits=("Circuito A", "Circuito B"), students=2)
    with TestingSessionLocal() as db:
        expected = expected_stations_by_student(db, ctx["event_id"])
    a, b = ctx["students"]
    assert [s.id for s in expected[a]] == ctx["stations"]["Circuito A"]
    assert [s.id for s in expected[b]] == ctx["stations"]["Circuito B"]


def test_close_is_blocked_while_a_student_has_an_unscored_station(auth_client):
    ctx = _build()
    student = ctx["students"][0]
    first, second = ctx["stations"]["Circuito A"]
    _score(ctx, student, first, 10)

    response = auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "cerrado")
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "incomplete_students"
    assert detail["total"] == 1
    assert detail["students"][0]["ecoe_number"] == "E001"
    assert detail["students"][0]["missing_station_numbers"] == [2]
    # Nada se consolidó ni cambió de estado.
    assert _status(ctx["event_id"]) == "en_ejecucion"
    with TestingSessionLocal() as db:
        assert db.scalars(select(ECOEResult).where(
            ECOEResult.ecoe_event_id == ctx["event_id"])).all() == []


def test_close_goes_through_when_everyone_is_complete(auth_client):
    ctx = _build()
    student = ctx["students"][0]
    for station_id in ctx["stations"]["Circuito A"]:
        _score(ctx, student, station_id, 10)
    response = auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "cerrado")
    )
    assert response.status_code == 200, response.text
    with TestingSessionLocal() as db:
        assert db.scalar(select(AuditLog).where(
            AuditLog.action == "force_close_incomplete",
            AuditLog.target_id == str(ctx["event_id"]))) is None


def test_suspending_the_absent_student_unblocks_the_close(auth_client):
    ctx = _build(students=2)
    present, absent = ctx["students"]
    for station_id in ctx["stations"]["Circuito A"]:
        _score(ctx, present, station_id, 10)
    assert auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "cerrado")
    ).status_code == 409
    assert auth_client.patch(
        f"/api/students/{absent}/status", json={"is_active": False}
    ).status_code == 200
    assert auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "cerrado")
    ).status_code == 200


def test_forced_close_scores_missing_stations_as_zero_and_marks_them(auth_client):
    ctx = _build()
    student = ctx["students"][0]
    first, second = ctx["stations"]["Circuito A"]
    _score(ctx, student, first, 10)  # 100 % en una de dos

    # En vivo la nota NO se castiga: la estación aún puede rendirse.
    with TestingSessionLocal() as db:
        live = compute_results(db, ctx["event_id"])[0]
    assert live["percentage"] == 100.0
    assert live["stations_counted"] == 1 and live["stations_expected"] == 2
    assert live["missing_stations"] == [2]

    response = auth_client.put(
        f"/api/ecoe/{ctx['event_id']}",
        json=_payload(ctx["event_id"], "cerrado", force_close_incomplete=True),
    )
    assert response.status_code == 200, response.text

    body = auth_client.get(f"/api/results/{ctx['event_id']}").json()
    assert body["frozen"] is True
    row = body["results"][0]
    assert row["percentage"] == 50.0  # (100 + 0) / 2
    assert row["stations_counted"] == 2 and row["stations_expected"] == 2
    with TestingSessionLocal() as db:
        snaps = {
            snap.station_id: snap
            for snap in db.scalars(select(StationResult).where(
                StationResult.ecoe_event_id == ctx["event_id"])).all()
        }
        assert snaps[first].is_missing is False and snaps[first].percent_score == 100
        assert snaps[second].is_missing is True
        assert (snaps[second].obtained_score, snaps[second].max_score) == (0, 10)
        log = db.scalar(select(AuditLog).where(
            AuditLog.action == "force_close_incomplete",
            AuditLog.target_id == str(ctx["event_id"])))
        assert log.payload["missing_station_scores"] == 1
        assert log.payload["students"][0]["missing_station_numbers"] == [2]


def test_a_real_zero_is_not_reported_as_missing():
    ctx = _build()
    student = ctx["students"][0]
    for station_id in ctx["stations"]["Circuito A"]:
        _score(ctx, student, station_id, 0)
    with TestingSessionLocal() as db:
        assert compute_missing_station_scores(db, ctx["event_id"]) == []


# ── PROC-7 ────────────────────────────────────────────────────────────


def _closed_event(auth_client) -> dict:
    ctx = _build()
    student = ctx["students"][0]
    for station_id in ctx["stations"]["Circuito A"]:
        _score(ctx, student, station_id, 10)
    assert auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "cerrado")
    ).status_code == 200
    return ctx


def test_reopen_requires_a_reason(auth_client):
    ctx = _closed_event(auth_client)
    response = auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "en_ejecucion")
    )
    assert response.status_code == 400
    assert "motivo" in response.json()["detail"]
    assert _status(ctx["event_id"]) == "cerrado"
    with TestingSessionLocal() as db:
        assert db.scalars(select(ECOEResult).where(
            ECOEResult.ecoe_event_id == ctx["event_id"])).all() != []


def test_reopen_invalidates_the_acta_accepts_contingency_and_is_audited(auth_client):
    ctx = _closed_event(auth_client)
    response = auth_client.put(
        f"/api/ecoe/{ctx['event_id']}",
        json=_payload(ctx["event_id"], "en_ejecucion",
                      transition_reason="Apareció una pauta en papel de la estación 2"),
    )
    assert response.status_code == 200, response.text
    assert _status(ctx["event_id"]) == "en_ejecucion"
    body = auth_client.get(f"/api/results/{ctx['event_id']}").json()
    assert body["frozen"] is False
    with TestingSessionLocal() as db:
        assert db.scalars(select(ECOEResult).where(
            ECOEResult.ecoe_event_id == ctx["event_id"])).all() == []
        log = db.scalar(select(AuditLog).where(
            AuditLog.action == "reopen_ecoe", AuditLog.target_id == str(ctx["event_id"])))
        assert log.payload["reason"].startswith("Apareció una pauta")
    # Y se puede volver a cerrar: el acta se regenera.
    assert auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "cerrado")
    ).status_code == 200
    assert auth_client.get(f"/api/results/{ctx['event_id']}").json()["frozen"] is True


def test_coeditor_cannot_reopen_a_closed_event(client, auth_client):
    ctx = _closed_event(auth_client)
    from app.models.entities import ECOEPermission, User
    with TestingSessionLocal() as db:
        coeditor = db.scalar(select(User).where(User.email == COEDITOR[0]))
        db.add(ECOEPermission(
            ecoe_event_id=ctx["event_id"], user_id=coeditor.id, role_code="coeditor_docente"))
        db.commit()
    login(client, COEDITOR)
    response = client.put(
        f"/api/ecoe/{ctx['event_id']}",
        json=_payload(ctx["event_id"], "en_ejecucion",
                      transition_reason="Motivo suficientemente largo"),
    )
    assert response.status_code == 403
    assert _status(ctx["event_id"]) == "cerrado"
    login(client, ADMIN)


def test_archived_event_can_no_longer_be_reactivated(auth_client):
    ctx = _closed_event(auth_client)
    assert auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "archivado")
    ).status_code == 200
    for target in ("borrador", "en_ejecucion", "cerrado"):
        response = auth_client.put(
            f"/api/ecoe/{ctx['event_id']}",
            json=_payload(ctx["event_id"], target, transition_reason="Motivo suficientemente largo"),
        )
        assert response.status_code == 400, (target, response.text)
    assert _status(ctx["event_id"]) == "archivado"


# ── PROC-8 ────────────────────────────────────────────────────────────


def test_acta_keeps_the_identity_it_was_consolidated_with(auth_client):
    ctx = _closed_event(auth_client)
    student_id = ctx["students"][0]
    # Alguien altera la nómina por fuera de la API (o un bug futuro lo permite).
    with TestingSessionLocal() as db:
        student = db.get(Student, student_id)
        student.ecoe_number = "E999"
        student.name = "Otro"
        db.commit()
        snap = db.scalar(select(ECOEResult).where(ECOEResult.ecoe_event_id == ctx["event_id"]))
        assert (snap.ecoe_number, snap.student_name, snap.student_rut) == (
            "E001", "Alumno1 X", f"{ctx['event_id']}-0")
    row = auth_client.get(f"/api/results/{ctx['event_id']}").json()["results"][0]
    assert row["ecoe_number"] == "E001"
    assert row["student_name"] == "Alumno1 X"
