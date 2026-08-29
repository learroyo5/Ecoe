"""OPT-7b · CRUD de los bancos de contenido (``StationTemplate`` /
``SimulatedPatient``).

Cubre los negativos obligatorios del plan
(``docs/optimizacion/PLANES/OPT-7b__crud-plantillas-pacientes.md``):

- editar / archivar sin permiso de origen → 403;
- purgar un registro referenciado → 409; ``/purge`` con coeditor → 403;
- regla de gracia para legados (``origin_event_id IS NULL``);
- soft-delete oculta del LIST salvo ``include_archived``;
- un registro archivado no es asignable a una estación nueva (una que ya lo usa
  sigue operativa);
- **contraste con OPT-7**: sin gate de estado, un PATCH sobre una plantilla
  usada por un ECOE ``en_ejecucion`` devuelve 200.
"""

import secrets
from datetime import date, timedelta

from sqlalchemy import select

from app.utils.clock import utcnow_naive

from app.core.security import get_password_hash
from app.models.entities import (
    ECOEEvent,
    Role,
    SimulatedPatient,
    StaffAssignment,
    Station,
    StationBank,
    StationTemplate,
    User,
)
from app.models.enums import ECOEStatus, RoleCode
from conftest import ADMIN, TestingSessionLocal, login


# ── Helpers ───────────────────────────────────────────────────────────

def _event(status: str = ECOEStatus.en_configuracion.value) -> int:
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name=f"OPT7b {secrets.token_hex(4)}",
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


def _coeditor(event_id: int) -> tuple[str, str]:
    email = f"coed-{secrets.token_hex(4)}@e.edu"
    password = secrets.token_urlsafe(24)
    _account(email, password)
    _grant(event_id, email, RoleCode.coeditor_docente.value)
    return email, password


def _template(*, origin_event_id: int | None, archived: bool = False,
              created_by: str | None = "creator@e.edu",
              name: str = "Plantilla OPT7b") -> int:
    with TestingSessionLocal() as db:
        template = StationTemplate(
            name=name, category="procedimental", description="desc",
            default_configuration={"requires_evaluator": True},
            archived=archived, created_by=created_by,
            origin_event_id=origin_event_id,
        )
        db.add(template)
        db.commit()
        return template.id


def _patient(*, origin_event_id: int | None, archived: bool = False,
             created_by: str | None = "creator@e.edu") -> int:
    with TestingSessionLocal() as db:
        patient = SimulatedPatient(
            character_name="Paciente OPT7b", summary_profile="perfil",
            base_story="historia", key_answers="respuestas",
            emotional_tone="neutro", special_instructions="ninguna",
            archived=archived, created_by=created_by,
            origin_event_id=origin_event_id,
        )
        db.add(patient)
        db.commit()
        return patient.id


def _station(event_id: int, *, template_id: int | None = None,
             simulated_patient_id: int | None = None) -> int:
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
            template_id=template_id, simulated_patient_id=simulated_patient_id,
            max_score=3,
        )
        db.add(station)
        db.commit()
        return station.id


def _bank_entry(*, template_id: int | None = None,
                simulated_patient_id: int | None = None) -> int:
    with TestingSessionLocal() as db:
        entry = StationBank(
            name="Banco E", station_type="procedimental",
            expected_outcomes="o", student_activity="a",
            pre_entry_instruction="p", evaluator_instruction="e",
            template_id=template_id, simulated_patient_id=simulated_patient_id,
        )
        db.add(entry)
        db.commit()
        return entry.id


def _template_row(template_id: int) -> StationTemplate | None:
    with TestingSessionLocal() as db:
        return db.get(StationTemplate, template_id)


def _patient_row(patient_id: int) -> SimulatedPatient | None:
    with TestingSessionLocal() as db:
        return db.get(SimulatedPatient, patient_id)


# ── Negativos obligatorios ────────────────────────────────────────────

