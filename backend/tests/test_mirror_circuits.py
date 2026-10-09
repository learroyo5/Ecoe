"""Circuitos espejo: creación, sincronía, validación, resultados y análisis."""

from datetime import date

import pytest
from sqlalchemy import select

from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEEvent,
    EvaluatorRecord,
    MediaAsset,
    StaffAssignment,
    Station,
    Student,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.live_cycle import compute_total_rounds, station_slot_count
from app.services.mirrors import mirror_structure_issues
from app.services.psychometrics import build_psychometrics_block
from app.services.results import compute_missing_station_scores, compute_results
from app.services.validation import compute_ecoe_validation
from conftest import ADMIN, EVALUATOR, TestingSessionLocal, login


def _event(*, stations: int = 4, students_per_circuit: int = 0, status: str = "en_configuracion") -> dict:
    """Evento con un circuito A de `stations` estaciones con pauta (máx 10)."""
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Espejo", date=date(2026, 12, 20), course_name="C", school_name="E",
            responsible_teacher="D", contact_email="d@example.edu",
            circuit_mode="paralelo_espejo", total_stations=1, station_time_minutes=8,
            transition_time_minutes=2, total_students=1, total_groups=2,
            passing_reference_percent=60, status=status,
        )
        db.add(event)
        db.flush()
        tool = AssessmentTool(name=f"Pauta espejo {event.id}", tool_type="lista_cotejo", max_score=10)
        db.add(tool)
        db.flush()
        db.add(AssessmentItem(tool_id=tool.id, label="Criterio", score_per_item=10, order_index=1))
        ids = []
        for number in range(1, stations + 1):
            station = Station(
                ecoe_event_id=event.id, station_number=number, name=f"Estación {number}",
                station_type="procedimental", circuit_name="Circuito A",
                station_time_minutes=8, transition_time_minutes=2,
                assessment_tool_id=tool.id, expected_outcomes="r", student_activity="a",
                pre_entry_instruction="i", student_station_instruction="d",
                evaluator_instruction="e", requires_evaluator=True, max_score=10, materials="m",
            )
            db.add(station)
            db.flush()
            ids.append(station.id)
        student_ids: dict[str, list[int]] = {"Circuito A": [], "Circuito B": []}
        index = 0
        for circuit in ("Circuito A", "Circuito B"):
            for _ in range(students_per_circuit):
                index += 1
                student = Student(
                    ecoe_event_id=event.id, name=f"S{index}", last_name="X",
                    rut=f"mc{event.id}-{index}", email=f"mc{event.id}-{index}@e.edu",
                    ecoe_number=f"E{index:03d}", group_name="G", circuit_name=circuit,
                    is_active=True,
                )
                db.add(student)
                db.flush()
                student_ids[circuit].append(student.id)
        db.commit()
        return {"event_id": event.id, "a": ids, "students": student_ids, "tool_id": tool.id}


def _mirror(client, ctx: dict, source="Circuito A", target="Circuito B"):
    return client.post(f"/api/ecoe/{ctx['event_id']}/circuits/mirror",
                       json={"source_circuit": source, "mirror_circuit": target})


def _stations(ctx: dict) -> list[Station]:
    with TestingSessionLocal() as db:
        return list(db.scalars(select(Station).where(
            Station.ecoe_event_id == ctx["event_id"]).order_by(Station.station_number)))


def _payload(station: Station, **overrides) -> dict:
    payload = {
        "ecoe_event_id": station.ecoe_event_id, "template_id": station.template_id,
        "assessment_tool_id": station.assessment_tool_id,
        "simulated_patient_id": station.simulated_patient_id,
        "station_number": station.station_number, "name": station.name,
        "station_type": station.station_type, "circuit_name": station.circuit_name,
        "expected_outcomes": station.expected_outcomes, "student_activity": station.student_activity,
        "student_station_instruction": station.student_station_instruction,
        "pre_entry_instruction": station.pre_entry_instruction,
        "evaluator_instruction": station.evaluator_instruction,
        "requires_evaluator": station.requires_evaluator,
        "requires_student_form": station.requires_student_form,
        "requires_deferred_grading": station.requires_deferred_grading,
        "uses_multimedia": station.uses_multimedia,
        "uses_simulated_patient": station.uses_simulated_patient,
        "uses_physical_resources": station.uses_physical_resources,
        "max_score": station.max_score, "materials": station.materials,
        "clinical_equipment": station.clinical_equipment, "simulator": station.simulator,
        "ambience": station.ambience, "multimedia_notes": station.multimedia_notes,
        "student_form_definition": station.student_form_definition or {},
        "contingency_ready": station.contingency_ready, "status": str(station.status),
    }
    payload.update(overrides)
    return payload


