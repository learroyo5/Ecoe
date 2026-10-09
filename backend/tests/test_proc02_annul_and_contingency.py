"""PROC-2 / PROC-3 (auditoría de proceso 2026-10-09).

- PROC-3: anular un ingreso confirmado por error; el mismo estudiante no queda
  confirmado en dos estaciones de la misma rotación sin que alguien lo decida.
- PROC-2: contingencia sustituye una respuesta autoenviada y rectifica una
  evaluación enviada, siempre con rastro en la auditoría.
"""

from sqlalchemy import select

from app.models.entities import (
    AuditLog,
    EvaluatorRecord,
    Station,
    StationCheckIn,
    StationResponseDraft,
    StudentResponse,
)
from app.models.enums import SessionMode
from conftest import ADMIN, EVALUATOR, TestingSessionLocal, login
from test_opt20_f2_deadline_and_sweep import (
    CHOICE_FORM,
    _add_checkin,
    _add_live_session,
    _build_event,
)


def _second_station(ctx: dict) -> int:
    with TestingSessionLocal() as db:
        station = Station(
            ecoe_event_id=ctx["event_id"], station_number=2, name="Estación 2",
            station_type="formulario_estudiante", circuit_name="Circuito A",
            station_time_minutes=8, transition_time_minutes=2,
            expected_outcomes="r", student_activity="a", pre_entry_instruction="i",
            student_station_instruction="d", evaluator_instruction="e",
            requires_evaluator=True, requires_student_form=True, max_score=4,
            student_form_definition=CHOICE_FORM,
        )
        db.add(station)
        db.commit()
        return station.id


def _confirm(client, ctx: dict, station_id: int, **extra):
    return client.post("/api/station-checkins/confirm", json={
        "ecoe_event_id": ctx["event_id"], "station_id": station_id,
        "ecoe_number": "001", **extra,
    })


def _statuses(ctx: dict) -> dict[int, list[str]]:
    with TestingSessionLocal() as db:
        out: dict[int, list[str]] = {}
        for item in db.scalars(
            select(StationCheckIn).where(StationCheckIn.ecoe_event_id == ctx["event_id"])
            .order_by(StationCheckIn.id)
        ):
            out.setdefault(item.station_id, []).append(item.status)
        return out


# ── PROC-3 ────────────────────────────────────────────────────────────


def test_same_student_in_two_stations_of_the_same_rotation_is_flagged(client):
    ctx = _build_event()
    other = _second_station(ctx)
    _add_live_session(ctx, status="running", remaining=480, started_secs_ago=30)
    login(client, ADMIN)
    assert _confirm(client, ctx, ctx["station_id"]).status_code == 200

    response = _confirm(client, ctx, other)
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "student_in_other_station"
    assert detail["station_number"] == 1
    # Nada cambió: sigue confirmado sólo en la estación original.
    assert _statuses(ctx) == {ctx["station_id"]: ["confirmado"]}


def test_moving_the_student_annuls_the_wrong_checkin_without_a_blank_response(client):
    ctx = _build_event()
    other = _second_station(ctx)
    _add_live_session(ctx, status="running", remaining=480, started_secs_ago=30)
    login(client, ADMIN)
    _confirm(client, ctx, ctx["station_id"])

    response = _confirm(client, ctx, other, move_from_other_station=True)
    assert response.status_code == 200, response.text
    assert _statuses(ctx) == {ctx["station_id"]: ["anulado"], other: ["confirmado"]}
    with TestingSessionLocal() as db:
        assert db.scalars(select(StudentResponse).where(
            StudentResponse.ecoe_event_id == ctx["event_id"])).all() == []
        assert db.scalar(select(AuditLog).where(AuditLog.action == "annul_station_checkin")) is not None


