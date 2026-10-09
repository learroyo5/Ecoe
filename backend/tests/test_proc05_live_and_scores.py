"""PROC-9 / PROC-10 / PROC-24 y guarda de consolidación (auditoría 2026-10-09)."""

from datetime import date

from sqlalchemy import select

from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEEvent,
    EvaluatorRecord,
    LiveSession,
    PilotRun,
    StaffAssignment,
    Station,
    Student,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.validation import update_ecoe_status
from conftest import TestingSessionLocal
from test_opt20_f2_deadline_and_sweep import _add_checkin, _build_event


def _control(client, event_id: int, action: str):
    return client.post("/api/live/control", json={"ecoe_event_id": event_id, "action": action})


def _live(client, event_id: int) -> dict:
    return client.get(f"/api/live/{event_id}").json()


# ── PROC-9 / PROC-24: reloj ───────────────────────────────────────────


def test_resume_on_a_session_that_never_started_is_rejected(auth_client):
    ctx = _build_event()
    assert _control(auth_client, ctx["event_id"], "reset").status_code == 200
    response = _control(auth_client, ctx["event_id"], "resume")
    assert response.status_code == 409
    assert _live(auth_client, ctx["event_id"])["status"] == "ready"


def test_pause_without_a_running_phase_is_rejected(auth_client):
    ctx = _build_event()
    _control(auth_client, ctx["event_id"], "reset")
    assert _control(auth_client, ctx["event_id"], "pause").status_code == 409


def test_pausing_a_transition_resumes_the_transition_not_a_station(auth_client):
    ctx = _build_event()
    with TestingSessionLocal() as db:  # segunda estación para poder avanzar
        db.add(Station(
            ecoe_event_id=ctx["event_id"], station_number=2, name="E2",
            station_type="procedimental", circuit_name="Circuito A",
            station_time_minutes=8, transition_time_minutes=2, expected_outcomes="r",
            student_activity="a", pre_entry_instruction="i", student_station_instruction="d",
            evaluator_instruction="e", requires_evaluator=True, max_score=4,
        ))
        db.commit()
    event_id = ctx["event_id"]
    _control(auth_client, event_id, "start")
    assert _control(auth_client, event_id, "next_transition").json()["status"] == "transition"
    assert _control(auth_client, event_id, "pause").json()["status"] == "paused"

    resumed = _control(auth_client, event_id, "resume").json()
    assert resumed["status"] == "transition"
    assert resumed["current_station_index"] == 2
    assert resumed["remaining_seconds"] <= 120


def test_pausing_a_station_still_resumes_to_running(auth_client):
    ctx = _build_event()
    _control(auth_client, ctx["event_id"], "start")
    _control(auth_client, ctx["event_id"], "pause")
    assert _control(auth_client, ctx["event_id"], "resume").json()["status"] == "running"


def _publishable_event() -> int:
    """Evento `publicado` listo para iniciar, con una sesión en vivo heredada
    del pilotaje en mal estado."""
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Herencia", date=date(2026, 12, 20), course_name="C", school_name="E",
            responsible_teacher="D", contact_email="d@example.edu",
            circuit_mode="secuencial", total_stations=1, station_time_minutes=6,
            transition_time_minutes=1, total_students=1, total_groups=1,
            passing_reference_percent=60, status=ECOEStatus.publicado.value,
        )
        db.add(event)
        db.flush()
        tool = AssessmentTool(name="Pauta herencia", tool_type="lista_cotejo", max_score=4)
        db.add(tool)
        db.flush()
        db.add(AssessmentItem(tool_id=tool.id, label="c1", score_per_item=4, order_index=1))
        station = Station(
            ecoe_event_id=event.id, station_number=1, name="E1", station_type="procedimental",
            circuit_name="Circuito A", station_time_minutes=6, transition_time_minutes=1,
            expected_outcomes="r", student_activity="a", pre_entry_instruction="i",
            student_station_instruction="d", evaluator_instruction="e",
            requires_evaluator=True, max_score=4, assessment_tool_id=tool.id, materials="m",
        )
        db.add(station)
        db.flush()
        db.add(Student(
            ecoe_event_id=event.id, name="A", last_name="B", rut=f"h{event.id}",
            email=f"h{event.id}@e.edu", ecoe_number="E001", group_name="G1",
            circuit_name="Circuito A", is_active=True,
        ))
        db.add(StaffAssignment(
            ecoe_event_id=event.id, name="Ev", last_name="X", email="eval1@ecoe.cl",
            role_code="evaluador", station_ids=[station.id],
        ))
        db.add(PilotRun(ecoe_event_id=event.id, name="Piloto", scope="circuito_completo"))
        db.add(LiveSession(
            ecoe_event_id=event.id, mode=SessionMode.pilotaje.value, status="circuit_complete",
            station_time_seconds=999, transition_time_seconds=999, current_station_index=5,
            remaining_seconds=0, phase_started_at=None, auto_mode=True,
            current_round=3, total_rounds=3,
        ))
        db.commit()
        return event.id


