"""OPT-20 F4 · "Sin respuesta" explícito + trazabilidad (D4).

Ver docs/optimizacion/PLANES/OPT-20__cronometro-sincronico.md
("FASE 4 — 'Sin respuesta' explícito + trazabilidad (D4)").

Cubre:
- ``grade_answers`` / ``per_question``: cada ítem lleva ``answered: bool`` sin
  cambiar la aritmética.
- ``submission_kind`` lo estampa siempre el servidor: ``manual`` en el envío del
  estudiante, ``auto`` en el barrido en blanco, ``contingency`` por coordinación,
  ``draft_finalized`` al promover un borrador del evaluador (reconciliación F3).
- El cliente nunca elige ``submission_kind`` (negativo).
- ``build_traceability_report``: cuenta y etiqueta los autoenvíos en blanco.
- ``export_results_excel``: hoja ``trazabilidad_envios`` con el indicador de origen.

No hay migración en F4: las columnas ``submission_kind`` ya existen (F2 en
``student_responses`` = ``l2m3n4o5p6q7``; F3 en ``evaluator_records`` =
``m3n4o5p6q7r8``). El ``answered`` por pregunta vive dentro del JSON de
``grading``, no es columna.
"""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO

import pandas as pd
from sqlalchemy import select

from app.models.entities import (
    ECOEEvent,
    EvaluatorRecord,
    LiveSession,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.grading import grade_answers
from app.services.live_sweep import sweep_expired_phases
from app.services.results import (
    build_traceability_report,
    compute_results,
    export_results_excel,
)
from conftest import EVALUATOR, TestingSessionLocal, login


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
        },
        {
            "type": "short_text",
            "label": "Justifica",
            "points": 3,
        },
    ]
}

AUTO_ONLY_FORM = {
    "questions": [
        {
            "type": "single_choice",
            "label": "Diagnóstico",
            "points": 4,
            "correct_option": "SCA",
            "options": ["SCA", "TEP", "RGE"],
        },
    ]
}


def _build_event(
    *, status: str = ECOEStatus.en_ejecucion.value, form: dict | None = None
) -> dict:
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="F4 sin respuesta",
            date=date(2026, 12, 22),
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
            name="Estación F4",
            station_type="formulario_estudiante",
            circuit_name="Circuito A",
            station_time_minutes=8,
            transition_time_minutes=2,
            expected_outcomes="Resultado",
            student_activity="Actividad",
            pre_entry_instruction="Ingreso",
            student_station_instruction="Dentro",
            evaluator_instruction="Evaluar",
            requires_evaluator=False,
            requires_student_form=True,
            max_score=0,
            student_form_definition=form or CHOICE_FORM,
        )
        db.add(station)
        db.flush()
        student = Student(
            ecoe_event_id=event.id,
            name="Alumna",
            last_name="F4",
            rut=f"54{event.id}00-1",
            email=f"f4-{event.id}@example.edu",
            ecoe_number="001",
            group_name="G1",
            circuit_name="Circuito A",
            is_active=True,
        )
        db.add(student)
        db.commit()
        return {"event_id": event.id, "station_id": station.id, "student_id": student.id}


def _add_checkin(ctx: dict, *, minutes_ago: float = 0.0) -> int:
    with TestingSessionLocal() as db:
        checkin = StationCheckIn(
            ecoe_event_id=ctx["event_id"],
            station_id=ctx["station_id"],
            student_id=ctx["student_id"],
            evaluator_email="eval@example.edu",
            evaluator_name="Eval Test",
            status="confirmado",
            mode=SessionMode.ejecucion.value,
            confirmed_at=_utcnow_naive() - timedelta(minutes=minutes_ago),
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin.id


def _add_running_expired_session(ctx: dict) -> None:
    with TestingSessionLocal() as db:
        db.add(LiveSession(
            ecoe_event_id=ctx["event_id"],
            mode=SessionMode.ejecucion.value,
            status="running",
            station_time_seconds=480,
            transition_time_seconds=120,
            remaining_seconds=1,
            phase_started_at=_utcnow_naive() - timedelta(seconds=600),
        ))
        db.commit()


# ── per_question answered flag ────────────────────────────────────────


def test_grading_per_question_answered_flag():
    result = grade_answers(CHOICE_FORM, {"question_1": "SCA"})
    per_q = result["per_question"]
    assert per_q["question_1"]["answered"] is True
    assert per_q["question_2"]["answered"] is False
    # Sin cambio de aritmética: single correcto suma 4, texto sigue pendiente.
    assert per_q["question_1"]["earned"] == 4
    assert per_q["question_2"]["earned"] is None
    assert result["auto_max"] == 4
    assert result["manual_max"] == 3


def test_grading_answered_flag_treats_empty_list_as_unanswered():
    result = grade_answers(
        {"questions": [{"type": "multiple_choice", "label": "x", "points": 2,
                        "correct_options": ["A"]}]},
        {"question_1": []},
    )
    assert result["per_question"]["question_1"]["answered"] is False


# ── submission_kind stamping ─────────────────────────────────────────


def test_manual_submission_kind_is_manual(auth_client):
    ctx = _build_event()
    checkin_id = _add_checkin(ctx)
    r = auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"],
        "student_id": ctx["student_id"],
        "answers": {"question_1": "SCA"},
    })
    assert r.status_code == 200, r.text
    with TestingSessionLocal() as db:
        resp = db.get(StudentResponse, r.json()["response_id"])
        assert resp.submission_kind == "manual"
        assert resp.by_contingency is False