# ── Crear y mantener el espejo ────────────────────────────────────────


def test_mirror_circuit_clones_every_station_with_the_same_design(auth_client):
    ctx = _event()
    response = _mirror(auth_client, ctx)
    assert response.status_code == 200, response.text
    stations = _stations(ctx)
    assert len(stations) == 8
    mirrors = [s for s in stations if s.mirror_of_id]
    assert {m.mirror_of_id for m in mirrors} == set(ctx["a"])
    assert {m.circuit_name for m in mirrors} == {"Circuito B"}
    by_id = {s.id: s for s in stations}
    for mirror in mirrors:
        original = by_id[mirror.mirror_of_id]
        assert (mirror.name, mirror.assessment_tool_id, mirror.max_score) == (
            original.name, original.assessment_tool_id, original.max_score)
    with TestingSessionLocal() as db:
        assert mirror_structure_issues(db, ctx["event_id"]) == []


def test_mirroring_twice_is_idempotent_and_completes_a_new_station(auth_client):
    ctx = _event(stations=2)
    _mirror(auth_client, ctx)
    assert _mirror(auth_client, ctx).status_code == 200
    assert len(_stations(ctx)) == 4

    # Se agrega una estación al circuito original: el espejo queda incompleto…
    original = _stations(ctx)[0]
    created = auth_client.post("/api/stations", json=_payload(original, name="Nueva", station_number=99))
    assert created.status_code == 200, created.text
    with TestingSessionLocal() as db:
        issues = mirror_structure_issues(db, ctx["event_id"])
    assert len(issues) == 1 and "faltan estaciones espejo" in issues[0]
    # …hasta sincronizar.
    assert _mirror(auth_client, ctx).status_code == 200
    assert len(_stations(ctx)) == 6
    with TestingSessionLocal() as db:
        assert mirror_structure_issues(db, ctx["event_id"]) == []


def test_editing_the_original_updates_its_mirror(auth_client):
    ctx = _event(stations=1)
    _mirror(auth_client, ctx)
    original = _stations(ctx)[0]
    response = auth_client.put(
        f"/api/stations/{original.id}",
        json=_payload(original, evaluator_instruction="Nueva guía", max_score=15),
    )
    assert response.status_code == 200, response.text
    mirror = [s for s in _stations(ctx) if s.mirror_of_id][0]
    assert mirror.evaluator_instruction == "Nueva guía" and mirror.max_score == 15


def test_a_mirror_station_cannot_be_designed_on_its_own(auth_client):
    ctx = _event(stations=1)
    _mirror(auth_client, ctx)
    mirror = [s for s in _stations(ctx) if s.mirror_of_id][0]

    changed = auth_client.put(f"/api/stations/{mirror.id}", json=_payload(mirror, max_score=99))
    assert changed.status_code == 409
    assert "Edita la original" in changed.json()["detail"]
    assert auth_client.delete(f"/api/stations/{mirror.id}").status_code == 409
    new_in_mirror = auth_client.post(
        "/api/stations", json=_payload(mirror, name="Suelta", station_number=50))
    assert new_in_mirror.status_code == 409
    upload = auth_client.post(
        f"/api/media/upload?ecoe_event_id={ctx['event_id']}&station_id={mirror.id}",
        files={"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")},
    )
    assert upload.status_code == 409
    assert [s for s in _stations(ctx) if s.mirror_of_id][0].max_score == 10


