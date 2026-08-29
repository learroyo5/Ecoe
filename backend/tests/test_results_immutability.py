"""OPT-1 · Inmutabilidad de resultados tras el cierre.

Cubre:
- `/results` y el export Excel sirven el snapshot `ECOEResult` cuando el evento
  está `cerrado`/`archivado`, y recalculan en vivo antes del cierre.
- `grade_response` rechaza con 409 la corrección tardía sobre evento cerrado.
- `apply_manual_scores` rechaza con 409 la re-corrección de una pregunta ya
  resuelta y sigue resolviendo las pendientes.
- La consolidación (endpoint y rama de cierre) deja `AuditLog` con actor.
"""

from datetime import date, datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.entities import AuditLog, ECOEEvent, ECOEResult, Station, StationCheckIn, Student, StudentResponse
from app.models.enums import ECOEStatus
from app.services.grading import apply_manual_scores
from app.services.results import compute_results, read_results
from app.services.validation import update_ecoe_status
from conftest import ADMIN, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


AUTO_FORM = {
    "questions": [
        {
            "type": "single_choice",
            "label": "Conducta inmediata",
            "options": ["A", "B"],
            "points": 5,
            "correct_option": "A",
        },
    ]
}

MANUAL_FORM = {
    "questions": [
        {"type": "short_text", "label": "Justifica el plan", "points": 4},
    ]
}

TWO_MANUAL_FORM = {
    "questions": [
        {"type": "short_text", "label": "Pregunta 1", "points": 4},
        {"type": "short_text", "label": "Pregunta 2", "points": 4},
    ]
}


def _build_event(form_definition: dict, *, status: str = ECOEStatus.en_ejecucion.value):
    """Evento con una estación de formulario, un estudiante y un check-in confirmado."""
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Inmutabilidad",
            date=date(2026, 12, 10),
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
            name="Formulario",
            station_type="formulario_estudiante",
            circuit_name="Circuito A",
            station_time_minutes=8,
            transition_time_minutes=2,
            expected_outcomes="Resultado",
            student_activity="Actividad",
            pre_entry_instruction="Ingreso",
            evaluator_instruction="",
            requires_evaluator=False,
            requires_student_form=True,
            max_score=0,
            student_form_definition=form_definition,
        )
        db.add(station)
        db.flush()
        student = Student(
            ecoe_event_id=event.id,
            name="Alumno",
            last_name="Inmutable",
            rut=f"42{event.id}00-1",
            email=f"immut{event.id}@example.edu",
            ecoe_number="001",
            group_name="G1",
            circuit_name="Circuito A",
            is_active=True,
        )
        db.add(student)
        db.flush()
        checkin = StationCheckIn(
            ecoe_event_id=event.id,
            station_id=station.id,
            student_id=student.id,
            evaluator_email="eval1@ecoe.cl",
            evaluator_name="Evaluadora",
            status="confirmado",
            confirmed_at=_utcnow_naive(),
        )
        db.add(checkin)
        db.commit()
        return event.id, station.id, student.id, checkin.id


def _submit(client, event_id, station_id, student_id, checkin_id, answers):
    response = client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        "answers": answers,
    })
    assert response.status_code == 200, response.text
    return response.json()["response_id"]


def _set_status(event_id: int, status: str) -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        event.status = status
        db.add(event)
        db.commit()


def _close(event_id: int, actor_email: str = "admin@ecoe.cl") -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        update_ecoe_status(db, event, ECOEStatus.cerrado.value, actor_email=actor_email)


def _mutate_response_score(response_id: int, new_score: float) -> None:
    with TestingSessionLocal() as db:
        response = db.get(StudentResponse, response_id)
        response.score_obtained = new_score
        db.add(response)
        db.commit()


# ── (A) lectura: snapshot tras el cierre, recálculo antes ──────────────