def test_auto_submitted_blank_marked_but_scores_zero():
    ctx = _build_event(form=AUTO_ONLY_FORM)
    _add_running_expired_session(ctx)
    checkin_id = _add_checkin(ctx, minutes_ago=15)

    with TestingSessionLocal() as db:
        out = sweep_expired_phases(db, db.get(ECOEEvent, ctx["event_id"]))
    assert out == {"auto_responses": 1, "closed_checkins": 1}

    with TestingSessionLocal() as db:
        resp = db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        )
        assert resp.submission_kind == "auto"
        assert resp.answers == {}
        # D4: suma 0 sobre el máximo, no cambia la aritmética.
        assert resp.score_obtained == 0
        assert resp.max_score == 4
        assert resp.grading["question_1"]["answered"] is False
        assert db.get(StationCheckIn, checkin_id).status == "cerrado"
        row = next(
            r for r in compute_results(db, ctx["event_id"])
            if r["student_id"] == ctx["student_id"]
        )
        assert row["total_score"] == 0
        assert row["max_score"] == 4


def test_auto_submitted_blank_with_pending_manual_stays_unscored():
    ctx = _build_event()  # CHOICE_FORM: lleva una pregunta de texto con puntaje
    _add_running_expired_session(ctx)
    _add_checkin(ctx, minutes_ago=15)
    with TestingSessionLocal() as db:
        sweep_expired_phases(db, db.get(ECOEEvent, ctx["event_id"]))
    with TestingSessionLocal() as db:
        resp = db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        )
        assert resp.submission_kind == "auto"
        assert resp.score_obtained is None  # texto manual pendiente
        assert resp.max_score == 7
        assert resp.grading["question_1"]["answered"] is False
        assert resp.grading["question_2"]["answered"] is False


def test_submission_kind_not_client_settable(auth_client):
    """El cliente manda submission_kind pero el servidor lo ignora (negativo)."""
    ctx = _build_event()
    checkin_id = _add_checkin(ctx)
    # Envío manual normal donde el cliente intenta marcarlo como contingencia.
    r = auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"],
        "student_id": ctx["student_id"],
        "answers": {"question_1": "SCA"},
        "submission_kind": "contingency",
        "by_contingency": True,
    })
    assert r.status_code == 200, r.text
    with TestingSessionLocal() as db:
        resp = db.get(StudentResponse, r.json()["response_id"])
        assert resp.submission_kind == "manual"
        assert resp.by_contingency is False


def test_contingency_submission_kind_ignores_client_value(auth_client):
    ctx = _build_event()
    _add_checkin(ctx)
    r = auth_client.post("/api/contingency/student-response", json={
        "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"],
        "student_id": ctx["student_id"],
        "answers": {"question_1": "SCA"},
        "submission_kind": "manual",
    })
    assert r.status_code == 200, r.text
    with TestingSessionLocal() as db:
        resp = db.scalar(
            select(StudentResponse).where(
                StudentResponse.ecoe_event_id == ctx["event_id"]
            )
        )
        assert resp.submission_kind == "contingency"
        assert resp.by_contingency is True


