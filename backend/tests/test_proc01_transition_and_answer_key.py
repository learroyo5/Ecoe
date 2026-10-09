"""PROC-1 / PROC-4 / PROC-19 / PROC-22 (auditoría de proceso 2026-10-09).

- PROC-1: un check-in confirmado durante la transición (o la pausa entre
  rondas) pertenece a la próxima fase de estación; el barrido no lo autoenvía.
- PROC-22: confirmar al siguiente estudiante conserva lo que escribió el anterior.
- PROC-4: la clave de respuestas no sale hacia el kiosco ni el estudiante.
- PROC-19: los medios "ambos" también llegan a la pantalla del estudiante.
"""

from datetime import timedelta

from sqlalchemy import select

from app.models.entities import (
    LiveSession,
    MediaAsset,
    Station,
    StationCheckIn,
    StationResponseDraft,
    Student,
    StudentResponse,
)
from app.models.enums import SessionMode
from app.services.kiosk import issue_kiosk_token
from app.services.live_sweep import sweep_expired_phases
from app.models.entities import ECOEEvent
from app.utils.helpers import public_form_definition
from conftest import ADMIN, STUDENT, TestingSessionLocal, login
from test_opt20_f2_deadline_and_sweep import (
    _add_checkin,
    _add_live_session,
    _build_event,
    _deadline,
    _utcnow_naive,
)


def _sweep(ctx: dict, **kwargs) -> dict:
    with TestingSessionLocal() as db:
        return sweep_expired_phases(db, db.get(ECOEEvent, ctx["event_id"]), **kwargs)


def _responses(ctx: dict) -> list[StudentResponse]:
    with TestingSessionLocal() as db:
        return list(db.scalars(
            select(StudentResponse).where(StudentResponse.ecoe_event_id == ctx["event_id"])
        ))


# ── PROC-1 ────────────────────────────────────────────────────────────


def test_checkin_during_transition_gets_the_next_station_phase():
    ctx = _build_event()
    # Transición de 120 s iniciada hace 40 s; el estudiante se confirma ahora.
    _add_live_session(ctx, status="transition", remaining=120, started_secs_ago=40)
    checkin_id = _add_checkin(ctx, minutes_ago=0)

    deadline = _deadline(ctx, checkin_id)
    # Fin de la próxima fase: quedan 80 s de transición + 480 s de estación.
    expected = _utcnow_naive() + timedelta(seconds=80 + 480)
    assert abs((deadline - expected).total_seconds()) < 5

    evaluator_deadline = _deadline(ctx, checkin_id, for_evaluator=True)
    assert abs((evaluator_deadline - deadline).total_seconds() - 120) < 1


def test_sweep_does_not_blank_a_student_confirmed_during_transition():
    ctx = _build_event()
    # 60 s dentro de la transición: ya pasó la gracia de 30 s del deadline viejo.
    _add_live_session(ctx, status="transition", remaining=120, started_secs_ago=60)
    checkin_id = _add_checkin(ctx, minutes_ago=0.25)

    assert _sweep(ctx) == {"auto_responses": 0, "closed_checkins": 0}
    assert _responses(ctx) == []
    with TestingSessionLocal() as db:
        assert db.get(StationCheckIn, checkin_id).status == "confirmado"


def test_buzzer_does_not_blank_a_student_confirmed_during_transition():
    ctx = _build_event()
    _add_live_session(ctx, status="transition", remaining=120, started_secs_ago=60)
    checkin_id = _add_checkin(ctx, minutes_ago=0.25)

    assert _sweep(ctx, force=True) == {"auto_responses": 0, "closed_checkins": 0}
    with TestingSessionLocal() as db:
        assert db.get(StationCheckIn, checkin_id).status == "confirmado"


def test_checkin_during_round_pause_gets_the_next_station_phase():
    ctx = _build_event()
    _add_live_session(ctx, status="round_pause", remaining=300, started_secs_ago=100)
    checkin_id = _add_checkin(ctx, minutes_ago=0)

    deadline = _deadline(ctx, checkin_id)
    expected = _utcnow_naive() + timedelta(seconds=200 + 480)
    assert abs((deadline - expected).total_seconds()) < 5
    assert _sweep(ctx) == {"auto_responses": 0, "closed_checkins": 0}


def test_previous_occupant_is_still_swept_during_transition():
    """Negativo: quien venía de la fase anterior sí se cierra al vencer."""
    ctx = _build_event()
    _add_live_session(ctx, status="transition", remaining=120, started_secs_ago=60)
    # Confirmado 5 min atrás: antes de que empezara la transición.
    checkin_id = _add_checkin(ctx, minutes_ago=5)

    assert _sweep(ctx) == {"auto_responses": 1, "closed_checkins": 1}
    with TestingSessionLocal() as db:
        assert db.get(StationCheckIn, checkin_id).status == "cerrado"