def test_saving_a_mirror_without_design_changes_is_allowed(auth_client):
    """Lo propio de la estación física (p. ej. otro paciente simulado) sí se guarda."""
    ctx = _event(stations=1)
    _mirror(auth_client, ctx)
    mirror = [s for s in _stations(ctx) if s.mirror_of_id][0]
    assert auth_client.put(f"/api/stations/{mirror.id}", json=_payload(mirror)).status_code == 200


def test_mirror_circuit_can_be_removed_whole_but_not_the_original(auth_client):
    ctx = _event(stations=2)
    _mirror(auth_client, ctx)
    refused = auth_client.delete(f"/api/ecoe/{ctx['event_id']}/circuits/mirror?circuit=Circuito A")
    assert refused.status_code == 409
    removed = auth_client.delete(f"/api/ecoe/{ctx['event_id']}/circuits/mirror?circuit=Circuito B")
    assert removed.status_code == 200 and removed.json()["deleted"] == 2
    assert len(_stations(ctx)) == 2


def test_mirror_creation_is_locked_after_publication_and_needs_permission(client, auth_client):
    ctx = _event(stations=1, status=ECOEStatus.publicado.value)
    assert _mirror(auth_client, ctx).status_code == 409
    open_ctx = _event(stations=1)
    login(client, EVALUATOR)
    assert _mirror(client, open_ctx).status_code == 403
    login(client, ADMIN)


def test_a_circuit_that_is_already_a_mirror_cannot_be_the_source(auth_client):
    ctx = _event(stations=1)
    _mirror(auth_client, ctx)
    assert _mirror(auth_client, ctx, source="Circuito B", target="Circuito C").status_code == 409
    assert _mirror(auth_client, ctx, source="Circuito A", target="Circuito A").status_code == 400


# ── Validación ────────────────────────────────────────────────────────


def test_two_hand_made_circuits_block_readiness(auth_client):
    ctx = _event(stations=2, students_per_circuit=1)
    with TestingSessionLocal() as db:
        second = db.get(Station, ctx["a"][1])
        second.circuit_name = "Circuito B"  # dos circuitos armados a mano
        db.commit()
        validation = compute_ecoe_validation(db, db.get(ECOEEvent, ctx["event_id"]))
    assert validation["mirrors_ready"] is False
    assert validation["can_pilot"] is False and validation["can_publish"] is False
    assert any("Crear circuito espejo" in blocker for blocker in validation["blockers"])


def test_a_drifted_mirror_blocks_readiness(auth_client):
    ctx = _event(stations=1)
    _mirror(auth_client, ctx)
    with TestingSessionLocal() as db:
        mirror = db.scalar(select(Station).where(
            Station.ecoe_event_id == ctx["event_id"], Station.mirror_of_id.is_not(None)))
        mirror.max_score = 3  # alguien lo alteró por fuera de la API
        db.commit()
        issues = mirror_structure_issues(db, ctx["event_id"])
    assert len(issues) == 1 and "max_score" in issues[0]


def test_single_circuit_events_are_unaffected():
    ctx = _event(stations=3)
    with TestingSessionLocal() as db:
        assert mirror_structure_issues(db, ctx["event_id"]) == []


# ── Operación y resultados ────────────────────────────────────────────


def _score(ctx: dict, student_id: int, station_id: int, obtained: float) -> None:
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=ctx["event_id"], station_id=station_id, student_id=student_id,
            mode=SessionMode.ejecucion.value, evaluator_name="E", score_obtained=obtained,
            max_score=10, is_draft=False, answers={"item_scores": {}},
        ))
        db.commit()


def _mirrored_event_with_scores(auth_client) -> dict:
    """4 estaciones × 2 circuitos, 3 estudiantes por circuito, todo evaluado."""
    ctx = _event(stations=4, students_per_circuit=3)
    assert _mirror(auth_client, ctx).status_code == 200
    stations = _stations(ctx)
    ctx["b"] = [s.id for s in stations if s.mirror_of_id]
    scores = [10, 8, 6, 4]
    for circuit, station_ids in (("Circuito A", ctx["a"]), ("Circuito B", ctx["b"])):
        for offset, student_id in enumerate(ctx["students"][circuit]):
            for index, station_id in enumerate(station_ids):
                bonus = 0 if circuit == "Circuito A" else -2
                _score(ctx, student_id, station_id, max(0, scores[(index + offset) % 4] + bonus))
    return ctx


