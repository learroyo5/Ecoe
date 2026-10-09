"""PROC-5 / PROC-13 / PROC-14 (auditoría de proceso 2026-10-09).

Candados por estado del ECOE sobre estructura y nómina, errores legibles al
borrar algo con registros y auditoría de los cambios de estructura.
"""

import pytest
from sqlalchemy import select

from app.models.entities import AuditLog, ECOEEvent, EvaluatorRecord, Station, Student
from app.models.enums import SessionMode
from conftest import TestingSessionLocal
from test_opt20_f2_deadline_and_sweep import _build_event

STRUCTURE_LOCKED = ["publicado", "en_ejecucion", "cerrado", "archivado"]
STRUCTURE_OPEN = ["borrador", "en_configuracion", "listo_para_pilotaje", "en_pilotaje", "pilotaje_validado"]


def _station_payload(ctx: dict, **overrides) -> dict:
    with TestingSessionLocal() as db:
        station = db.get(Station, ctx["station_id"])
        payload = {
            "ecoe_event_id": ctx["event_id"], "station_number": station.station_number,
            "name": station.name, "station_type": station.station_type,
            "circuit_name": station.circuit_name, "expected_outcomes": station.expected_outcomes,
            "student_activity": station.student_activity,
            "student_station_instruction": station.student_station_instruction,
            "pre_entry_instruction": station.pre_entry_instruction,
            "evaluator_instruction": station.evaluator_instruction,
            "max_score": station.max_score, "materials": "", "multimedia_notes": "",
            "requires_evaluator": station.requires_evaluator,
            "requires_student_form": station.requires_student_form,
            "uses_multimedia": False, "uses_simulated_patient": False,
            "uses_physical_resources": False, "contingency_ready": False,
            "student_form_definition": station.student_form_definition, "status": "en_diseno",
        }
    payload.update(overrides)
    return payload


def _event_payload(ctx: dict, **overrides) -> dict:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, ctx["event_id"])
        payload = {
            "name": event.name, "date": str(event.date), "course_name": event.course_name,
            "school_name": event.school_name, "responsible_teacher": event.responsible_teacher,
            "contact_email": event.contact_email, "circuit_mode": event.circuit_mode,
            "station_time_minutes": event.station_time_minutes,
            "transition_time_minutes": event.transition_time_minutes,
            "inter_round_pause_minutes": event.inter_round_pause_minutes,
            "total_groups": event.total_groups,
            "passing_reference_percent": event.passing_reference_percent,
            "status": str(event.status),
        }
    payload.update(overrides)
    return payload


def _add_evaluation(ctx: dict) -> None:
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=ctx["event_id"], station_id=ctx["station_id"],
            student_id=ctx["student_id"], mode=SessionMode.ejecucion.value,
            evaluator_name="Eval", score_obtained=1, max_score=4, is_draft=False,
        ))
        db.commit()


# ── Estructura: bloqueada desde `publicado` ───────────────────────────


@pytest.mark.parametrize("status", STRUCTURE_LOCKED)
def test_structure_is_locked_from_publication_onwards(auth_client, status):
    ctx = _build_event(status=status)
    event_id = ctx["event_id"]

    edited = auth_client.put(f"/api/stations/{ctx['station_id']}", json=_station_payload(ctx, max_score=999))
    assert edited.status_code == 409, edited.text
    assert auth_client.post("/api/stations", json=_station_payload(ctx, name="Nueva")).status_code == 409
    assert auth_client.delete(f"/api/stations/{ctx['station_id']}").status_code == 409
    assert auth_client.post(f"/api/students/{event_id}/renumber").status_code == 409
    assert auth_client.post(f"/api/students/{event_id}/deduplicate-rut").status_code == 409
    assert auth_client.delete(f"/api/students/{ctx['student_id']}").status_code == 409
    assert auth_client.patch(f"/api/ecoe/{event_id}/timing", json={
        "station_time_minutes": 3, "transition_time_minutes": 1, "sync_existing_stations": True,
    }).status_code == 409
    assert auth_client.put(
        f"/api/ecoe/{event_id}", json=_event_payload(ctx, station_time_minutes=3)
    ).status_code == 409
    assert auth_client.post(
        f"/api/media/upload?ecoe_event_id={event_id}&station_id={ctx['station_id']}",
        files={"file": ("a.png", b"\\x89PNG\\r\\n\\x1a\\n" + b"0" * 20, "image/png")},
    ).status_code == 409

    with TestingSessionLocal() as db:
        station = db.get(Station, ctx["station_id"])
        assert station is not None and station.max_score == 4
        assert db.get(Student, ctx["student_id"]).ecoe_number == "001"
        assert db.get(ECOEEvent, event_id).station_time_minutes == 8


@pytest.mark.parametrize("status", STRUCTURE_OPEN)
def test_structure_stays_editable_before_publication(auth_client, status):
    ctx = _build_event(status=status)
    edited = auth_client.put(f"/api/stations/{ctx['station_id']}", json=_station_payload(ctx, max_score=10))
    assert edited.status_code == 200, edited.text
    assert auth_client.post(f"/api/students/{ctx['event_id']}/renumber").status_code == 200


# ── Acta congelada ────────────────────────────────────────────────────