def test_archive_template_without_origin_permission_returns_403(client):
    login(client, ADMIN)
    event_a, event_b = _event(), _event()
    template_id = _template(origin_event_id=event_a)  # pertenece a A
    email, password = _coeditor(event_b)              # coeditor solo de B

    login(client, (email, password))
    resp = client.delete(f"/api/templates/{template_id}?ecoe_event_id={event_b}")
    assert resp.status_code == 403, resp.text
    assert _template_row(template_id).archived is False


def test_patch_patient_without_origin_permission_returns_403(client):
    login(client, ADMIN)
    event_a, event_b = _event(), _event()
    patient_id = _patient(origin_event_id=event_a)
    email, password = _coeditor(event_b)

    login(client, (email, password))
    resp = client.patch(
        f"/api/simulated-patients/{patient_id}?ecoe_event_id={event_b}",
        json={"emotional_tone": "hostil"},
    )
    assert resp.status_code == 403, resp.text
    assert _patient_row(patient_id).emotional_tone == "neutro"


def test_purge_referenced_template_returns_409(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()

    referenced_by_station = _template(origin_event_id=event_id)
    _station(event_id, template_id=referenced_by_station)
    resp = auth_client.delete(
        f"/api/templates/{referenced_by_station}/purge?ecoe_event_id={event_id}")
    assert resp.status_code == 409, resp.text
    assert _template_row(referenced_by_station) is not None

    # También bloquea si la referencia está solo en el banco de estaciones.
    referenced_by_bank = _template(origin_event_id=event_id)
    _bank_entry(template_id=referenced_by_bank)
    resp2 = auth_client.delete(
        f"/api/templates/{referenced_by_bank}/purge?ecoe_event_id={event_id}")
    assert resp2.status_code == 409
    assert _template_row(referenced_by_bank) is not None


def test_purge_requires_admin_ecoe_not_coeditor(client):
    login(client, ADMIN)
    event_id = _event()
    template_id = _template(origin_event_id=event_id)
    email, password = _coeditor(event_id)

    login(client, (email, password))
    resp = client.delete(f"/api/templates/{template_id}/purge?ecoe_event_id={event_id}")
    assert resp.status_code == 403
    assert _template_row(template_id) is not None


def test_legacy_grace_rule(client):
    login(client, ADMIN)
    event_ref = _event()      # evento que hoy referencia el registro legado
    event_other = _event()    # evento sin relación

    # Legado con 1 referencia: coeditor del evento que lo referencia → archiva.
    legacy = _template(origin_event_id=None, created_by=None)
    _station(event_ref, template_id=legacy)
    email_ref, pw_ref = _coeditor(event_ref)
    login(client, (email_ref, pw_ref))
    ok = client.delete(f"/api/templates/{legacy}?ecoe_event_id={event_ref}")
    assert ok.status_code == 200, ok.text
    assert _template_row(legacy).archived is True

    # Coeditor de un evento sin relación → 403.
    legacy2 = _template(origin_event_id=None, created_by=None)
    _station(event_ref, template_id=legacy2)
    email_other, pw_other = _coeditor(event_other)
    login(client, (email_other, pw_other))
    denied = client.delete(f"/api/templates/{legacy2}?ecoe_event_id={event_other}")
    assert denied.status_code == 403

    # Legado con 0 referencias → solo admin_global; coeditor 403.
    orphan_legacy = _template(origin_event_id=None, created_by=None)
    email_o, pw_o = _coeditor(event_ref)
    login(client, (email_o, pw_o))
    denied2 = client.delete(
        f"/api/templates/{orphan_legacy}?ecoe_event_id={event_ref}")
    assert denied2.status_code == 403
    login(client, ADMIN)
    ok2 = client.delete(
        f"/api/templates/{orphan_legacy}?ecoe_event_id={event_ref}")
    assert ok2.status_code == 200


def test_archived_template_not_selectable_for_new_station(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    archived = _template(origin_event_id=event_id, archived=True)

    resp = auth_client.post("/api/stations", json={
        "ecoe_event_id": event_id, "station_number": 1, "name": "Nueva",
        "station_type": "procedimental", "circuit_name": "Circuito A",
        "expected_outcomes": "o", "student_activity": "a",
        "pre_entry_instruction": "p", "evaluator_instruction": "e",
        "template_id": archived, "max_score": 3,
    })
    assert resp.status_code == 400, resp.text

    # Una estación que ya lo referenciaba sigue existiendo y sirviéndose.
    existing = _station(event_id, template_id=archived)
    listing = auth_client.get(f"/api/stations/{event_id}")
    assert any(s["id"] == existing and s["template_id"] == archived
               for s in listing.json())


def test_archived_patient_not_selectable_for_new_station(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    archived = _patient(origin_event_id=event_id, archived=True)
    resp = auth_client.post("/api/stations", json={
        "ecoe_event_id": event_id, "station_number": 1, "name": "Nueva",
        "station_type": "procedimental", "circuit_name": "Circuito A",
        "expected_outcomes": "o", "student_activity": "a",
        "pre_entry_instruction": "p", "evaluator_instruction": "e",
        "simulated_patient_id": archived, "max_score": 3,
    })
    assert resp.status_code == 400, resp.text


def test_list_hides_archived_by_default(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    live_t = _template(origin_event_id=event_id)
    arch_t = _template(origin_event_id=event_id, archived=True)
    live_p = _patient(origin_event_id=event_id)
    arch_p = _patient(origin_event_id=event_id, archived=True)

    t_default = {t["id"] for t in auth_client.get(
        f"/api/templates?ecoe_event_id={event_id}").json()}
    assert live_t in t_default and arch_t not in t_default
    t_all = {t["id"] for t in auth_client.get(
        f"/api/templates?ecoe_event_id={event_id}&include_archived=true").json()}
    assert {live_t, arch_t} <= t_all

    p_default = {p["id"] for p in auth_client.get(
        f"/api/simulated-patients?ecoe_event_id={event_id}").json()}
    assert live_p in p_default and arch_p not in p_default
    p_all = {p["id"] for p in auth_client.get(
        f"/api/simulated-patients?ecoe_event_id={event_id}&include_archived=true").json()}
    assert {live_p, arch_p} <= p_all


# ── Positivos ─────────────────────────────────────────────────────────

def test_patch_template_updates_all_fields_freely(auth_client):
    """Sin gate de estado: plantilla usada por una estación de un ECOE
    ``en_ejecucion`` → PATCH 200 (contraste con OPT-7, que devolvería 409)."""
    login(auth_client, ADMIN)
    event_id = _event(ECOEStatus.en_ejecucion.value)
    template_id = _template(origin_event_id=event_id)
    _station(event_id, template_id=template_id)

    resp = auth_client.patch(
        f"/api/templates/{template_id}?ecoe_event_id={event_id}",
        json={
            "name": "Corregida", "category": "hibrida",
            "description": "nueva desc",
            "default_configuration": {"requires_evaluator": False, "x": 1},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Corregida"
    assert body["category"] == "hibrida"
    assert body["default_configuration"] == {"requires_evaluator": False, "x": 1}


def test_soft_delete_then_restore_template(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    template_id = _template(origin_event_id=event_id)

    d = auth_client.delete(f"/api/templates/{template_id}?ecoe_event_id={event_id}")
    assert d.status_code == 200 and d.json()["archived"] is True
    d2 = auth_client.delete(f"/api/templates/{template_id}?ecoe_event_id={event_id}")
    assert d2.status_code == 200 and d2.json()["archived"] is True  # idempotente
    r = auth_client.post(f"/api/templates/{template_id}/restore?ecoe_event_id={event_id}")
    assert r.status_code == 200 and r.json()["archived"] is False


def test_soft_delete_then_restore_patient(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    patient_id = _patient(origin_event_id=event_id)

    d = auth_client.delete(f"/api/simulated-patients/{patient_id}?ecoe_event_id={event_id}")
    assert d.status_code == 200 and d.json()["archived"] is True
    r = auth_client.post(
        f"/api/simulated-patients/{patient_id}/restore?ecoe_event_id={event_id}")
    assert r.status_code == 200 and r.json()["archived"] is False


def test_create_stamps_created_by_and_origin_event(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()

    t = auth_client.post(f"/api/templates?ecoe_event_id={event_id}", json={
        "name": "Nueva plantilla", "category": "procedimental",
        "description": "d", "default_configuration": {},
    })
    assert t.status_code == 200, t.text
    assert t.json()["origin_event_id"] == event_id
    assert t.json()["created_by"] == ADMIN[0]
    assert t.json()["archived"] is False
    assert t.json()["reference_count"] == 0

    p = auth_client.post(f"/api/simulated-patients?ecoe_event_id={event_id}", json={
        "character_name": "Nuevo", "summary_profile": "s", "base_story": "b",
        "key_answers": "k", "emotional_tone": "t", "special_instructions": "i",
    })
    assert p.status_code == 200, p.text
    assert p.json()["origin_event_id"] == event_id
    assert p.json()["created_by"] == ADMIN[0]


def test_purge_orphan_template_succeeds(auth_client):
    login(auth_client, ADMIN)
    event_id = _event()
    template_id = _template(origin_event_id=event_id)
    resp = auth_client.delete(
        f"/api/templates/{template_id}/purge?ecoe_event_id={event_id}")
    assert resp.status_code == 200
    assert _template_row(template_id) is None


def test_purge_orphan_command_dry_run_then_apply(auth_client):
    from scripts.purge_orphan_content import find_candidates, main

    login(auth_client, ADMIN)
    event_id = _event()

    old_orphan = _template(origin_event_id=event_id, name="Vieja huérfana")
    recent_orphan = _template(origin_event_id=event_id, name="Nueva huérfana")
    referenced = _template(origin_event_id=event_id, name="Referenciada")
    _station(event_id, template_id=referenced)

    with TestingSessionLocal() as db:
        row = db.get(StationTemplate, old_orphan)
        row.created_at = utcnow_naive() - timedelta(days=200)
        db.add(row)
        db.commit()

        cands = {c["id"] for c in find_candidates(
            db, kind="templates", min_age_days=90, include_archived=False)}
    assert old_orphan in cands
    assert recent_orphan not in cands   # demasiado nuevo
    assert referenced not in cands      # tiene referencia

    assert main(["--kind", "templates", "--min-age-days", "90"]) == 0  # dry-run
    assert _template_row(old_orphan) is not None

    assert main(["--kind", "templates", "--min-age-days", "90", "--apply"]) == 0
    assert _template_row(old_orphan) is None
    assert _template_row(recent_orphan) is not None
    assert _template_row(referenced) is not None


def test_purge_orphan_command_patients_kind(auth_client):
    from scripts.purge_orphan_content import main

    login(auth_client, ADMIN)
    event_id = _event()
    orphan = _patient(origin_event_id=event_id)
    with TestingSessionLocal() as db:
        row = db.get(SimulatedPatient, orphan)
        row.created_at = utcnow_naive() - timedelta(days=200)
        db.add(row)
        db.commit()
    assert main(["--kind", "patients", "--min-age-days", "90", "--apply"]) == 0
    assert _patient_row(orphan) is None


def test_create_station_from_template_still_works(auth_client):
    """La creación de una estación que referencia una plantilla viva (el
    Constructor copia los campos en el cliente; el backend solo guarda el FK)
    no se rompe."""
    login(auth_client, ADMIN)
    event_id = _event()
    template_id = _template(origin_event_id=event_id)
    patient_id = _patient(origin_event_id=event_id)

    resp = auth_client.post("/api/stations", json={
        "ecoe_event_id": event_id, "station_number": 1, "name": "Desde plantilla",
        "station_type": "procedimental", "circuit_name": "Circuito A",
        "expected_outcomes": "o", "student_activity": "a",
        "pre_entry_instruction": "p", "evaluator_instruction": "e",
        "template_id": template_id, "simulated_patient_id": patient_id,
        "max_score": 3,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["template_id"] == template_id
    assert resp.json()["simulated_patient_id"] == patient_id