def test_transition_checkin_expires_normally_once_its_own_phase_ends():
    """Negativo: la protección no es indefinida. Ya en `running`, el mismo
    check-in vence con la fase como cualquier otro."""
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    _add_checkin(ctx, minutes_ago=12)

    assert _sweep(ctx) == {"auto_responses": 1, "closed_checkins": 1}


# ── PROC-22 ───────────────────────────────────────────────────────────


def test_confirming_next_student_keeps_previous_students_draft(client):
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=480, started_secs_ago=10)
    previous = _add_checkin(ctx, minutes_ago=1)
    with TestingSessionLocal() as db:
        db.add(StationResponseDraft(
            checkin_id=previous,
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            answers={"question_1": "SCA"},
        ))
        db.add(Student(
            ecoe_event_id=ctx["event_id"], name="Siguiente", last_name="X",
            rut=f"77{ctx['event_id']}-7", email=f"sig{ctx['event_id']}@e.edu",
            ecoe_number="002", group_name="G1", circuit_name="Circuito A",
            is_active=True,
        ))
        db.commit()

    login(client, ADMIN)
    response = client.post("/api/station-checkins/confirm", json={
        "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"],
        "ecoe_number": "002",
    })
    assert response.status_code == 200, response.text

    saved = _responses(ctx)
    assert len(saved) == 1
    assert saved[0].student_id == ctx["student_id"]
    assert saved[0].answers == {"question_1": "SCA"}
    assert saved[0].submission_kind == "auto"
    assert saved[0].score_obtained == 4
    with TestingSessionLocal() as db:
        assert db.get(StationCheckIn, previous).status == "cerrado"


# ── PROC-4 ────────────────────────────────────────────────────────────


def test_public_form_definition_strips_only_the_answer_key():
    form = {
        "title": "t",
        "questions": [
            {"type": "single_choice", "label": "a", "options": ["x", "y"], "points": 4, "correct_option": "x"},
            {"type": "multiple_choice", "label": "b", "options": ["x", "y"], "correct_options": ["x"]},
            {"type": "short_text", "label": "c", "points": 2},
        ],
    }
    public = public_form_definition(form)
    assert public["title"] == "t"
    assert [q["label"] for q in public["questions"]] == ["a", "b", "c"]
    assert public["questions"][0]["options"] == ["x", "y"]
    assert public["questions"][0]["points"] == 4
    assert "correct" not in str(public)
    # No muta el original: la autocorrección sigue necesitando la clave.
    assert form["questions"][0]["correct_option"] == "x"
    assert public_form_definition(None) is None


def test_kiosk_context_never_exposes_the_answer_key(client):
    ctx = _build_event()
    _add_checkin(ctx, minutes_ago=0)
    with TestingSessionLocal() as db:
        token = issue_kiosk_token(
            db, db.get(Station, ctx["station_id"]), issued_by_email="t@e.edu"
        )["token"]
        db.commit()

    response = client.get("/api/kiosk/context", headers={"X-Kiosk-Token": token})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["active"]["student_form_definition"]["questions"][0]["options"] == ["SCA", "TEP", "RGE"]
    assert "correct_option" not in response.text


def test_student_access_never_exposes_the_answer_key_and_sees_shared_media(client):
    ctx = _build_event()
    with TestingSessionLocal() as db:
        student = db.get(Student, ctx["student_id"])
        student.email = STUDENT[0]
        db.add(student)
        db.add(MediaAsset(
            station_id=ctx["station_id"], filename="ecg.png", original_name="ecg.png", file_path="/tmp/ecg.png",
            content_type="image/png", target_viewer="ambos",
        ))
        db.add(MediaAsset(
            station_id=ctx["station_id"], filename="pauta.png", original_name="pauta.png", file_path="/tmp/p.png",
            content_type="image/png", target_viewer="evaluador",
        ))
        db.commit()
    _add_checkin(ctx, minutes_ago=0)

    login(client, STUDENT)
    response = client.post("/api/student/access", json={"ecoe_event_id": ctx["event_id"], "ecoe_number": "001"})
    assert response.status_code == 200, response.text
    assert "correct_option" not in response.text
    names = [asset["original_name"] for asset in response.json()["media_assets"]]
    assert names == ["ecg.png"]  # "ambos" sí; "evaluador" nunca


def test_answer_key_still_grades_on_the_server(client):
    """Negativo de PROC-4: quitar la clave de la respuesta no rompe la corrección."""
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=0)
    with TestingSessionLocal() as db:
        token = issue_kiosk_token(
            db, db.get(Station, ctx["station_id"]), issued_by_email="t@e.edu"
        )["token"]
        db.commit()
    response = client.post(
        "/api/kiosk/submit",
        headers={"X-Kiosk-Token": token},
        json={"checkin_id": checkin_id, "answers": {"question_1": "SCA"}},
    )
    assert response.status_code == 200, response.text
    assert _responses(ctx)[0].score_obtained == 4