def test_rounds_and_expected_stations_follow_each_circuit(auth_client):
    ctx = _mirrored_event_with_scores(auth_client)
    with TestingSessionLocal() as db:
        assert station_slot_count(db, ctx["event_id"]) == 4  # no 8
        assert compute_total_rounds(db, ctx["event_id"]) == 1  # 3 estudiantes, 4 estaciones
        assert compute_missing_station_scores(db, ctx["event_id"]) == []
        results = compute_results(db, ctx["event_id"])
    assert len(results) == 6
    assert all(r["stations_counted"] == 4 and r["stations_expected"] == 4 for r in results)


def test_results_by_station_merge_mirrors_and_break_down_by_circuit(auth_client):
    ctx = _mirrored_event_with_scores(auth_client)
    body = auth_client.get(f"/api/results/{ctx['event_id']}").json()["by_station"]
    assert len(body["stations"]) == 4  # una fila por estación de diseño, no 8
    first = body["stations"][0]
    assert first["n"] == 6
    assert [c["circuit_name"] for c in first["circuits"]] == ["Circuito A", "Circuito B"]
    assert [c["n"] for c in first["circuits"]] == [3, 3]
    assert first["circuits"][0]["mean_percent"] > first["circuits"][1]["mean_percent"]
    assert {row["circuit_name"] for row in body["students"]} == {"Circuito A", "Circuito B"}
    assert {row["station_number"] for row in body["students"]} == {1, 2, 3, 4}


def test_reliability_uses_design_stations_so_every_student_is_complete(auth_client):
    ctx = _mirrored_event_with_scores(auth_client)
    with TestingSessionLocal() as db:
        block = build_psychometrics_block(db, ctx["event_id"], SessionMode.ejecucion.value)
    reliability = block["reliability"]
    assert reliability["k_stations"] == 4
    assert reliability["n_complete"] == 6 and reliability["n_total"] == 6
    assert len(block["station_stats"]) == 4


def test_evaluator_of_a_mirror_station_sees_the_originals_media(client, auth_client):
    ctx = _event(stations=1)
    _mirror(auth_client, ctx)
    mirror = [s for s in _stations(ctx) if s.mirror_of_id][0]
    with TestingSessionLocal() as db:
        db.add(MediaAsset(
            station_id=ctx["a"][0], filename="g.png", original_name="guia.png",
            content_type="image/png", file_path="/tmp/g.png", target_viewer="evaluador",
        ))
        db.add(StaffAssignment(
            ecoe_event_id=ctx["event_id"], name="Camila", last_name="Soto",
            email=EVALUATOR[0], role_code="evaluador", station_ids=[mirror.id],
        ))
        db.commit()
    login(client, EVALUATOR)
    listed = client.get(f"/api/media/{mirror.id}")
    assert listed.status_code == 200, listed.text
    assert [asset["original_name"] for asset in listed.json()] == ["guia.png"]
    login(client, ADMIN)


def test_duplicating_an_event_keeps_its_mirror_structure(auth_client):
    ctx = _event(stations=2)
    _mirror(auth_client, ctx)
    clone = auth_client.post(f"/api/ecoe/{ctx['event_id']}/duplicate", json={"name": "Copia espejo"})
    assert clone.status_code == 200, clone.text
    with TestingSessionLocal() as db:
        stations = db.scalars(select(Station).where(
            Station.ecoe_event_id == clone.json()["id"]).order_by(Station.station_number)).all()
        originals = {s.id for s in stations if s.mirror_of_id is None}
        assert len(stations) == 4 and len(originals) == 2
        assert {s.mirror_of_id for s in stations if s.mirror_of_id} == originals
        assert mirror_structure_issues(db, clone.json()["id"]) == []
