"""F0.2 (H05 de la auditoría SaaS): reintentos de envío y orden de borradores."""

from sqlalchemy import select

from app.models.entities import (
    EvaluatorRecord,
    Station,
    StationCheckIn,
    StationResponseDraft,
    StudentResponse,
)
from app.services.drafts import upsert_checkin_draft
from app.services.kiosk import issue_kiosk_token
from conftest import TestingSessionLocal
from test_opt20_f2_deadline_and_sweep import _add_checkin, _add_live_session, _build_event


def _kiosk(ctx: dict) -> dict:
    with TestingSessionLocal() as db:
        token = issue_kiosk_token(
            db, db.get(Station, ctx["station_id"]), issued_by_email="t@e.edu")["token"]
        db.commit()
    return {"X-Kiosk-Token": token}


def _responses(ctx: dict) -> list[StudentResponse]:
    with TestingSessionLocal() as db:
        return list(db.scalars(select(StudentResponse).where(
            StudentResponse.ecoe_event_id == ctx["event_id"])))


# ── Envíos ────────────────────────────────────────────────────────────


def test_kiosk_retry_of_the_same_answers_is_a_success_not_an_error(client):
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    headers = _kiosk(ctx)
    body = {"checkin_id": checkin_id, "answers": {"question_1": "SCA"}}

    first = client.post("/api/kiosk/submit", headers=headers, json=body)
    retry = client.post("/api/kiosk/submit", headers=headers, json=body)
    assert first.status_code == 200 and retry.status_code == 200, retry.text
    assert retry.json()["response_id"] == first.json()["response_id"]
    assert retry.json()["already_saved"] is True
    assert len(_responses(ctx)) == 1


def test_kiosk_retry_succeeds_even_after_the_window_expired(client):
    """Se perdió la respuesta HTTP, la fase venció y la tablet reintenta."""
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    headers = _kiosk(ctx)
    body = {"checkin_id": checkin_id, "answers": {"question_1": "SCA"}}
    assert client.post("/api/kiosk/submit", headers=headers, json=body).status_code == 200
    with TestingSessionLocal() as db:  # la ventana por check-in ya pasó
        checkin = db.get(StationCheckIn, checkin_id)
        checkin.confirmed_at = checkin.confirmed_at.replace(year=checkin.confirmed_at.year - 1)
        db.commit()
    retry = client.post("/api/kiosk/submit", headers=headers, json=body)
    assert retry.status_code == 200, retry.text
    assert retry.json()["already_saved"] is True


def test_a_different_second_submission_is_still_rejected(client):
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    headers = _kiosk(ctx)
    client.post("/api/kiosk/submit", headers=headers,
                json={"checkin_id": checkin_id, "answers": {"question_1": "TEP"}})
    changed = client.post("/api/kiosk/submit", headers=headers,
                          json={"checkin_id": checkin_id, "answers": {"question_1": "SCA"}})
    assert changed.status_code == 400
    assert _responses(ctx)[0].answers == {"question_1": "TEP"}


def test_student_retry_of_the_same_answers_is_a_success(auth_client):
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    body = {
        "checkin_id": checkin_id, "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"], "student_id": ctx["student_id"],
        "answers": {"question_1": "SCA"},
    }
    first = auth_client.post("/api/student/submit", json=body)
    retry = auth_client.post("/api/student/submit", json=body)
    assert first.status_code == 200 and retry.status_code == 200, retry.text
    assert retry.json()["already_saved"] is True
    assert len(_responses(ctx)) == 1


def _evaluation_body(ctx: dict, checkin_id: int, score: float) -> dict:
    return {
        "checkin_id": checkin_id, "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"], "student_id": ctx["student_id"],
        "evaluator_name": "Eval", "score_obtained": score, "max_score": 4,
        "observation": "ok", "answers": {},
    }


def test_evaluator_retry_is_a_success_and_a_changed_score_is_not(auth_client):
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    first = auth_client.post("/api/evaluator/submit", json=_evaluation_body(ctx, checkin_id, 3))
    retry = auth_client.post("/api/evaluator/submit", json=_evaluation_body(ctx, checkin_id, 3))
    changed = auth_client.post("/api/evaluator/submit", json=_evaluation_body(ctx, checkin_id, 4))
    assert first.status_code == 200 and retry.status_code == 200, retry.text
    assert retry.json()["already_saved"] is True
    assert retry.json()["record_id"] == first.json()["record_id"]
    assert changed.status_code == 400
    with TestingSessionLocal() as db:
        records = db.scalars(select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == ctx["event_id"])).all()
        assert [r.score_obtained for r in records] == [3]


# ── Borradores ────────────────────────────────────────────────────────


def _draft(ctx: dict) -> StationResponseDraft | None:
    with TestingSessionLocal() as db:
        return db.scalar(select(StationResponseDraft).where(
            StationResponseDraft.ecoe_event_id == ctx["event_id"]))


def test_a_late_older_draft_does_not_overwrite_a_newer_one(client):
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    headers = _kiosk(ctx)

    def push(seq: int, answer: str):
        return client.put("/api/kiosk/draft", headers=headers, json={
            "checkin_id": checkin_id, "answers": {"question_1": answer}, "client_seq": seq,
        })

    assert push(10, "TEP").json()["applied"] is True
    assert push(20, "SCA").json()["applied"] is True
    late = push(15, "RGE")  # salió antes, llegó después
    assert late.status_code == 200 and late.json()["applied"] is False
    assert push(20, "RGE").json()["applied"] is False  # reintento del mismo
    assert _draft(ctx).answers == {"question_1": "SCA"}


def test_drafts_without_sequence_keep_last_write_wins(client):
    """Compatibilidad: un cliente sin `client_seq` se comporta como antes."""
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    headers = _kiosk(ctx)
    for answer in ("TEP", "SCA"):
        response = client.put("/api/kiosk/draft", headers=headers, json={
            "checkin_id": checkin_id, "answers": {"question_1": answer},
        })
        assert response.json()["applied"] is True
    assert _draft(ctx).answers == {"question_1": "SCA"}


def test_the_sweep_finalizes_the_newest_draft(client):
    from app.models.entities import ECOEEvent
    from app.services.live_sweep import sweep_expired_phases

    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    checkin_id = _add_checkin(ctx, minutes_ago=15)
    with TestingSessionLocal() as db:
        checkin = db.get(StationCheckIn, checkin_id)
        upsert_checkin_draft(db, checkin, {"question_1": "SCA"}, client_seq=20)
        upsert_checkin_draft(db, checkin, {"question_1": "TEP"}, client_seq=5)
        db.commit()
        sweep_expired_phases(db, db.get(ECOEEvent, ctx["event_id"]))
    saved = _responses(ctx)
    assert len(saved) == 1 and saved[0].answers == {"question_1": "SCA"}
    assert saved[0].score_obtained == 4