def test_checkin_from_a_previous_rotation_is_closed_and_keeps_its_draft(client):
    """La rotación normal no dispara el aviso: el ingreso de la estación
    anterior se cierra solo y conserva lo que el estudiante escribió."""
    ctx = _build_event()
    other = _second_station(ctx)
    _add_live_session(ctx, status="running", remaining=480, started_secs_ago=30)
    previous = _add_checkin(ctx, minutes_ago=12)  # rotación anterior
    with TestingSessionLocal() as db:
        db.add(StationResponseDraft(
            checkin_id=previous, ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"], student_id=ctx["student_id"],
            answers={"question_1": "SCA"},
        ))
        db.commit()
    login(client, ADMIN)

    assert _confirm(client, ctx, other).status_code == 200
    assert _statuses(ctx) == {ctx["station_id"]: ["cerrado"], other: ["confirmado"]}
    with TestingSessionLocal() as db:
        saved = db.scalars(select(StudentResponse).where(
            StudentResponse.ecoe_event_id == ctx["event_id"])).all()
        assert [(r.station_id, r.answers) for r in saved] == [
            (ctx["station_id"], {"question_1": "SCA"})
        ]


def test_annul_checkin_removes_it_from_the_station_and_from_traceability(client):
    ctx = _build_event()
    login(client, ADMIN)
    checkin_id = _confirm(client, ctx, ctx["station_id"]).json()["checkin_id"]

    response = client.post(f"/api/station-checkins/{checkin_id}/annul")
    assert response.status_code == 200, response.text
    assert _statuses(ctx) == {ctx["station_id"]: ["anulado"]}
    context = client.get(f"/api/evaluator/context/{ctx['event_id']}").json()
    assert context["active_checkin"] is None
    trace = client.get(f"/api/results/{ctx['event_id']}").json()["student_traceability"]
    assert trace[0]["checkins_confirmed"] == 0
    # Anular dos veces no es posible.
    assert client.post(f"/api/station-checkins/{checkin_id}/annul").status_code == 409


def test_annul_is_refused_once_there_is_a_record(client):
    ctx = _build_event()
    login(client, ADMIN)
    checkin_id = _confirm(client, ctx, ctx["station_id"]).json()["checkin_id"]
    with TestingSessionLocal() as db:
        db.add(StudentResponse(
            ecoe_event_id=ctx["event_id"], station_id=ctx["station_id"],
            student_id=ctx["student_id"], mode=SessionMode.ejecucion.value,
            answers={"question_1": "TEP"}, locked=True, submission_kind="manual",
        ))
        db.commit()

    response = client.post(f"/api/station-checkins/{checkin_id}/annul")
    assert response.status_code == 409
    assert _statuses(ctx) == {ctx["station_id"]: ["confirmado"]}


def test_evaluator_cannot_annul_a_checkin_of_another_station(client):
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    login(client, EVALUATOR)  # eval1 no tiene asignación en este evento
    response = client.post(f"/api/station-checkins/{checkin_id}/annul")
    assert response.status_code == 403
    assert _statuses(ctx) == {ctx["station_id"]: ["confirmado"]}


def test_annulled_checkin_does_not_enable_contingency(client):
    ctx = _build_event()
    login(client, ADMIN)
    checkin_id = _confirm(client, ctx, ctx["station_id"]).json()["checkin_id"]
    client.post(f"/api/station-checkins/{checkin_id}/annul")
    response = client.post("/api/contingency/student-response", json={
        "ecoe_event_id": ctx["event_id"], "station_id": ctx["station_id"],
        "student_id": ctx["student_id"], "answers": {"question_1": "SCA"},
    })
    assert response.status_code == 400
    assert "check-in" in response.json()["detail"]


# ── PROC-2 ────────────────────────────────────────────────────────────


def _contingency_response(client, ctx: dict, answers: dict):
    return client.post("/api/contingency/student-response", json={
        "ecoe_event_id": ctx["event_id"], "station_id": ctx["station_id"],
        "student_id": ctx["student_id"], "answers": answers,
    })