@pytest.mark.parametrize("status", ["cerrado", "archivado"])
def test_frozen_event_rejects_any_data_change(auth_client, status):
    ctx = _build_event(status=status)
    event_id = ctx["event_id"]

    renamed = auth_client.put(f"/api/ecoe/{event_id}", json=_event_payload(ctx, name="Otro nombre"))
    assert renamed.status_code == 409, renamed.text
    assert auth_client.put(
        f"/api/ecoe/{event_id}", json=_event_payload(ctx, passing_reference_percent=30)
    ).status_code == 409
    assert auth_client.patch(
        f"/api/students/{ctx['student_id']}/status", json={"is_active": False}
    ).status_code == 409
    assert auth_client.post("/api/students", json={
        "ecoe_event_id": event_id, "name": "Tardío", "last_name": "X", "rut": "1-9",
        "email": "tardio@example.edu", "group_name": "G1", "circuit_name": "Circuito A",
    }).status_code == 409
    assert auth_client.post("/api/staff", json={
        "ecoe_event_id": event_id, "name": "N", "last_name": "L",
        "email": "eval1@ecoe.cl", "role_code": "evaluador", "station_ids": [],
    }).status_code == 409

    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        assert event.name == "F2 deadline" and event.passing_reference_percent == 60
        assert db.get(Student, ctx["student_id"]).is_active is True


def test_running_event_still_accepts_what_the_day_needs(auth_client):
    """Negativo del candado: en ejecución se puede sumar a un rezagado, editar
    datos descriptivos y reenviar el formulario sin cambios de tiempos."""
    ctx = _build_event(status="en_ejecucion")
    event_id = ctx["event_id"]
    assert auth_client.post("/api/students", json={
        "ecoe_event_id": event_id, "name": "Rezagada", "last_name": "X", "rut": "2-7",
        "email": "rezagada@example.edu", "group_name": "G1", "circuit_name": "Circuito A",
    }).status_code == 200
    unchanged = auth_client.put(f"/api/ecoe/{event_id}", json=_event_payload(ctx))
    assert unchanged.status_code == 200, unchanged.text
    described = auth_client.put(
        f"/api/ecoe/{event_id}", json=_event_payload(ctx, responsible_teacher="Otra docente")
    )
    assert described.status_code == 200, described.text


def test_student_with_execution_records_cannot_be_suspended_mid_exam(auth_client):
    ctx = _build_event(status="en_ejecucion")
    _add_evaluation(ctx)
    response = auth_client.patch(
        f"/api/students/{ctx['student_id']}/status", json={"is_active": False}
    )
    assert response.status_code == 409
    with TestingSessionLocal() as db:
        assert db.get(Student, ctx["student_id"]).is_active is True


def test_absent_student_can_be_suspended_mid_exam(auth_client):
    ctx = _build_event(status="en_ejecucion")
    response = auth_client.patch(
        f"/api/students/{ctx['student_id']}/status", json={"is_active": False}
    )
    assert response.status_code == 200, response.text


# ── PROC-13: borrar con registros ─────────────────────────────────────


def test_deleting_with_records_is_a_readable_conflict_never_a_500(auth_client):
    ctx = _build_event(status="en_pilotaje")
    _add_evaluation(ctx)
    student = auth_client.delete(f"/api/students/{ctx['student_id']}")
    station = auth_client.delete(f"/api/stations/{ctx['station_id']}")
    # SQLite no aplica las FK: allí el borrado pasa. En PostgreSQL (CI) debe
    # ser un 409 con mensaje, nunca un 500.
    assert student.status_code in (200, 409), student.text
    assert station.status_code in (200, 409), station.text
    if student.status_code == 409:
        assert "suspéndelo" in student.json()["detail"]


# ── PROC-14: auditoría ────────────────────────────────────────────────


def test_structure_changes_leave_an_audit_trail(auth_client):
    ctx = _build_event(status="en_configuracion")
    auth_client.put(f"/api/stations/{ctx['station_id']}", json=_station_payload(ctx, max_score=10))
    auth_client.post(f"/api/students/{ctx['event_id']}/renumber")
    auth_client.patch(f"/api/students/{ctx['student_id']}/status", json={"is_active": False})
    auth_client.delete(f"/api/students/{ctx['student_id']}")

    with TestingSessionLocal() as db:
        logs = {
            log.action: log
            for log in db.scalars(select(AuditLog).where(AuditLog.action.in_([
                "update_station", "renumber_students", "update_student_status", "delete_student",
            ])).order_by(AuditLog.id.asc())).all()
            if (log.payload or {}).get("ecoe_event_id") == ctx["event_id"]
        }
    assert set(logs) == {"update_station", "renumber_students", "update_student_status", "delete_student"}
    assert "max_score" in logs["update_station"].payload["changed_fields"]
    assert logs["delete_student"].payload["ecoe_event_id"] == ctx["event_id"]


def test_unchanged_station_save_does_not_spam_the_audit_log(auth_client):
    ctx = _build_event(status="en_configuracion")
    with TestingSessionLocal() as db:
        before = len(db.scalars(select(AuditLog).where(AuditLog.action == "update_station")).all())
    first = auth_client.put(f"/api/stations/{ctx['station_id']}", json=_station_payload(ctx))
    assert first.status_code == 200, first.text
    second = auth_client.put(f"/api/stations/{ctx['station_id']}", json=first.json() | {"ecoe_event_id": ctx["event_id"]})
    assert second.status_code == 200, second.text
    with TestingSessionLocal() as db:
        after = len(db.scalars(select(AuditLog).where(AuditLog.action == "update_station")).all())
    assert after - before <= 1
