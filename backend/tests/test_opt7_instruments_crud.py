"""OPT-7 · CRUD del banco de instrumentos (``AssessmentTool``).

Cubre los negativos obligatorios del plan
(``docs/optimizacion/PLANES/OPT-7__crud-instrumentos.md``):

- editar un tool usado por un ECOE en etapa avanzada → 409;
- archivar/editar sin permiso de origen (ni regla de gracia) → 403;
- hard-delete de un tool referenciado → 409; ``/purge`` con coeditor → 403;
- PATCH que reordena/edita ítems preservando ``AssessmentItem.id`` (las claves
  históricas de ``EvaluatorRecord.answers`` no se corrompen).
"""

import secrets
from datetime import date, timedelta

from sqlalchemy import select

from app.utils.clock import utcnow_naive

from app.core.security import get_password_hash
from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEEvent,
    ECOEPermission,
    EvaluatorRecord,
    Role,
    StaffAssignment,
    Station,
    StationBank,
    User,
)
from app.models.enums import ECOEStatus, RoleCode
from conftest import ADMIN, TestingSessionLocal, login


# ── Helpers ───────────────────────────────────────────────────────────

def _event(status: str = ECOEStatus.en_configuracion.value) -> int:
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name=f"OPT7 {secrets.token_hex(4)}",
            date=date(2026, 11, 1),
            course_name="Curso", school_name="Escuela",
            responsible_teacher="Docente", contact_email="d@e.edu",
            circuit_mode="paralelo_espejo", total_stations=1,
            station_time_minutes=8, transition_time_minutes=2,
            total_students=1, total_groups=1, passing_reference_percent=60,
            status=status,
        )
        db.add(event)
        db.commit()
        return event.id


def _account(email: str, password: str) -> None:
    with TestingSessionLocal() as db:
        role = db.scalar(select(Role).where(Role.code == RoleCode.miembro.value))
        db.add(User(
            email=email, full_name=email.split("@", 1)[0],
            hashed_password=get_password_hash(password),
            role_id=role.id, is_active=True,
        ))
        db.commit()


def _grant(event_id: int, email: str, role_code: str) -> None:
    with TestingSessionLocal() as db:
        db.add(StaffAssignment(
            ecoe_event_id=event_id, name="N", last_name="A",
            email=email, role_code=role_code, station_ids=[],
        ))
        db.commit()


def _tool(*, origin_event_id: int | None, archived: bool = False,
          created_by: str | None = "creator@e.edu",
          labels: tuple[str, ...] = ("A", "B", "C")) -> int:
    with TestingSessionLocal() as db:
        tool = AssessmentTool(
            name="Pauta OPT7", tool_type="lista_cotejo", max_score=float(len(labels)),
            free_observation=True, archived=archived,
            created_by=created_by, origin_event_id=origin_event_id,
        )
        db.add(tool)
        db.flush()
        for idx, label in enumerate(labels, start=1):
            db.add(AssessmentItem(tool_id=tool.id, label=label,
                                  score_per_item=1.0, order_index=idx))
        db.commit()
        return tool.id


def _station(event_id: int, tool_id: int | None) -> int:
    with TestingSessionLocal() as db:
        used = db.scalars(
            select(Station.station_number).where(Station.ecoe_event_id == event_id)
        ).all()
        number = (max(used) if used else 0) + 1
        station = Station(
            ecoe_event_id=event_id, station_number=number, name=f"E{number}",
            station_type="procedimental", circuit_name="Circuito A",
            station_time_minutes=8, transition_time_minutes=2,
            expected_outcomes="o", student_activity="a",
            pre_entry_instruction="p", evaluator_instruction="e",
            assessment_tool_id=tool_id, max_score=3,
        )
        db.add(station)
        db.commit()
        return station.id


def _bank_entry(tool_id: int) -> int:
    with TestingSessionLocal() as db:
        entry = StationBank(
            assessment_tool_id=tool_id, name="Banco E", station_type="procedimental",
            expected_outcomes="o", student_activity="a",
            pre_entry_instruction="p", evaluator_instruction="e",
        )
        db.add(entry)
        db.commit()
        return entry.id


def _tool_row(tool_id: int) -> AssessmentTool | None:
    with TestingSessionLocal() as db:
        return db.get(AssessmentTool, tool_id)


def _items(tool_id: int) -> list[tuple[int, str, int]]:
    with TestingSessionLocal() as db:
        rows = db.scalars(
            select(AssessmentItem).where(AssessmentItem.tool_id == tool_id)
            .order_by(AssessmentItem.order_index)
        ).all()
        return [(r.id, r.label, r.order_index) for r in rows]