def test_contingency_replaces_a_blank_auto_response_and_regrades(client):
    ctx = _build_event()
    _add_checkin(ctx, minutes_ago=15, status="cerrado")
    with TestingSessionLocal() as db:
        db.add(StudentResponse(
            ecoe_event_id=ctx["event_id"], station_id=ctx["station_id"],
            student_id=ctx["student_id"], mode=SessionMode.ejecucion.value,
            answers={}, locked=True, submission_kind="auto",
            score_obtained=0, max_score=4, graded_by_email="auto",
        ))
        db.commit()
    login(client, ADMIN)

    response = _contingency_response(client, ctx, {"question_1": "SCA"})
    assert response.status_code == 200, response.text
    assert response.json()["replaced_auto"] is True
    with TestingSessionLocal() as db:
        rows = db.scalars(select(StudentResponse).where(
            StudentResponse.ecoe_event_id == ctx["event_id"])).all()
        assert len(rows) == 1
        assert rows[0].answers == {"question_1": "SCA"}
        assert rows[0].score_obtained == 4
        assert rows[0].submission_kind == "contingency"
        assert rows[0].by_contingency is True
        log = db.scalar(select(AuditLog).where(
            AuditLog.action == "replace_auto_student_response_contingency",
            AuditLog.target_id == str(rows[0].id)))
        assert log.payload["previous"]["score_obtained"] == 0
        assert log.payload["previous"]["submission_kind"] == "auto"


def test_contingency_never_replaces_a_deliberate_student_submission(client):
    ctx = _build_event()
    _add_checkin(ctx, minutes_ago=15, status="cerrado")
    with TestingSessionLocal() as db:
        db.add(StudentResponse(
            ecoe_event_id=ctx["event_id"], station_id=ctx["station_id"],
            student_id=ctx["student_id"], mode=SessionMode.ejecucion.value,
            answers={"question_1": "TEP"}, locked=True, submission_kind="manual",
            score_obtained=0, max_score=4,
        ))
        db.commit()
    login(client, ADMIN)

    assert _contingency_response(client, ctx, {"question_1": "SCA"}).status_code == 400
    with TestingSessionLocal() as db:
        row = db.scalar(select(StudentResponse).where(
            StudentResponse.ecoe_event_id == ctx["event_id"]))
        assert row.answers == {"question_1": "TEP"}
        assert row.submission_kind == "manual"


def _rectify(client, ctx: dict, **overrides):
    payload = {
        "ecoe_event_id": ctx["event_id"], "station_id": ctx["station_id"],
        "student_id": ctx["student_id"], "evaluator_name": "Coordinación",
        "score_obtained": 3, "observation": "corregido",
        "reason": "Puntaje mal digitado por el evaluador",
    }
    payload.update(overrides)
    return client.post("/api/contingency/evaluator-record/rectify", json=payload)


def _add_evaluation(ctx: dict, *, is_draft: bool = False) -> None:
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=ctx["event_id"], station_id=ctx["station_id"],
            student_id=ctx["student_id"], mode=SessionMode.ejecucion.value,
            evaluator_name="Eval", score_obtained=1, max_score=4,
            is_draft=is_draft, submission_kind="manual",
        ))
        db.commit()


def test_rectify_updates_the_record_and_audits_the_previous_value(client):
    ctx = _build_event()
    _add_checkin(ctx, minutes_ago=15, status="cerrado")
    _add_evaluation(ctx)
    login(client, ADMIN)

    response = _rectify(client, ctx)
    assert response.status_code == 200, response.text
    with TestingSessionLocal() as db:
        record = db.scalar(select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == ctx["event_id"]))
        assert record.score_obtained == 3
        assert record.submission_kind == "rectified"
        assert record.by_contingency is True
        log = db.scalar(select(AuditLog).where(
            AuditLog.action == "rectify_evaluation_contingency",
            AuditLog.target_id == str(record.id)))
        assert log.payload["previous"]["score_obtained"] == 1
        assert log.payload["reason"].startswith("Puntaje mal digitado")


def test_rectify_requires_a_reason_a_valid_score_and_an_existing_record(client):
    ctx = _build_event()
    _add_checkin(ctx, minutes_ago=15, status="cerrado")
    login(client, ADMIN)
    # Sin evaluación enviada no hay nada que rectificar.
    assert _rectify(client, ctx).status_code == 404
    _add_evaluation(ctx)
    assert _rectify(client, ctx, reason="corto").status_code == 422
    assert _rectify(client, ctx, score_obtained=99).status_code == 400
    with TestingSessionLocal() as db:
        record = db.scalar(select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == ctx["event_id"]))
        assert record.score_obtained == 1


def test_rectify_is_only_for_contingency_roles(client):
    ctx = _build_event()
    _add_checkin(ctx, minutes_ago=15, status="cerrado")
    _add_evaluation(ctx)
    login(client, EVALUATOR)
    assert _rectify(client, ctx).status_code == 403
