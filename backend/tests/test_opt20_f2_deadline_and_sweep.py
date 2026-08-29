"""OPT-20 F2 · Deadline autoritativo desde LiveSession + autoenvío server-side.

Ver docs/optimizacion/PLANES/OPT-20__cronometro-sincronico.md
("FASE 2 — Deadline autoritativo desde LiveSession + autoenvío server-side").

Cubre:
- ``resolve_submission_deadline``: el deadline sigue la fase del ``LiveSession``
  (D1), el que entra tarde tiene menos tiempo (D2), la pausa congela la ventana,
  y el fallback al Reloj B cuando no hay ``LiveSession`` activo (pilotaje).
- ``sweep_expired_phases``: crea ``StudentResponse`` en blanco ``auto`` al vencer
  la fase, es idempotente, respeta el modo y nunca corre tras el cierre.
- Endpoints ``PUT /student/draft`` / ``PUT /kiosk/draft`` y la acción
  ``expire_phase`` de ``/live/control``.

Tests negativos (toca datos, tiempo y auth): fallback de pilotaje, aislamiento
de modo, no-op tras cierre, borrador de otra cuenta, borrador fuera de etapa.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models.entities import (
    ECOEEvent,
    LiveSession,
    Station,
    StationCheckIn,
    StationResponseDraft,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.live_sweep import sweep_expired_phases
from app.utils.helpers import resolve_submission_deadline
from conftest import ADMIN, COORDINATOR, STUDENT, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


CHOICE_FORM = {
    "questions": [
        {
            "type": "single_choice",
            "label": "Diagnóstico",
            "points": 4,
            "correct_option": "SCA",
            "options": ["SCA", "TEP", "RGE"],
        }
    ]
}


def _build_event(*, status: str = ECOEStatus.en_ejecucion.value) -> dict:
    """Evento con una estación de formulario y un estudiante, sin LiveSession."""
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="F2 deadline",
            date=date(2026, 12, 20),
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
        station = Station(
            ecoe_event_id=event.id,
            station_number=1,
            name="Estación F2",
            station_type="formulario_estudiante",
            circuit_name="Circuito A",
            station_time_minutes=8,
            transition_time_minutes=2,
            expected_outcomes="Resultado",
            student_activity="Actividad",
            pre_entry_instruction="Ingreso",
            student_station_instruction="Dentro",
            evaluator_instruction="Evaluar",
            requires_evaluator=True,
            requires_student_form=True,
            max_score=4,
            student_form_definition=CHOICE_FORM,
        )
        db.add(station)
        db.flush()
        student = Student(
            ecoe_event_id=event.id,
            name="Alumna",
            last_name="F2",
            rut=f"52{event.id}00-1",
            email=f"f2-{event.id}@example.edu",
            ecoe_number="001",
            group_name="G1",
            circuit_name="Circuito A",
            is_active=True,
        )
        db.add(student)
        db.commit()
        return {"event_id": event.id, "station_id": station.id, "student_id": student.id}


def _add_live_session(ctx: dict, *, status: str, remaining: int = 480,
                      started_secs_ago: float | None = 0.0,
                      transition_secs: int = 120) -> None:
    with TestingSessionLocal() as db:
        started = (
            None if started_secs_ago is None
            else _utcnow_naive() - timedelta(seconds=started_secs_ago)
        )
        db.add(LiveSession(
            ecoe_event_id=ctx["event_id"],
            mode=SessionMode.ejecucion.value,
            status=status,
            station_time_seconds=480,
            transition_time_seconds=transition_secs,
            remaining_seconds=remaining,
            phase_started_at=started,
        ))
        db.commit()


def _add_checkin(ctx: dict, *, minutes_ago: float = 0.0, student_id: int | None = None,
                 status: str = "confirmado") -> int:
    with TestingSessionLocal() as db:
        checkin = StationCheckIn(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=student_id or ctx["student_id"],
            evaluator_email="eval@example.edu",
            evaluator_name="Eval Test",
            status=status,
            mode=SessionMode.ejecucion.value,
            confirmed_at=_utcnow_naive() - timedelta(minutes=minutes_ago),
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin.id


def _deadline(ctx: dict, checkin_id: int, *, for_evaluator: bool = False):
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, ctx["event_id"])
        checkin = db.get(StationCheckIn, checkin_id)
        station = db.get(Station, ctx["station_id"])
        return resolve_submission_deadline(
            db, event, checkin, station, for_evaluator=for_evaluator
        )


# ── resolve_submission_deadline ───────────────────────────────────────


def test_deadline_follows_live_phase_running():
    """D1: dos check-ins con confirmed_at distinto → mismo deadline (fin de fase)."""
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=480, started_secs_ago=60)
    early = _add_checkin(ctx, minutes_ago=7)
    late = _add_checkin(ctx, minutes_ago=1, student_id=None, status="cerrado")
    # segundo check-in en la misma fase, otro alumno
    with TestingSessionLocal() as db:
        other = Student(
            ecoe_event_id=ctx["event_id"], name="Otro", last_name="X",
            rut=f"9{ctx['event_id']}9-9", email=f"o{ctx['event_id']}@e.edu",
            ecoe_number="002", group_name="G1", circuit_name="Circuito A",
        )
        db.add(other)
        db.commit()
        other_id = other.id
    late = _add_checkin(ctx, minutes_ago=1, student_id=other_id)

    d_early = _deadline(ctx, early)
    d_late = _deadline(ctx, late)
    assert d_early == d_late
    # Fin de fase = phase_started_at + remaining_seconds (≈ ahora + 420s).
    assert abs((d_early - _utcnow_naive()).total_seconds() - 420) < 5


def test_late_checkin_gets_less_time():
    """D2: el check-in a mitad de fase hereda el deadline de la rotación."""
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=480, started_secs_ago=300)
    checkin = _add_checkin(ctx, minutes_ago=0)  # entra tarde
    deadline = _deadline(ctx, checkin)
    # Reloj B daría confirmed_at + 8 min ≈ ahora + 480s; la fase da ~180s.
    remaining = (deadline - _utcnow_naive()).total_seconds()
    assert 150 < remaining < 210


def test_paused_session_freezes_deadline():
    ctx = _build_event()
    _add_live_session(ctx, status="paused", remaining=200, started_secs_ago=None)
    checkin = _add_checkin(ctx, minutes_ago=30)
    assert _deadline(ctx, checkin) is None  # sin deadline efectivo: se acepta

    # Al reanudar, la ventana vuelve a correr desde los 200s restantes.
    with TestingSessionLocal() as db:
        session = db.scalar(
            select(LiveSession).where(LiveSession.ecoe_event_id == ctx["event_id"])
        )
        session.status = "running"
        session.phase_started_at = _utcnow_naive()
        db.commit()
    resumed = _deadline(ctx, checkin)
    assert resumed is not None
    assert 170 < (resumed - _utcnow_naive()).total_seconds() < 210


def test_deadline_fallback_to_checkin_window_when_no_live_session():
    """Pilotaje sin LiveSession activo: se usa el Reloj B (confirmed_at + tiempo)."""
    ctx = _build_event(status=ECOEStatus.en_pilotaje.value)
    checkin = _add_checkin(ctx, minutes_ago=3)
    deadline = _deadline(ctx, checkin)
    # confirmed_at (hace 3 min) + 8 min de estación ≈ ahora + 300s.
    assert 270 < (deadline - _utcnow_naive()).total_seconds() < 330

    # idem con LiveSession en 'ready' (nadie maneja /live).
    _add_live_session(ctx, status="ready", started_secs_ago=None)
    assert 270 < (_deadline(ctx, checkin) - _utcnow_naive()).total_seconds() < 330


def test_evaluator_deadline_includes_transition_phase():
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=480, started_secs_ago=0,
                      transition_secs=120)
    checkin = _add_checkin(ctx, minutes_ago=0)
    student_deadline = _deadline(ctx, checkin)
    evaluator_deadline = _deadline(ctx, checkin, for_evaluator=True)
    assert evaluator_deadline > student_deadline
    assert abs((evaluator_deadline - student_deadline).total_seconds() - 120) < 2

    # En 'transition' el deadline del evaluador es el fin real de la transición.
    with TestingSessionLocal() as db:
        session = db.scalar(
            select(LiveSession).where(LiveSession.ecoe_event_id == ctx["event_id"])
        )
        session.status = "transition"
        session.remaining_seconds = 120
        session.phase_started_at = _utcnow_naive()
        db.commit()
    trans_eval = _deadline(ctx, checkin, for_evaluator=True)
    assert 110 < (trans_eval - _utcnow_naive()).total_seconds() < 125


# ── sweep_expired_phases ──────────────────────────────────────────────


def _run_sweep(ctx: dict, **kwargs) -> dict:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, ctx["event_id"])
        return sweep_expired_phases(db, event, **kwargs)


def test_server_sweep_creates_blank_student_response_on_phase_expiry():
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    checkin_id = _add_checkin(ctx, minutes_ago=15)

    out = _run_sweep(ctx)
    assert out == {"auto_responses": 1, "closed_checkins": 1}

    with TestingSessionLocal() as db:
        resp = db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        )
        assert resp is not None
        assert resp.locked is True
        assert resp.submission_kind == "auto"
        assert resp.by_contingency is False
        assert resp.answers == {}
        # single_choice sin responder → 0 sobre el máximo (D4: suma 0, marcado).
        assert resp.score_obtained == 0
        assert resp.max_score == 4
        assert db.get(StationCheckIn, checkin_id).status == "cerrado"


def test_server_sweep_uses_draft_answers_when_present():
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    checkin_id = _add_checkin(ctx, minutes_ago=15)
    with TestingSessionLocal() as db:
        db.add(StationResponseDraft(
            checkin_id=checkin_id,
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            answers={"question_1": "SCA"},
        ))
        db.commit()

    _run_sweep(ctx)
    with TestingSessionLocal() as db:
        resp = db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        )
        assert resp.answers == {"question_1": "SCA"}
        assert resp.score_obtained == 4  # respuesta correcta autocalificada
        # el borrador se descarta al finalizar
        assert db.scalar(
            select(StationResponseDraft).where(
                StationResponseDraft.checkin_id == checkin_id
            )
        ) is None


def test_server_sweep_is_idempotent():
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    _add_checkin(ctx, minutes_ago=15)

    first = _run_sweep(ctx)
    second = _run_sweep(ctx)
    assert first["auto_responses"] == 1
    assert second == {"auto_responses": 0, "closed_checkins": 0}
    with TestingSessionLocal() as db:
        rows = db.scalars(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        ).all()
        assert len(rows) == 1


def test_server_sweep_does_not_touch_a_manual_response():
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    checkin_id = _add_checkin(ctx, minutes_ago=15)
    with TestingSessionLocal() as db:
        db.add(StudentResponse(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            mode=SessionMode.ejecucion.value,
            answers={"question_1": "SCA"},
            submission_kind="manual",
            score_obtained=4,
            max_score=4,
        ))
        db.commit()

    out = _run_sweep(ctx)
    assert out["auto_responses"] == 0
    with TestingSessionLocal() as db:
        resp = db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        )
        assert resp.submission_kind == "manual"
        assert resp.score_obtained == 4


def test_server_sweep_does_not_run_after_close():
    ctx = _build_event(status=ECOEStatus.cerrado.value)
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    _add_checkin(ctx, minutes_ago=15)

    out = _run_sweep(ctx, force=True)
    assert out == {"auto_responses": 0, "closed_checkins": 0}
    with TestingSessionLocal() as db:
        assert db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        ) is None


def test_server_sweep_respects_mode_scoping():
    """Negativo: una respuesta de pilotaje no satisface la fase de ejecución."""
    ctx = _build_event()  # en_ejecucion
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    checkin_id = _add_checkin(ctx, minutes_ago=15)
    with TestingSessionLocal() as db:
        db.add(StudentResponse(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            mode=SessionMode.pilotaje.value,
            answers={"question_1": "SCA"},
            submission_kind="manual",
            score_obtained=4,
            max_score=4,
        ))
        db.commit()

    out = _run_sweep(ctx)
    assert out["auto_responses"] == 1
    with TestingSessionLocal() as db:
        modes = sorted(db.scalars(
            select(StudentResponse.mode).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        ).all())
        assert modes == ["ejecucion", "pilotaje"]
        auto = db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"],
                StudentResponse.mode == SessionMode.ejecucion.value,
            )
        )
        assert auto.submission_kind == "auto"


def test_server_sweep_noop_while_phase_open_or_paused():
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=480, started_secs_ago=30)
    _add_checkin(ctx, minutes_ago=1)
    assert _run_sweep(ctx) == {"auto_responses": 0, "closed_checkins": 0}

    with TestingSessionLocal() as db:
        session = db.scalar(
            select(LiveSession).where(LiveSession.ecoe_event_id == ctx["event_id"])
        )
        session.status = "paused"
        session.phase_started_at = None
        db.commit()
    assert _run_sweep(ctx) == {"auto_responses": 0, "closed_checkins": 0}


# ── Endpoints: drafts + expire_phase ──────────────────────────────────


def _seed_student_checkin(*, minutes_ago: float = 0.0) -> int:
    """Check-in confirmado para student1 en la estación 2 del evento demo."""
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, 1)
        event.status = ECOEStatus.en_ejecucion.value
        db.add(event)
        checkin = StationCheckIn(
            ecoe_event_id=1,
            station_id=2,
            student_id=1,
            evaluator_email="eval1@ecoe.cl",
            evaluator_name="Eval",
            status="confirmado",
            mode=SessionMode.ejecucion.value,
            confirmed_at=_utcnow_naive() - timedelta(minutes=minutes_ago),
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin.id


def _restore_event_1(previous: str) -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, 1)
        event.status = previous
        db.add(event)
        db.execute(
            StationResponseDraft.__table__.delete().where(
                StationResponseDraft.ecoe_event_id == 1
            )
        )
        db.commit()


def test_student_draft_upsert_is_idempotent(client):
    with TestingSessionLocal() as db:
        previous = str(db.get(ECOEEvent, 1).status)
    checkin_id = _seed_student_checkin(minutes_ago=1)
    try:
        login(client, STUDENT)
        r = client.put("/api/student/draft", json={
            "ecoe_event_id": 1, "station_id": 2, "student_id": 1,
            "checkin_id": checkin_id, "answers": {"question_1": "SCA"},
        })
        assert r.status_code == 200, r.text
        assert r.json()["saved"] is True
        with TestingSessionLocal() as db:
            draft = db.scalar(
                select(StationResponseDraft).where(
                    StationResponseDraft.checkin_id == checkin_id
                )
            )
            assert draft.answers == {"question_1": "SCA"}

        # Segundo PUT: upsert, no duplica.
        r2 = client.put("/api/student/draft", json={
            "ecoe_event_id": 1, "station_id": 2, "student_id": 1,
            "checkin_id": checkin_id, "answers": {"question_1": "TEP"},
        })
        assert r2.status_code == 200
        with TestingSessionLocal() as db:
            drafts = db.scalars(
                select(StationResponseDraft).where(
                    StationResponseDraft.checkin_id == checkin_id
                )
            ).all()
            assert len(drafts) == 1
            assert drafts[0].answers == {"question_1": "TEP"}
    finally:
        _restore_event_1(previous)


def test_student_draft_rejected_for_another_student(client):
    with TestingSessionLocal() as db:
        previous = str(db.get(ECOEEvent, 1).status)
    checkin_id = _seed_student_checkin(minutes_ago=1)
    try:
        login(client, STUDENT)  # student1
        r = client.put("/api/student/draft", json={
            "ecoe_event_id": 1, "station_id": 2, "student_id": 2,
            "checkin_id": checkin_id, "answers": {"question_1": "SCA"},
        })
        assert r.status_code == 403
    finally:
        _restore_event_1(previous)


def test_student_draft_rejected_outside_submission_stage(client):
    with TestingSessionLocal() as db:
        previous = str(db.get(ECOEEvent, 1).status)
        event = db.get(ECOEEvent, 1)
        event.status = ECOEStatus.publicado.value
        db.add(event)
        db.commit()
    try:
        login(client, STUDENT)
        r = client.put("/api/student/draft", json={
            "ecoe_event_id": 1, "station_id": 2, "student_id": 1,
            "answers": {"question_1": "SCA"},
        })
        assert r.status_code == 409
    finally:
        _restore_event_1(previous)


def test_kiosk_draft_requires_active_checkin(client):
    with TestingSessionLocal() as db:
        previous = str(db.get(ECOEEvent, 1).status)
    _seed_student_checkin(minutes_ago=1)  # station 2
    try:
        login(client, COORDINATOR)
        token = client.post("/api/kiosk/stations/2/token").json()["token"]
        # checkin_id inexistente para esta estación
        r = client.put("/api/kiosk/draft", headers={"X-Kiosk-Token": token},
                       json={"checkin_id": 999999, "answers": {}})
        assert r.status_code == 400
    finally:
        _restore_event_1(previous)


def test_expire_phase_finalizes_open_checkins(auth_client):
    """Buzzer server-side: expire_phase congela en 0 y barre las ventanas
    abiertas sin avanzar el índice de estación (H-opt20-6 / H-vivo-8)."""
    ctx = _build_event()
    checkin_id = _add_checkin(ctx, minutes_ago=1)
    started = auth_client.post(
        "/api/live/control",
        json={"ecoe_event_id": ctx["event_id"], "action": "start"},
    ).json()
    assert started["current_station_index"] == 1

    r = auth_client.post(
        "/api/live/control",
        json={"ecoe_event_id": ctx["event_id"], "action": "expire_phase"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["remaining_seconds"] == 0
    assert r.json()["current_station_index"] == 1  # NO avanza de estación

    with TestingSessionLocal() as db:
        resp = db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        )
        assert resp is not None
        assert resp.submission_kind == "auto"
        assert resp.locked is True
        assert db.get(StationCheckIn, checkin_id).status == "cerrado"


def test_expire_phase_rejected_for_unknown_action(auth_client):
    r = auth_client.post(
        "/api/live/control", json={"ecoe_event_id": 1, "action": "teleport"}
    )
    assert r.status_code == 400