def test_get_results_reads_snapshot_after_close(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_FORM)
    response_id = _submit(auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "A"})

    _close(event_id)
    # Se manipula el puntaje real después de consolidar.
    _mutate_response_score(response_id, 0)

    payload = auth_client.get(f"/api/results/{event_id}")
    assert payload.status_code == 200, payload.text
    body = payload.json()
    assert body["frozen"] is True
    assert body["consolidated_at"] is not None
    row = next(item for item in body["results"] if item["student_id"] == student_id)
    assert row["total_score"] == 5  # snapshot, no el 0 recalculado

    with TestingSessionLocal() as db:
        live = next(r for r in compute_results(db, event_id) if r["student_id"] == student_id)
    assert live["total_score"] == 0  # el recálculo en vivo sí ve la mutación


def test_get_results_recalculates_before_close(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_FORM)
    response_id = _submit(auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "A"})

    body = auth_client.get(f"/api/results/{event_id}").json()
    assert body["frozen"] is False
    assert body["consolidated_at"] is None
    assert next(r for r in body["results"] if r["student_id"] == student_id)["total_score"] == 5

    _mutate_response_score(response_id, 2)
    body = auth_client.get(f"/api/results/{event_id}").json()
    assert body["frozen"] is False
    assert next(r for r in body["results"] if r["student_id"] == student_id)["total_score"] == 2


def test_get_results_without_snapshot_falls_back_to_live(auth_client):
    """Evento cerrado sin `ECOEResult` (cierre previo a `persist_results`)."""
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_FORM)
    _submit(auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "A"})
    _set_status(event_id, ECOEStatus.cerrado.value)  # cierre "a mano", sin snapshot

    with TestingSessionLocal() as db:
        assert not db.scalars(select(ECOEResult).where(ECOEResult.ecoe_event_id == event_id)).all()

    body = auth_client.get(f"/api/results/{event_id}").json()
    assert body["frozen"] is False
    assert body["consolidated_at"] is None
    assert next(r for r in body["results"] if r["student_id"] == student_id)["total_score"] == 5


def test_export_excel_uses_snapshot_after_close(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_FORM)
    response_id = _submit(auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "A"})
    _close(event_id)
    _mutate_response_score(response_id, 0)

    export = auth_client.get(f"/api/results/{event_id}/export/excel")
    assert export.status_code == 200
    # OPT-19: el Excel es multi-hoja (`metadatos` es la primera); el consolidado
    # vive en la hoja `consolidado`.
    df = pd.read_excel(BytesIO(export.content), sheet_name="consolidado")
    exported = df[df["student_id"] == student_id]["total_score"].iloc[0]

    with TestingSessionLocal() as db:
        snap = db.scalar(
            select(ECOEResult).where(
                ECOEResult.ecoe_event_id == event_id,
                ECOEResult.student_id == student_id,
            )
        )
    assert exported == snap.total_score == 5


def test_read_results_helper_shapes_match(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_FORM)
    _submit(auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "A"})
    _close(event_id)
    with TestingSessionLocal() as db:
        frozen_rows, frozen, consolidated_at = read_results(db, event_id)
    assert frozen is True
    assert consolidated_at is not None
    assert set(frozen_rows[0]) == {
        "student_id", "student_name", "ecoe_number",
        "total_score", "max_score", "percentage", "equivalent_grade",
    }


# ── (B) gate de estado en grade_response ──────────────────────────────


def test_grade_response_rejected_after_close(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(MANUAL_FORM)
    response_id = _submit(
        auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "texto"}
    )

    _set_status(event_id, ECOEStatus.cerrado.value)
    rejected = auth_client.post(
        f"/api/grading/responses/{response_id}", json={"scores": {"question_1": 3}}
    )
    assert rejected.status_code == 409, rejected.text

    _set_status(event_id, ECOEStatus.archivado.value)
    rejected_archived = auth_client.post(
        f"/api/grading/responses/{response_id}", json={"scores": {"question_1": 3}}
    )
    assert rejected_archived.status_code == 409, rejected_archived.text

    with TestingSessionLocal() as db:
        assert db.get(StudentResponse, response_id).score_obtained is None


def test_grade_response_allowed_before_close(auth_client):
    for status in (ECOEStatus.en_ejecucion.value, ECOEStatus.en_pilotaje.value):
        event_id, station_id, student_id, checkin_id = _build_event(MANUAL_FORM, status=status)
        response_id = _submit(
            auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "texto"}
        )
        graded = auth_client.post(
            f"/api/grading/responses/{response_id}", json={"scores": {"question_1": 3}}
        )
        assert graded.status_code == 200, f"{status}: {graded.text}"
        assert graded.json()["score_obtained"] == 3