def test_starting_execution_resets_the_live_session_left_by_the_pilot():
    event_id = _publishable_event()
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        update_ecoe_status(db, event, ECOEStatus.en_ejecucion.value, actor_email="a@e.cl")
        session = db.scalar(select(LiveSession).where(LiveSession.ecoe_event_id == event_id))
        assert session.status == "ready"
        assert session.current_station_index == 1
        assert session.auto_mode is False
        assert (session.current_round, session.total_rounds) == (1, None)
        assert session.station_time_seconds == 360
        assert session.transition_time_seconds == 60
        assert session.remaining_seconds == 360


def test_reopening_a_closed_event_does_not_reset_the_live_session():
    """Negativo: sólo publicado → en_ejecucion limpia el reloj."""
    ctx = _build_event(status=ECOEStatus.cerrado.value)
    with TestingSessionLocal() as db:
        db.add(LiveSession(
            ecoe_event_id=ctx["event_id"], status="paused", station_time_seconds=480,
            transition_time_seconds=120, current_station_index=3, remaining_seconds=77,
        ))
        db.commit()
        event = db.get(ECOEEvent, ctx["event_id"])
        update_ecoe_status(
            db, event, ECOEStatus.en_ejecucion.value, actor_email="a@e.cl",
            transition_reason="Faltó transcribir una pauta en papel",
        )
        session = db.scalar(select(LiveSession).where(LiveSession.ecoe_event_id == ctx["event_id"]))
        assert (session.status, session.current_station_index, session.remaining_seconds) == (
            "paused", 3, 77)


# ── PROC-10: puntaje del evaluador ────────────────────────────────────


def _event_with_rubric() -> dict:
    ctx = _build_event()
    with TestingSessionLocal() as db:
        tool = AssessmentTool(name=f"Pauta {ctx['event_id']}", tool_type="lista_cotejo", max_score=10)
        db.add(tool)
        db.flush()
        first = AssessmentItem(tool_id=tool.id, label="Lavado de manos", score_per_item=2, order_index=1)
        second = AssessmentItem(tool_id=tool.id, label="Técnica", score_per_item=8, order_index=2)
        db.add_all([first, second])
        station = db.get(Station, ctx["station_id"])
        station.assessment_tool_id = tool.id
        db.commit()
        ctx["items"] = (first.id, second.id)
    ctx["checkin_id"] = _add_checkin(ctx, minutes_ago=0)
    return ctx


def _submit(client, ctx: dict, score: float, item_scores: dict | None):
    return client.post("/api/evaluator/submit", json={
        "checkin_id": ctx["checkin_id"], "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"], "student_id": ctx["student_id"],
        "evaluator_name": "Eval", "score_obtained": score, "max_score": 10,
        "answers": {} if item_scores is None else {"item_scores": item_scores},
    })


def _saved_score(ctx: dict):
    with TestingSessionLocal() as db:
        record = db.scalar(select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == ctx["event_id"]))
        return None if record is None else record.score_obtained


def test_total_that_contradicts_the_rubric_breakdown_is_rejected(auth_client):
    ctx = _event_with_rubric()
    first, second = ctx["items"]
    response = _submit(auth_client, ctx, 10, {str(first): 0, str(second): 0})
    assert response.status_code == 400
    assert "no coincide" in response.json()["detail"]
    assert _saved_score(ctx) is None


def test_criterion_above_its_maximum_or_foreign_to_the_rubric_is_rejected(auth_client):
    ctx = _event_with_rubric()
    first, second = ctx["items"]
    assert _submit(auth_client, ctx, 10, {str(first): 5, str(second): 5}).status_code == 400
    assert _submit(auth_client, ctx, 2, {"999999": 2}).status_code == 400
    assert _submit(auth_client, ctx, -1, {str(first): -1}).status_code == 400
    assert _saved_score(ctx) is None


def test_consistent_breakdown_is_accepted(auth_client):
    ctx = _event_with_rubric()
    first, second = ctx["items"]
    response = _submit(auth_client, ctx, 8, {str(first): 2, str(second): 6})
    assert response.status_code == 200, response.text
    assert _saved_score(ctx) == 8


def test_draft_score_is_recomputed_from_the_breakdown(auth_client):
    ctx = _event_with_rubric()
    first, second = ctx["items"]
    response = auth_client.put("/api/evaluator/draft", json={
        "checkin_id": ctx["checkin_id"], "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["station_id"], "student_id": ctx["student_id"],
        "evaluator_name": "Eval", "score_obtained": 10, "observation": "",
        "answers": {"item_scores": {str(first): 2, str(second): 1}},
    })
    assert response.status_code == 200, response.text
    assert _saved_score(ctx) == 3


# ── Consolidación manual ──────────────────────────────────────────────


def test_manual_consolidation_cannot_rewrite_a_closed_acta(auth_client):
    ctx = _build_event(status=ECOEStatus.cerrado.value)
    response = auth_client.post(f"/api/results/{ctx['event_id']}/consolidate")
    assert response.status_code == 409


# ── PROC-11: circuitos espejo ─────────────────────────────────────────


