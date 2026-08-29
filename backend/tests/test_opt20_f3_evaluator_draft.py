"""OPT-20 F3 · Borrador server-side del EvaluatorRecord (D3).

Ver docs/optimizacion/PLANES/OPT-20__cronometro-sincronico.md
("FASE 3 — Borrador server-side del EvaluatorRecord").

Cubre:
- ``PUT /evaluator/draft``: upsert de un ``EvaluatorRecord`` parcial con
  ``is_draft=True`` (scoping por estación asignada, ventana del evaluador,
  gate de etapa).
- ``POST /evaluator/submit``: promueve un borrador existente en vez de
  rechazarlo por "ya existe".
- ``compute_results`` / ``build_traceability_report``: un borrador no suma al
  consolidado ni cuenta como evaluación completa.
- ``sweep_expired_phases``: al vencer la fase, un borrador de evaluador sigue
  ``is_draft=True`` (el barrido no lo promueve ni crea filas).
- ``/contingency/evaluator-record``: finaliza un borrador existente.
- ``compute_ecoe_validation``: advertencia de cierre con borradores pendientes.

Negativos (datos + resultados + auth): borrador de estación no asignada (403),
borrador fuera de etapa (409), borrador cuando ya hay registro final (409).
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models.entities import (
    ECOEEvent,
    EvaluatorRecord,
    LiveSession,
    Station,
    StationCheckIn,
    Student,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.live_sweep import sweep_expired_phases
from app.services.results import build_traceability_report, compute_results
from app.services.validation import compute_ecoe_validation
from conftest import ADMIN, COORDINATOR, EVALUATOR, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Isolated event helpers (evaluator station + one student) ───────────


def _build_event(*, status: str = ECOEStatus.en_ejecucion.value) -> dict:
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="F3 borrador evaluador",
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
        station = Station(
            ecoe_event_id=event.id,
            station_number=1,
            name="Estación evaluador F3",
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
            requires_student_form=False,
            max_score=20,
        )
        db.add(station)
        db.flush()
        student = Student(
            ecoe_event_id=event.id,
            name="Alumna",
            last_name="F3",
            rut=f"53{event.id}00-1",
            email=f"f3-{event.id}@example.edu",
            ecoe_number="001",
            group_name="G1",
            circuit_name="Circuito A",
            is_active=True,
        )
        db.add(student)
        db.commit()
        return {"event_id": event.id, "station_id": station.id, "student_id": student.id}


def _add_checkin(ctx: dict, *, minutes_ago: float = 0.0, status: str = "confirmado") -> int:
    with TestingSessionLocal() as db:
        checkin = StationCheckIn(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
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


def _add_draft(ctx: dict, *, score: float = 12.0, is_draft: bool = True) -> int:
    with TestingSessionLocal() as db:
        record = EvaluatorRecord(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            mode=SessionMode.ejecucion.value,
            evaluator_name="Eval Test",
            score_obtained=score,
            max_score=20,
            observation="parcial",
            answers={"item_1": 2},
            is_draft=is_draft,
            submission_kind="manual",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record.id


def _add_live_session(ctx: dict, *, status: str, remaining: int = 1,
                      started_secs_ago: float = 600.0) -> None:
    with TestingSessionLocal() as db:
        db.add(LiveSession(
            ecoe_event_id=ctx["event_id"],
            mode=SessionMode.ejecucion.value,
            status=status,
            station_time_seconds=480,
            transition_time_seconds=120,
            remaining_seconds=remaining,
            phase_started_at=_utcnow_naive() - timedelta(seconds=started_secs_ago),
        ))
        db.commit()


# ── compute_results / traceability ────────────────────────────────────


def test_evaluator_draft_not_counted_in_results():
    ctx = _build_event()
    _add_draft(ctx, score=12.0, is_draft=True)

    with TestingSessionLocal() as db:
        results = compute_results(db, ctx["event_id"])
        row = next(r for r in results if r["student_id"] == ctx["student_id"])
        # El borrador no suma nada al consolidado.
        assert row["total_score"] == 0
        assert row["max_score"] == 0

        report = build_traceability_report(db, ctx["event_id"])
        student_row = report["student_traceability"][0]
        assert student_row["evaluator_submissions"] == 0
        assert student_row["pending_evaluator_drafts"] == 1
        assert student_row["completion_status"] == "parcial"
        assert report["summary"]["pending_evaluator_drafts"] == 1


def test_evaluator_draft_promoted_counts_in_results():
    ctx = _build_event()
    record_id = _add_draft(ctx, score=12.0, is_draft=True)
    with TestingSessionLocal() as db:
        record = db.get(EvaluatorRecord, record_id)
        record.is_draft = False
        record.score_obtained = 15
        db.commit()

    with TestingSessionLocal() as db:
        row = next(
            r for r in compute_results(db, ctx["event_id"])
            if r["student_id"] == ctx["student_id"]
        )
        assert row["total_score"] == 15
        assert row["max_score"] == 20


# ── sweep ─────────────────────────────────────────────────────────────


def test_sweep_keeps_evaluator_record_as_draft():
    ctx = _build_event()
    _add_live_session(ctx, status="running", remaining=1, started_secs_ago=600)
    _add_checkin(ctx, minutes_ago=15)
    record_id = _add_draft(ctx, is_draft=True)

    with TestingSessionLocal() as db:
        out = sweep_expired_phases(db, db.get(ECOEEvent, ctx["event_id"]), force=True)
    # La estación no es de formulario: el barrido no crea StudentResponse.
    assert out == {"auto_responses": 0, "closed_checkins": 0}
    with TestingSessionLocal() as db:
        record = db.get(EvaluatorRecord, record_id)
        assert record.is_draft is True
        rows = db.scalars(
            select(EvaluatorRecord).where(
                EvaluatorRecord.ecoe_event_id == ctx["event_id"]
            )
        ).all()
        assert len(rows) == 1  # ni promueve ni duplica


# ── compute_ecoe_validation ───────────────────────────────────────────


def test_close_warning_counts_pending_evaluator_drafts():
    ctx = _build_event()
    _add_draft(ctx, is_draft=True)
    with TestingSessionLocal() as db:
        report = compute_ecoe_validation(db, db.get(ECOEEvent, ctx["event_id"]))
    assert report["pending_evaluator_draft_count"] == 1
    assert report["pending_evaluator_draft_stations"] == [1]
    assert any(
        "evaluador en borrador sin finalizar" in warning
        for warning in report["warnings"]
    )


# ── Endpoints (demo event, real assignments) ──────────────────────────
#
# El evento demo (id 1) está en_ejecucion; eval1@ecoe.cl tiene la estación 1
# asignada. El seed ya deja un EvaluatorRecord final para student 1, así que
# los tests de borrador usan student 2.


def _seed_evaluator_checkin(station_id: int, student_id: int, *, minutes_ago: float = 0.0) -> int:
    with TestingSessionLocal() as db:
        checkin = StationCheckIn(
            ecoe_event_id=1,
            station_id=station_id,
            student_id=student_id,
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


def _cleanup_event_1_records(student_ids: tuple[int, ...]) -> None:
    with TestingSessionLocal() as db:
        db.execute(
            EvaluatorRecord.__table__.delete().where(
                EvaluatorRecord.ecoe_event_id == 1,
                EvaluatorRecord.student_id.in_(student_ids),
            )
        )
        db.execute(
            StationCheckIn.__table__.delete().where(
                StationCheckIn.ecoe_event_id == 1,
                StationCheckIn.student_id.in_(student_ids),
            )
        )
        db.commit()


def test_evaluator_draft_and_promotion_via_submit(client):
    checkin_id = _seed_evaluator_checkin(1, 2, minutes_ago=1)
    try:
        login(client, EVALUATOR)
        draft = client.put("/api/evaluator/draft", json={
            "ecoe_event_id": 1, "station_id": 1, "student_id": 2,
            "checkin_id": checkin_id, "evaluator_name": "Camila Soto",
            "score_obtained": 6, "observation": "parcial",
            "answers": {"item_scores": {"1": 2}},
        })
        assert draft.status_code == 200, draft.text
        assert draft.json()["is_draft"] is True
        record_id = draft.json()["record_id"]

        with TestingSessionLocal() as db:
            record = db.get(EvaluatorRecord, record_id)
            assert record.is_draft is True
            assert record.max_score == 20  # autoritativo (suma de ítems)
            # No cuenta en resultados mientras sea borrador.
            row = next(
                r for r in compute_results(db, 1) if r["student_id"] == 2
            )
            assert row["total_score"] == 0

        # Segundo PUT: upsert, no duplica.
        draft2 = client.put("/api/evaluator/draft", json={
            "ecoe_event_id": 1, "station_id": 1, "student_id": 2,
            "checkin_id": checkin_id, "evaluator_name": "Camila Soto",
            "score_obtained": 10, "observation": "más avanzado", "answers": {},
        })
        assert draft2.status_code == 200
        assert draft2.json()["record_id"] == record_id

        # POST /evaluator/submit sobre la tupla con borrador → promueve, no 400.
        submit = client.post("/api/evaluator/submit", json={
            "checkin_id": checkin_id, "ecoe_event_id": 1, "station_id": 1,
            "student_id": 2, "evaluator_name": "Camila Soto",
            "score_obtained": 14, "max_score": 999, "observation": "final",
            "answers": {"item_scores": {"1": 2, "2": 2}},
        })
        assert submit.status_code == 200, submit.text
        assert submit.json()["record_id"] == record_id

        with TestingSessionLocal() as db:
            record = db.get(EvaluatorRecord, record_id)
            assert record.is_draft is False
            assert record.score_obtained == 14
            assert record.max_score == 20  # recalculado, no el 999 del cliente
            assert record.submission_kind == "manual"
            rows = db.scalars(
                select(EvaluatorRecord).where(
                    EvaluatorRecord.ecoe_event_id == 1,
                    EvaluatorRecord.student_id == 2,
                )
            ).all()
            assert len(rows) == 1
    finally:
        _cleanup_event_1_records((2,))


def test_evaluator_draft_scoping_rejects_unassigned_station(client):
    # eval1 tiene la estación 1; la 3 es de otro evaluador.
    checkin_id = _seed_evaluator_checkin(3, 3, minutes_ago=1)
    try:
        login(client, EVALUATOR)
        r = client.put("/api/evaluator/draft", json={
            "ecoe_event_id": 1, "station_id": 3, "student_id": 3,
            "checkin_id": checkin_id, "evaluator_name": "Camila Soto",
            "score_obtained": 4, "observation": "", "answers": {},
        })
        assert r.status_code == 403, r.text
        with TestingSessionLocal() as db:
            assert db.scalar(
                select(EvaluatorRecord).where(
                    EvaluatorRecord.ecoe_event_id == 1,
                    EvaluatorRecord.station_id == 3,
                )
            ) is None
    finally:
        _cleanup_event_1_records((3,))


def test_evaluator_draft_rejected_outside_submission_stage(client):
    with TestingSessionLocal() as db:
        previous = str(db.get(ECOEEvent, 1).status)
    checkin_id = _seed_evaluator_checkin(1, 2, minutes_ago=1)
    try:
        with TestingSessionLocal() as db:
            event = db.get(ECOEEvent, 1)
            event.status = ECOEStatus.publicado.value
            db.add(event)
            db.commit()
        login(client, EVALUATOR)
        r = client.put("/api/evaluator/draft", json={
            "ecoe_event_id": 1, "station_id": 1, "student_id": 2,
            "checkin_id": checkin_id, "evaluator_name": "Camila Soto",
            "score_obtained": 4, "observation": "", "answers": {},
        })
        assert r.status_code == 409, r.text
    finally:
        with TestingSessionLocal() as db:
            event = db.get(ECOEEvent, 1)
            event.status = previous
            db.add(event)
            db.commit()
        _cleanup_event_1_records((2,))


def test_evaluator_draft_rejected_when_final_record_exists(client):
    # student 1 ya tiene un registro final del seed en la estación 1.
    checkin_id = _seed_evaluator_checkin(1, 1, minutes_ago=1)
    try:
        login(client, EVALUATOR)
        r = client.put("/api/evaluator/draft", json={
            "ecoe_event_id": 1, "station_id": 1, "student_id": 1,
            "checkin_id": checkin_id, "evaluator_name": "Camila Soto",
            "score_obtained": 4, "observation": "", "answers": {},
        })
        assert r.status_code == 409, r.text
    finally:
        with TestingSessionLocal() as db:
            db.execute(
                StationCheckIn.__table__.delete().where(
                    StationCheckIn.id == checkin_id
                )
            )
            db.commit()


def test_pending_evaluator_drafts_listing(client):
    checkin_id = _seed_evaluator_checkin(1, 2, minutes_ago=1)
    try:
        login(client, EVALUATOR)
        client.put("/api/evaluator/draft", json={
            "ecoe_event_id": 1, "station_id": 1, "student_id": 2,
            "checkin_id": checkin_id, "evaluator_name": "Camila Soto",
            "score_obtained": 7, "observation": "a medias", "answers": {},
        })
        # Negativo: un evaluador no puede leer la lista de coordinación.
        assert client.get("/api/contingency/evaluator-drafts/1").status_code == 403

        login(client, COORDINATOR)
        r = client.get("/api/contingency/evaluator-drafts/1")
        assert r.status_code == 200, r.text
        drafts = r.json()["drafts"]
        assert len(drafts) == 1
        assert drafts[0]["student_id"] == 2
        assert drafts[0]["station_number"] == 1
        assert drafts[0]["score_obtained"] == 7
    finally:
        _cleanup_event_1_records((2,))


def test_contingency_finalizes_evaluator_draft(client):
    checkin_id = _seed_evaluator_checkin(1, 2, minutes_ago=1)
    try:
        login(client, EVALUATOR)
        draft = client.put("/api/evaluator/draft", json={
            "ecoe_event_id": 1, "station_id": 1, "student_id": 2,
            "checkin_id": checkin_id, "evaluator_name": "Camila Soto",
            "score_obtained": 6, "observation": "quedó a medias", "answers": {},
        })
        assert draft.status_code == 200, draft.text
        record_id = draft.json()["record_id"]

        # Coordinación finaliza el borrador por contingencia.
        login(client, COORDINATOR)
        fin = client.post("/api/contingency/evaluator-record", json={
            "ecoe_event_id": 1, "station_id": 1, "student_id": 2,
            "evaluator_name": "Coordinación", "score_obtained": 13,
            "max_score": 999, "observation": "cerrado por contingencia",
            "answers": {},
        })
        assert fin.status_code == 200, fin.text
        assert fin.json()["record_id"] == record_id
        assert fin.json()["finalized_draft"] is True

        with TestingSessionLocal() as db:
            record = db.get(EvaluatorRecord, record_id)
            assert record.is_draft is False
            assert record.by_contingency is True
            assert record.submission_kind == "contingency"
            assert record.score_obtained == 13
            assert record.max_score == 20
            row = next(
                r for r in compute_results(db, 1) if r["student_id"] == 2
            )
            assert row["total_score"] == 13
    finally:
        _cleanup_event_1_records((2,))
