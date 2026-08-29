"""OPT-2 · Aislamiento pilotaje/ejecución en trazabilidad, cierre y cola de
corrección.

Ver docs/optimizacion/PLANES/OPT-2__aislamiento-mode.md. El consolidado
(`compute_results`) ya filtra `mode == ejecucion`; estos tests cubren que el
resto de la maquinaria de cierre (trazabilidad, advertencia de corrección
diferida del modal de cierre y cola de `/grading`) haga lo mismo, y que
entrar a la ejecución real cierre los check-ins residuales del pilotaje.

Tests negativos: el aislamiento pilotaje/ejecución es dato sensible — un
registro de un modo no debe contar en el otro (AGENTS.md).
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models.entities import (
    ECOEEvent,
    EvaluatorRecord,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.results import build_traceability_report
from app.services.validation import compute_ecoe_validation, update_ecoe_status
from conftest import ADMIN, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


MANUAL_FORM = {
    "questions": [
        {"type": "short_text", "label": "Interpreta el ECG", "points": 6},
    ]
}


def _build_event(*, deferred: bool = False) -> dict:
    """Evento en ejecución real con una estación (evaluador + formulario) y un
    estudiante del mismo circuito, sin ningún registro operativo todavía."""
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Aislamiento",
            date=date(2026, 12, 15),
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
            status=ECOEStatus.en_ejecucion.value,
        )
        db.add(event)
        db.flush()
        station = Station(
            ecoe_event_id=event.id,
            station_number=1,
            name="Estación ECG",
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
            requires_deferred_grading=deferred,
            max_score=6,
            student_form_definition=MANUAL_FORM,
        )
        db.add(station)
        db.flush()
        student = Student(
            ecoe_event_id=event.id,
            name="Alumna",
            last_name="Aislada",
            rut=f"42{event.id}00-1",
            email=f"iso{event.id}@example.edu",
            ecoe_number="001",
            group_name="G1",
            circuit_name="Circuito A",
            is_active=True,
        )
        db.add(student)
        db.commit()
        return {"event_id": event.id, "station_id": station.id, "student_id": student.id}


def _add_evaluator_record(ctx: dict, *, mode: str) -> None:
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            evaluator_name="Evaluador Test",
            mode=mode,
            score_obtained=5,
            max_score=6,
        ))
        db.commit()


def _add_student_response(ctx: dict, *, mode: str, score_obtained=6.0, max_score=6.0) -> int:
    with TestingSessionLocal() as db:
        grading = (
            {}
            if score_obtained is not None
            else {"question_1": {"kind": "manual", "earned": None, "max": max_score}}
        )
        response = StudentResponse(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            mode=mode,
            answers={"question_1": "texto"},
            grading=grading,
            submitted_at=_utcnow_naive(),
            score_obtained=score_obtained,
            max_score=max_score,
        )
        db.add(response)
        db.commit()
        db.refresh(response)
        return response.id


def _add_checkin(ctx: dict, *, status: str = "confirmado", mode: str = SessionMode.ejecucion.value) -> int:
    with TestingSessionLocal() as db:
        checkin = StationCheckIn(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            evaluator_email="eval@example.edu",
            evaluator_name="Evaluador Test",
            status=status,
            mode=mode,
            confirmed_at=_utcnow_naive(),
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin.id


def _set_event_status(event_id: int, status: str) -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        event.status = status
        db.add(event)
        db.commit()


def _trace_row(event_id: int, student_id: int) -> tuple[dict, dict]:
    with TestingSessionLocal() as db:
        report = build_traceability_report(db, event_id)
    row = next(r for r in report["student_traceability"] if r["student_id"] == student_id)
    return row, report["summary"]


# ── Trazabilidad ──────────────────────────────────────────────────────

def test_traceability_ignores_pilotage_activity():
    """Un estudiante con SOLO registros de pilotaje no tiene actividad real:
    debe verse "sin actividad", con faltantes completos y contadores en 0."""
    ctx = _build_event()
    _add_evaluator_record(ctx, mode=SessionMode.pilotaje.value)
    _add_student_response(ctx, mode=SessionMode.pilotaje.value)

    row, summary = _trace_row(ctx["event_id"], ctx["student_id"])
    assert row["completion_status"] == "sin actividad"
    assert row["missing_evaluations"] == 1
    assert row["missing_student_submissions"] == 1
    assert row["evaluator_submissions"] == 0
    assert row["student_submissions"] == 0
    assert summary["evaluator_submissions"] == 0
    assert summary["student_submissions"] == 0


def test_traceability_counts_execution_activity():
    """El mismo estudiante con actividad de ejecución real: "completo"."""
    ctx = _build_event()
    _add_evaluator_record(ctx, mode=SessionMode.ejecucion.value)
    _add_student_response(ctx, mode=SessionMode.ejecucion.value)

    row, summary = _trace_row(ctx["event_id"], ctx["student_id"])
    assert row["completion_status"] == "completo"
    assert row["missing_evaluations"] == 0
    assert row["missing_student_submissions"] == 0
    assert summary["evaluator_submissions"] == 1
    assert summary["student_submissions"] == 1


def test_traceability_mixed_modes_counts_only_execution():
    """Pilotaje + ejecución en la misma estación: solo cuenta la ejecución."""
    ctx = _build_event()
    _add_evaluator_record(ctx, mode=SessionMode.pilotaje.value)
    _add_evaluator_record(ctx, mode=SessionMode.ejecucion.value)
    _add_student_response(ctx, mode=SessionMode.pilotaje.value)
    _add_student_response(ctx, mode=SessionMode.ejecucion.value)

    row, summary = _trace_row(ctx["event_id"], ctx["student_id"])
    assert row["evaluator_submissions"] == 1
    assert row["student_submissions"] == 1
    assert row["completion_status"] == "completo"
    assert summary["evaluator_submissions"] == 1
    assert summary["student_submissions"] == 1


# ── Cola de corrección diferida (/grading) ────────────────────────────

def test_grading_queue_excludes_pilotage_responses(auth_client):
    """Negativo: una respuesta de pilotaje sin puntuar no aparece en la cola
    de corrección ni suma a `pending_count`."""
    login(auth_client, ADMIN)
    ctx = _build_event(deferred=True)
    pilot_id = _add_student_response(
        ctx, mode=SessionMode.pilotaje.value, score_obtained=None, max_score=6.0
    )
    exec_id = _add_student_response(
        ctx, mode=SessionMode.ejecucion.value, score_obtained=None, max_score=6.0
    )

    listing = auth_client.get(f"/api/grading/{ctx['event_id']}")
    assert listing.status_code == 200, listing.text
    body = listing.json()
    returned_ids = {row["response_id"] for row in body["responses"]}
    assert exec_id in returned_ids
    assert pilot_id not in returned_ids
    assert body["pending_count"] == 1


# ── Advertencia de corrección diferida del modal de cierre ────────────

def test_close_warning_ignores_pilotage_pending_grading():
    """Negativo: una respuesta de pilotaje sin puntuar no enciende
    `pending_deferred_grading_stations`."""
    ctx = _build_event(deferred=True)
    _add_student_response(
        ctx, mode=SessionMode.pilotaje.value, score_obtained=None, max_score=6.0
    )

    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, ctx["event_id"])
        validation = compute_ecoe_validation(db, event)
    assert validation["pending_deferred_grading_stations"] == []


def test_close_warning_fires_for_execution_pending_grading():
    ctx = _build_event(deferred=True)
    _add_student_response(
        ctx, mode=SessionMode.ejecucion.value, score_obtained=None, max_score=6.0
    )

    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, ctx["event_id"])
        validation = compute_ecoe_validation(db, event)
    assert validation["pending_deferred_grading_stations"] == [1]


# ── Efecto colateral: entrar a la ejecución cierra check-ins residuales ─

def test_entering_execution_closes_open_pilotage_checkins(monkeypatch):
    """Un check-in `confirmado` del pilotaje queda `cerrado` al entrar a
    `en_ejecucion`, y no vuelve a aparecer como sesión activa. (H-vivo-4)"""
    ctx = _build_event()
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, ctx["event_id"])
        event.status = ECOEStatus.publicado.value
        db.add(event)
        checkin = StationCheckIn(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            evaluator_email="eval@example.edu",
            evaluator_name="Evaluador Test",
            status="confirmado",
            confirmed_at=_utcnow_naive() - timedelta(minutes=1),
        )
        db.add(checkin)
        db.commit()
        checkin_id = checkin.id

    # Los gates de readiness no son lo que este test ejercita: sólo el efecto
    # colateral de la transición → en_ejecucion.
    monkeypatch.setattr(
        "app.services.validation.compute_ecoe_validation",
        lambda db, event: {"can_pilot": True, "can_publish": True, "can_start_live": True},
    )

    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, ctx["event_id"])
        update_ecoe_status(db, event, ECOEStatus.en_ejecucion.value)

    with TestingSessionLocal() as db:
        assert db.get(StationCheckIn, checkin_id).status == "cerrado"
        still_open = db.scalars(
            select(StationCheckIn).where(
                StationCheckIn.ecoe_event_id == ctx["event_id"],
                StationCheckIn.status == "confirmado",
            )
        ).all()
        assert still_open == []


# ── Parte 2: columna `mode` en station_checkins ──────────────────────

def test_checkin_mode_stamped_from_event_status(auth_client):
    """`confirm_station_checkin` estampa el modo resuelto del evento."""
    login(auth_client, ADMIN)
    original = None
    with TestingSessionLocal() as db:
        original = str(db.get(ECOEEvent, 1).status)
    try:
        _set_event_status(1, ECOEStatus.en_pilotaje.value)
        r1 = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E001",
        })
        assert r1.status_code == 200, r1.text

        _set_event_status(1, ECOEStatus.en_ejecucion.value)
        r2 = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E001",
        })
        assert r2.status_code == 200, r2.text

        with TestingSessionLocal() as db:
            modes = {
                (c.status, str(c.mode))
                for c in db.scalars(
                    select(StationCheckIn).where(
                        StationCheckIn.ecoe_event_id == 1,
                        StationCheckIn.station_id == 1,
                    )
                ).all()
            }
        assert ("confirmado", "ejecucion") in modes
        assert any(m == "pilotaje" for _, m in modes)
    finally:
        with TestingSessionLocal() as db:
            db.query(StationCheckIn).filter(
                StationCheckIn.ecoe_event_id == 1, StationCheckIn.station_id == 1
            ).delete()
            event = db.get(ECOEEvent, 1)
            event.status = original
            db.add(event)
            db.commit()


def test_traceability_ignores_pilotage_checkins():
    """Negativo: un check-in de pilotaje no cuenta en la trazabilidad real."""
    ctx = _build_event()
    _add_checkin(ctx, mode=SessionMode.pilotaje.value)

    row, summary = _trace_row(ctx["event_id"], ctx["student_id"])
    assert row["completion_status"] == "sin actividad"
    assert row["checkins_confirmed"] == 0
    assert summary["confirmed_checkins"] == 0


def test_traceability_counts_execution_checkins():
    ctx = _build_event()
    _add_checkin(ctx, mode=SessionMode.ejecucion.value)

    row, summary = _trace_row(ctx["event_id"], ctx["student_id"])
    assert row["checkins_confirmed"] == 1
    assert summary["confirmed_checkins"] == 1