def _coeditor(event_id: int) -> tuple[str, str]:
    email = f"coed-{secrets.token_hex(4)}@e.edu"
    password = secrets.token_urlsafe(24)
    _account(email, password)
    _grant(event_id, email, RoleCode.coeditor_docente.value)
    return email, password


# ── Negativos obligatorios ────────────────────────────────────────────

def test_patch_tool_of_advanced_event_returns_409(auth_client):
    for status in (ECOEStatus.en_pilotaje.value, ECOEStatus.publicado.value,
                   ECOEStatus.en_ejecucion.value, ECOEStatus.cerrado.value):
        login(auth_client, ADMIN)
        event_id = _event(status)
        tool_id = _tool(origin_event_id=event_id)
        _station(event_id, tool_id)

        resp = auth_client.patch(
            f"/api/instruments/{tool_id}?ecoe_event_id={event_id}",
            json={"name": "Renombrada"},
        )
        assert resp.status_code == 409, f"{status}: {resp.text}"
        assert _tool_row(tool_id).name == "Pauta OPT7"


def test_archive_tool_of_advanced_event_returns_409(auth_client):
    login(auth_client, ADMIN)
    event_id = _event(ECOEStatus.publicado.value)
    tool_id = _tool(origin_event_id=event_id)
    _station(event_id, tool_id)
    resp = auth_client.delete(f"/api/instruments/{tool_id}?ecoe_event_id={event_id}")
    assert resp.status_code == 409
    assert _tool_row(tool_id).archived is False


def test_archive_tool_without_origin_permission_returns_403(client):
    login(client, ADMIN)
    event_a = _event()
    event_b = _event()
    tool_id = _tool(origin_event_id=event_a)  # pertenece a A
    email, password = _coeditor(event_b)      # coeditor solo de B

    login(client, (email, password))
    resp = client.delete(f"/api/instruments/{tool_id}?ecoe_event_id={event_b}")
    assert resp.status_code == 403, resp.text
    assert _tool_row(tool_id).archived is False


def test_patch_tool_without_origin_permission_returns_403(client):
    login(client, ADMIN)
    event_a, event_b = _event(), _event()
    tool_id = _tool(origin_event_id=event_a)
    email, password = _coeditor(event_b)

    login(client, (email, password))
    resp = client.patch(
        f"/api/instruments/{tool_id}?ecoe_event_id={event_b}",
        json={"name": "x"},
    )
    assert resp.status_code == 403


def test_purge_referenced_tool_returns_409(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    tool_id = _tool(origin_event_id=event_id)
    _station(event_id, tool_id)
    resp = auth_client.delete(f"/api/instruments/{tool_id}/purge?ecoe_event_id={event_id}")
    assert resp.status_code == 409
    assert _tool_row(tool_id) is not None

    # También bloquea si la referencia está solo en el banco de estaciones.
    tool2 = _tool(origin_event_id=event_id)
    _bank_entry(tool2)
    resp2 = auth_client.delete(f"/api/instruments/{tool2}/purge?ecoe_event_id={event_id}")
    assert resp2.status_code == 409
    assert _tool_row(tool2) is not None


def test_purge_requires_admin_ecoe_not_coeditor(client):
    login(client, ADMIN)
    event_id = _event()
    tool_id = _tool(origin_event_id=event_id)
    email, password = _coeditor(event_id)

    login(client, (email, password))
    resp = client.delete(f"/api/instruments/{tool_id}/purge?ecoe_event_id={event_id}")
    assert resp.status_code == 403
    assert _tool_row(tool_id) is not None


def test_patch_preserves_item_ids(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    tool_id = _tool(origin_event_id=event_id, labels=("Uno", "Dos", "Tres"))
    original = _items(tool_id)  # [(id1,'Uno',1),(id2,'Dos',2),(id3,'Tres',3)]
    id1, id2, id3 = [r[0] for r in original]

    # Un EvaluatorRecord histórico keyed por esos ids de ítem.
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=event_id, station_id=_station(event_id, tool_id),
            student_id=1, evaluator_name="Ev", score_obtained=2, max_score=3,
            answers={str(id1): 1, str(id2): 0, str(id3): 1},
        ))
        db.commit()

    # PATCH: reordena (Tres primero), edita el label del ítem 2, agrega un ítem 4,
    # mantiene el ítem 1 y 3.
    resp = auth_client.patch(
        f"/api/instruments/{tool_id}?ecoe_event_id={event_id}",
        json={"items": [
            {"id": id3, "label": "Tres", "score_per_item": 1, "order_index": 1},
            {"id": id1, "label": "Uno", "score_per_item": 1, "order_index": 2},
            {"id": id2, "label": "Dos (corregido)", "score_per_item": 2, "order_index": 3},
            {"label": "Cuatro", "score_per_item": 1, "order_index": 4},
        ]},
    )
    assert resp.status_code == 200, resp.text

    after = {r[0]: r for r in _items(tool_id)}
    assert set(after) >= {id1, id2, id3}  # los ids sobreviven
    assert after[id2][1] == "Dos (corregido)"
    assert after[id3][2] == 1 and after[id1][2] == 2
    assert len(after) == 4

    # Las claves del answers histórico siguen resolviendo contra ítems vivos.
    with TestingSessionLocal() as db:
        rec = db.scalar(select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == event_id))
        live_ids = {i.id for i in db.scalars(
            select(AssessmentItem).where(AssessmentItem.tool_id == tool_id))}
    assert {int(k) for k in rec.answers} <= live_ids