def _mirror_event(students_a: int, students_b: int) -> dict:
    from app.services.live_cycle import compute_total_rounds, station_slot_count  # noqa: F401

    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Espejo", date=date(2026, 12, 20), course_name="C", school_name="E",
            responsible_teacher="D", contact_email="d@example.edu",
            circuit_mode="paralelo_espejo", total_stations=1, station_time_minutes=8,
            transition_time_minutes=2, total_students=1, total_groups=2,
            passing_reference_percent=60, status=ECOEStatus.en_ejecucion.value,
        )
        db.add(event)
        db.flush()
        stations: dict[str, list[int]] = {"Circuito A": [], "Circuito B": []}
        number = 0
        for circuit in stations:
            for _ in range(3):
                number += 1
                station = Station(
                    ecoe_event_id=event.id, station_number=number, name=f"E{number}",
                    station_type="procedimental", circuit_name=circuit,
                    station_time_minutes=8, transition_time_minutes=2, expected_outcomes="r",
                    student_activity="a", pre_entry_instruction="i",
                    student_station_instruction="d", evaluator_instruction="e",
                    requires_evaluator=True, max_score=10,
                )
                db.add(station)
                db.flush()
                stations[circuit].append(station.id)
        index = 0
        for circuit, count in (("Circuito A", students_a), ("Circuito B", students_b)):
            for _ in range(count):
                index += 1
                db.add(Student(
                    ecoe_event_id=event.id, name=f"S{index}", last_name="X",
                    rut=f"m{event.id}-{index}", email=f"m{event.id}-{index}@e.edu",
                    ecoe_number=f"E{index:03d}", group_name="G", circuit_name=circuit,
                    is_active=True,
                ))
        db.commit()
        return {"event_id": event.id, "stations": stations}


def test_mirror_circuits_run_in_parallel_for_the_auto_cycle():
    from app.services.live_cycle import compute_total_rounds, station_slot_count

    ctx = _mirror_event(students_a=5, students_b=3)
    with TestingSessionLocal() as db:
        # 6 estaciones en dos circuitos de 3: una ronda son 3 fases, no 6.
        assert station_slot_count(db, ctx["event_id"]) == 3
        # A necesita ⌈5/3⌉ = 2 rondas, B sólo 1: manda el que más necesita.
        assert compute_total_rounds(db, ctx["event_id"]) == 2


def test_single_circuit_keeps_the_previous_round_math():
    from app.services.live_cycle import compute_total_rounds, station_slot_count

    ctx = _build_event()
    with TestingSessionLocal() as db:
        assert station_slot_count(db, ctx["event_id"]) == 1
        assert compute_total_rounds(db, ctx["event_id"]) == 1


def test_checkin_of_a_student_from_the_other_circuit_is_flagged(auth_client):
    ctx = _mirror_event(students_a=1, students_b=1)
    station_b = ctx["stations"]["Circuito B"][0]
    body = {"ecoe_event_id": ctx["event_id"], "station_id": station_b, "ecoe_number": "E001"}

    response = auth_client.post("/api/station-checkins/confirm", json=body)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "student_other_circuit"

    confirmed = auth_client.post(
        "/api/station-checkins/confirm", json=body | {"confirm_other_circuit": True}
    )
    assert confirmed.status_code == 200, confirmed.text


def test_checkin_in_the_students_own_circuit_is_not_flagged(auth_client):
    ctx = _mirror_event(students_a=1, students_b=1)
    response = auth_client.post("/api/station-checkins/confirm", json={
        "ecoe_event_id": ctx["event_id"],
        "station_id": ctx["stations"]["Circuito A"][0],
        "ecoe_number": "E001",
    })
    assert response.status_code == 200, response.text


# ── PROC-16: validación ───────────────────────────────────────────────


def test_station_nobody_can_score_blocks_readiness():
    from app.services.validation import compute_ecoe_validation

    ctx = _build_event(status=ECOEStatus.en_configuracion.value)
    with TestingSessionLocal() as db:
        station = db.get(Station, ctx["station_id"])
        station.requires_evaluator = False
        station.requires_student_form = False
        db.commit()
        validation = compute_ecoe_validation(db, db.get(ECOEEvent, ctx["event_id"]))
    issue = validation["station_issues"][0]
    assert any("nada puede calificar" in blocker for blocker in issue["blockers"])
    assert validation["can_pilot"] is False


def test_publication_requires_active_students():
    from app.services.validation import compute_ecoe_validation

    ctx = _build_event(status=ECOEStatus.pilotaje_validado.value)
    with TestingSessionLocal() as db:
        student = db.get(Student, ctx["student_id"])
        student.is_active = False
        db.commit()
        validation = compute_ecoe_validation(db, db.get(ECOEEvent, ctx["event_id"]))
    assert validation["can_publish"] is False


def test_validation_warns_about_stations_that_need_a_manual_checkin():
    from app.services.validation import compute_ecoe_validation

    ctx = _build_event(status=ECOEStatus.en_configuracion.value)
    with TestingSessionLocal() as db:
        station = db.get(Station, ctx["station_id"])
        station.requires_evaluator = False
        db.commit()
        validation = compute_ecoe_validation(db, db.get(ECOEEvent, ctx["event_id"]))
    assert any("Estaciones sin evaluador" in warning for warning in validation["warnings"])