# ── (C) guard de re-corrección en apply_manual_scores ─────────────────


def _fake_response(grading: dict, score_obtained):
    return SimpleNamespace(
        grading=grading,
        score_obtained=score_obtained,
        graded_by_email="prev@ecoe.cl" if score_obtained is not None else None,
        graded_at=_utcnow_naive() if score_obtained is not None else None,
    )


def test_apply_manual_scores_rejects_regrade_of_resolved_question():
    response = _fake_response(
        {
            "question_1": {"kind": "manual", "earned": 2.0, "max": 4},
            "question_2": {"kind": "auto", "earned": 5.0, "max": 5},
        },
        score_obtained=7.0,
    )
    with pytest.raises(HTTPException) as exc:
        apply_manual_scores(response, {"question_1": 4.0}, graded_by_email="new@ecoe.cl")
    assert exc.value.status_code == 409
    # El puntaje original queda intacto.
    assert response.score_obtained == 7.0
    assert response.grading["question_1"]["earned"] == 2.0
    assert response.graded_by_email == "prev@ecoe.cl"


def test_apply_manual_scores_still_resolves_remaining():
    response = _fake_response(
        {
            "question_1": {"kind": "manual", "earned": 3.0, "max": 4},
            "question_2": {"kind": "manual", "earned": None, "max": 4},
        },
        score_obtained=None,
    )
    apply_manual_scores(response, {"question_2": 2.0}, graded_by_email="new@ecoe.cl")
    assert response.grading["question_1"]["earned"] == 3.0
    assert response.grading["question_2"]["earned"] == 2.0
    assert response.score_obtained == 5.0
    assert response.graded_by_email == "new@ecoe.cl"


def test_apply_manual_scores_regrade_rejected_via_endpoint(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(MANUAL_FORM)
    response_id = _submit(
        auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "texto"}
    )
    first = auth_client.post(
        f"/api/grading/responses/{response_id}", json={"scores": {"question_1": 2.5}}
    )
    assert first.status_code == 200, first.text

    regrade = auth_client.post(
        f"/api/grading/responses/{response_id}", json={"scores": {"question_1": 4}}
    )
    assert regrade.status_code == 409, regrade.text
    with TestingSessionLocal() as db:
        assert db.get(StudentResponse, response_id).score_obtained == 2.5


def test_apply_manual_scores_resolves_remaining_via_endpoint(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(TWO_MANUAL_FORM)
    response_id = _submit(
        auth_client,
        event_id,
        station_id,
        student_id,
        checkin_id,
        {"question_1": "uno", "question_2": "dos"},
    )
    both = auth_client.post(
        f"/api/grading/responses/{response_id}",
        json={"scores": {"question_1": 4, "question_2": 3}},
    )
    assert both.status_code == 200, both.text
    assert both.json()["score_obtained"] == 7


# ── (D) AuditLog en la consolidación ─────────────────────────────────


def test_consolidate_endpoint_writes_audit_log(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_FORM)
    _submit(auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "A"})

    result = auth_client.post(f"/api/results/{event_id}/consolidate")
    assert result.status_code == 200, result.text

    with TestingSessionLocal() as db:
        entry = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "consolidate_results",
                AuditLog.target_id == str(event_id),
            )
        )
    assert entry is not None
    assert entry.user_email == "admin@ecoe.cl"
    assert entry.payload["student_count"] == 1


def test_close_branch_writes_consolidation_audit_log(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_FORM)
    _submit(auth_client, event_id, station_id, student_id, checkin_id, {"question_1": "A"})

    _close(event_id, actor_email="admin@ecoe.cl")

    with TestingSessionLocal() as db:
        entry = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "consolidate_results",
                AuditLog.target_id == str(event_id),
            )
        )
    assert entry is not None
    assert entry.user_email == "admin@ecoe.cl"


def test_get_results_requires_event_access(client):
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_FORM)
    login(client, ("student1@ecoe.cl", "test-student-password"))
    denied = client.get(f"/api/results/{event_id}")
    assert denied.status_code in (401, 403)