# ── evaluator draft → draft_finalized (reconciliación F3, plan §"FASE 4") ──
#
# El evento demo (id 1) está en_ejecucion; eval1@ecoe.cl tiene la estación 1.
# El seed deja un EvaluatorRecord final para student 1, así que se usa student 2.


def _cleanup_event_1(student_ids: tuple[int, ...]) -> None:
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


def test_evaluator_draft_promoted_via_submit_is_draft_finalized(client):
    with TestingSessionLocal() as db:
        checkin = StationCheckIn(
            ecoe_event_id=1, station_id=1, student_id=2,
            evaluator_email="eval1@ecoe.cl", evaluator_name="Eval",
            status="confirmado", mode=SessionMode.ejecucion.value,
            confirmed_at=_utcnow_naive() - timedelta(minutes=1),
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        checkin_id = checkin.id
    try:
        login(client, EVALUATOR)
        draft = client.put("/api/evaluator/draft", json={
            "ecoe_event_id": 1, "station_id": 1, "student_id": 2,
            "checkin_id": checkin_id, "evaluator_name": "Camila Soto",
            "score_obtained": 6, "observation": "parcial", "answers": {},
        })
        assert draft.status_code == 200, draft.text
        record_id = draft.json()["record_id"]

        submit = client.post("/api/evaluator/submit", json={
            "checkin_id": checkin_id, "ecoe_event_id": 1, "station_id": 1,
            "student_id": 2, "evaluator_name": "Camila Soto",
            "score_obtained": 14, "max_score": 999, "observation": "final",
            "answers": {"item_scores": {"1": 2}},
        })
        assert submit.status_code == 200, submit.text
        with TestingSessionLocal() as db:
            record = db.get(EvaluatorRecord, record_id)
            assert record.is_draft is False
            assert record.submission_kind == "draft_finalized"
    finally:
        _cleanup_event_1((2,))


# ── traceability ─────────────────────────────────────────────────────


def test_traceability_flags_blank_auto_submissions():
    ctx = _build_event()
    _add_running_expired_session(ctx)
    _add_checkin(ctx, minutes_ago=15)
    with TestingSessionLocal() as db:
        sweep_expired_phases(db, db.get(ECOEEvent, ctx["event_id"]))

    with TestingSessionLocal() as db:
        report = build_traceability_report(db, ctx["event_id"])
    assert report["summary"]["blank_auto_submissions"] == 1
    student_row = report["student_traceability"][0]
    assert student_row["blank_auto_submissions"] == 1
    station_row = report["station_traceability"][0]
    assert station_row["blank_auto_submissions"] == 1
    entry = next(
        item for item in report["activity_log"]
        if item["type"] == "respuesta_estudiante"
    )
    assert entry["submission_kind"] == "auto"
    assert entry["answered"] is False
    assert "sin respuesta" in entry["label"].lower()


def test_traceability_manual_response_not_flagged_blank(auth_client):
    ctx = _build_event()
    checkin_id = _add_checkin(ctx)
    auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"],
        "student_id": ctx["student_id"],
        "answers": {"question_1": "SCA"},
    })
    with TestingSessionLocal() as db:
        report = build_traceability_report(db, ctx["event_id"])
    assert report["summary"]["blank_auto_submissions"] == 0
    assert report["student_traceability"][0]["blank_auto_submissions"] == 0
    entry = next(
        item for item in report["activity_log"]
        if item["type"] == "respuesta_estudiante"
    )
    assert entry["submission_kind"] == "manual"
    assert entry["answered"] is True


# ── export ───────────────────────────────────────────────────────────


def test_export_excel_includes_submission_kind_column():
    ctx = _build_event()
    _add_running_expired_session(ctx)
    _add_checkin(ctx, minutes_ago=15)
    with TestingSessionLocal() as db:
        sweep_expired_phases(db, db.get(ECOEEvent, ctx["event_id"]))

    with TestingSessionLocal() as db:
        content = export_results_excel(db, ctx["event_id"])
    sheets = pd.read_excel(BytesIO(content), sheet_name=None)
    assert "trazabilidad_envios" in sheets
    trace = sheets["trazabilidad_envios"]
    assert "origen" in trace.columns
    assert "en_blanco" in trace.columns
    row = trace.iloc[0]
    assert row["origen"] == "Automático"
    assert row["en_blanco"] == "Sí"
    # La hoja consolidado sigue siendo la primera y no cambió de forma.
    consolidado = pd.read_excel(BytesIO(content))
    assert "total_score" in consolidado.columns