def test_patch_drops_item_documented_behavior(auth_client):
    """Un ítem quitado del payload se elimina (delete-orphan). Su `id`
    desaparece; una clave histórica que apuntara a él queda huérfana — por eso
    el gate de `EDIT_BLOCKING_STATUSES` impide editar tools de eventos ya
    piloteados/ejecutados."""
    login(auth_client, ADMIN)
    event_id = _event()
    tool_id = _tool(origin_event_id=event_id, labels=("A", "B", "C"))
    id1, id2, id3 = [r[0] for r in _items(tool_id)]

    resp = auth_client.patch(
        f"/api/instruments/{tool_id}?ecoe_event_id={event_id}",
        json={"items": [
            {"id": id1, "label": "A", "score_per_item": 1, "order_index": 1},
            {"id": id2, "label": "B", "score_per_item": 1, "order_index": 2},
        ]},
    )
    assert resp.status_code == 200
    remaining = {r[0] for r in _items(tool_id)}
    assert remaining == {id1, id2}
    assert id3 not in remaining


def test_list_instruments_hides_archived_by_default(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    live = _tool(origin_event_id=event_id)
    archived = _tool(origin_event_id=event_id, archived=True)

    default = auth_client.get(f"/api/instruments?ecoe_event_id={event_id}")
    assert default.status_code == 200
    ids = {t["id"] for t in default.json()}
    assert live in ids and archived not in ids

    withall = auth_client.get(
        f"/api/instruments?ecoe_event_id={event_id}&include_archived=true")
    ids_all = {t["id"] for t in withall.json()}
    assert live in ids_all and archived in ids_all


def test_archived_tool_not_selectable_for_new_station(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    archived = _tool(origin_event_id=event_id, archived=True)

    # Estación nueva que intenta usar el tool archivado → 400.
    resp = auth_client.post("/api/stations", json={
        "ecoe_event_id": event_id, "station_number": 1, "name": "Nueva",
        "station_type": "procedimental", "circuit_name": "Circuito A",
        "expected_outcomes": "o", "student_activity": "a",
        "pre_entry_instruction": "p", "evaluator_instruction": "e",
        "assessment_tool_id": archived, "max_score": 3,
    })
    assert resp.status_code == 400

    # Una estación que ya lo referenciaba sigue existiendo y sirviéndose.
    existing_station = _station(event_id, archived)
    listing = auth_client.get(f"/api/stations/{event_id}")
    assert any(s["id"] == existing_station and s["assessment_tool_id"] == archived
               for s in listing.json())


# ── Regla de gracia para tools legados ────────────────────────────────

def test_historical_tool_grace_rule(client):
    login(client, ADMIN)
    event_ref = _event()          # evento que hoy referencia el tool legado
    event_other = _event()        # evento sin relación

    legacy_tool = _tool(origin_event_id=None, created_by=None)
    _station(event_ref, legacy_tool)

    # Coeditor del evento que lo referencia → puede archivar.
    email_ref, pw_ref = _coeditor(event_ref)
    login(client, (email_ref, pw_ref))
    ok = client.delete(f"/api/instruments/{legacy_tool}?ecoe_event_id={event_ref}")
    assert ok.status_code == 200, ok.text
    assert _tool_row(legacy_tool).archived is True

    # Coeditor de un evento sin relación → 403.
    legacy_tool_2 = _tool(origin_event_id=None, created_by=None)
    _station(event_ref, legacy_tool_2)
    email_other, pw_other = _coeditor(event_other)
    login(client, (email_other, pw_other))
    denied = client.delete(
        f"/api/instruments/{legacy_tool_2}?ecoe_event_id={event_other}")
    assert denied.status_code == 403

    # Tool legado con 0 referencias → solo admin_global; coeditor 403.
    orphan_legacy = _tool(origin_event_id=None, created_by=None)
    email_o, pw_o = _coeditor(event_ref)
    login(client, (email_o, pw_o))
    denied2 = client.delete(
        f"/api/instruments/{orphan_legacy}?ecoe_event_id={event_ref}")
    assert denied2.status_code == 403
    login(client, ADMIN)
    ok2 = client.delete(
        f"/api/instruments/{orphan_legacy}?ecoe_event_id={event_ref}")
    assert ok2.status_code == 200


# ── Positivos ─────────────────────────────────────────────────────────

def test_patch_tool_of_draft_event_ok(auth_client):
    login(auth_client, ADMIN)
    event_id = _event(ECOEStatus.en_configuracion.value)
    tool_id = _tool(origin_event_id=event_id)
    _station(event_id, tool_id)
    resp = auth_client.patch(
        f"/api/instruments/{tool_id}?ecoe_event_id={event_id}",
        json={"name": "Pauta corregida", "free_observation": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Pauta corregida"
    assert resp.json()["free_observation"] is False


def test_soft_delete_then_restore(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    tool_id = _tool(origin_event_id=event_id)

    d = auth_client.delete(f"/api/instruments/{tool_id}?ecoe_event_id={event_id}")
    assert d.status_code == 200 and d.json()["archived"] is True
    # idempotente
    d2 = auth_client.delete(f"/api/instruments/{tool_id}?ecoe_event_id={event_id}")
    assert d2.status_code == 200 and d2.json()["archived"] is True

    r = auth_client.post(f"/api/instruments/{tool_id}/restore?ecoe_event_id={event_id}")
    assert r.status_code == 200 and r.json()["archived"] is False


def test_create_instrument_stamps_created_by_and_origin_event(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    resp = auth_client.post(f"/api/instruments?ecoe_event_id={event_id}", json={
        "name": "Nueva pauta", "tool_type": "lista_cotejo", "max_score": 4,
        "free_observation": True,
        "items": [{"label": "x", "score_per_item": 2, "order_index": 1}],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["origin_event_id"] == event_id
    assert body["created_by"] == ADMIN[0]
    assert body["archived"] is False
    assert body["reference_count"] == 0


def test_purge_orphan_command_dry_run_lists_and_apply_deletes(auth_client):
    from scripts.purge_orphan_instruments import find_candidates, main

    login(auth_client, ADMIN)
    event_id = _event()

    old_orphan = _tool(origin_event_id=event_id)
    recent_orphan = _tool(origin_event_id=event_id)
    referenced = _tool(origin_event_id=event_id)
    _station(event_id, referenced)

    with TestingSessionLocal() as db:
        # envejecer el huérfano viejo por debajo del umbral de 90 días
        tool = db.get(AssessmentTool, old_orphan)
        tool.created_at = utcnow_naive() - timedelta(days=200)
        db.add(tool)
        db.commit()

        cands = {c["id"] for c in find_candidates(db, min_age_days=90,
                                                  include_archived=False)}
    assert old_orphan in cands
    assert recent_orphan not in cands   # demasiado nuevo
    assert referenced not in cands      # tiene referencia

    # dry-run: no borra
    assert main(["--min-age-days", "90"]) == 0
    assert _tool_row(old_orphan) is not None

    # --apply: borra solo el candidato
    assert main(["--min-age-days", "90", "--apply"]) == 0
    assert _tool_row(old_orphan) is None
    assert _tool_row(recent_orphan) is not None
    assert _tool_row(referenced) is not None


def test_purge_orphan_command_respects_evaluator_answer_keys(auth_client):
    from scripts.purge_orphan_instruments import find_candidates

    login(auth_client, ADMIN)
    event_id = _event()
    tool_id = _tool(origin_event_id=event_id)
    item_ids = [r[0] for r in _items(tool_id)]

    with TestingSessionLocal() as db:
        tool = db.get(AssessmentTool, tool_id)
        tool.created_at = utcnow_naive() - timedelta(days=200)
        db.add(EvaluatorRecord(
            ecoe_event_id=event_id, station_id=_station(event_id, None),
            student_id=1, evaluator_name="Ev", score_obtained=1, max_score=1,
            answers={str(item_ids[0]): 1},
        ))
        db.commit()
        cands = {c["id"] for c in find_candidates(db, min_age_days=90,
                                                  include_archived=False)}
    assert tool_id not in cands  # un item.id sigue referenciado en answers


def test_purge_orphan_tool_succeeds(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    tool_id = _tool(origin_event_id=event_id)
    resp = auth_client.delete(
        f"/api/instruments/{tool_id}/purge?ecoe_event_id={event_id}")
    assert resp.status_code == 200
    assert _tool_row(tool_id) is None
    with TestingSessionLocal() as db:
        assert db.scalars(
            select(AssessmentItem).where(AssessmentItem.tool_id == tool_id)
        ).all() == []
