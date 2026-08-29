"""Reglas compartidas de los bancos institucionales de contenido de estación
(``StationTemplate`` y ``SimulatedPatient``).

OPT-7b · follow-up de OPT-7. El banco es cross-event y su única noción de
propietario son las columnas ``created_by`` / ``origin_event_id`` (ver
``models/entities.py``). Este módulo concentra lo que el CRUD necesita y no debe
divergir por modelo:

- **quién referencia un registro** (``reference_summary``) — estaciones *y*
  banco de estaciones, más los eventos que lo referencian;
- **si el actor puede gestionarlo** (``ensure_content_manage_permission``) — la
  regla de propiedad + gracia para legados (misma que
  ``instruments.ensure_tool_manage_permission``).

A diferencia de OPT-7 **no** hay ``ensure_*_editable``: el contenido de estos dos
bancos no se lee en runtime (``default_configuration`` solo se copia campo a
campo en el Constructor; la ficha del paciente no entra al cálculo de notas), así
que basta UPDATE libre + soft-delete.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    SimulatedPatient,
    Station,
    StationBank,
    StationTemplate,
    User,
)
from app.models.enums import RoleCode
from app.services.authorization import get_user_event_roles

_OWNER_ROLE_CODES = (RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)

# Columna de FK en `stations` / `station_bank` por tipo de registro.
_REF_COLUMNS = {
    "template": (Station.template_id, StationBank.template_id),
    "patient": (Station.simulated_patient_id, StationBank.simulated_patient_id),
}


def _kind_for(record) -> str:
    if isinstance(record, StationTemplate):
        return "template"
    if isinstance(record, SimulatedPatient):
        return "patient"
    raise TypeError(f"Registro de banco no soportado: {type(record)!r}")


# ── Referencias ───────────────────────────────────────────────────────

def reference_summary(db: Session, kind: str, record_id: int) -> dict:
    """Dónde se usa un registro del banco (estaciones + banco de estaciones).

    Una referencia desde ``station_bank`` (institucional, sin evento) suma a
    ``reference_count`` pero nunca aporta un ``event_id``.
    """
    station_col, bank_col = _REF_COLUMNS[kind]
    station_rows = db.execute(
        select(Station.id, Station.ecoe_event_id).where(station_col == record_id)
    ).all()
    bank_ids = list(db.scalars(select(StationBank.id).where(bank_col == record_id)).all())
    event_ids = sorted({row[1] for row in station_rows})
    return {
        "station_ids": [row[0] for row in station_rows],
        "bank_ids": bank_ids,
        "event_ids": event_ids,
        "reference_count": len(station_rows) + len(bank_ids),
    }


def summary_for(db: Session, record) -> dict:
    return reference_summary(db, _kind_for(record), record.id)


def reference_counts(db: Session, kind: str, record_ids: list[int]) -> dict[int, int]:
    """``reference_count`` (estaciones + banco) en lote, para el LIST."""
    if not record_ids:
        return {}
    station_col, bank_col = _REF_COLUMNS[kind]
    counts: dict[int, int] = defaultdict(int)
    for value in db.scalars(select(station_col).where(station_col.in_(record_ids))):
        counts[value] += 1
    for value in db.scalars(select(bank_col).where(bank_col.in_(record_ids))):
        counts[value] += 1
    return counts


# ── Permiso de propiedad ──────────────────────────────────────────────

def ensure_content_manage_permission(
    db: Session,
    user: User,
    record,
    summary: dict | None = None,
    *,
    require_admin: bool = False,
) -> None:
    """Editar / archivar / restaurar / purgar un registro del banco exige una de:

    1. ``admin_global`` (bypass universal).
    2. Rol ``admin_ecoe`` / ``coeditor_docente`` en ``record.origin_event_id``.
    3. Regla de gracia para legados (``origin_event_id IS NULL``): rol
       ``admin_ecoe`` / ``coeditor_docente`` en al menos un evento que hoy
       referencia el registro. Si el legado tiene 0 referencias con evento →
       solo ``admin_global``.

    ``require_admin`` (purge) restringe las reglas 2 y 3 a ``admin_ecoe``.
    """
    if str(user.role.code) == RoleCode.admin_global.value:
        return

    wanted = (RoleCode.admin_ecoe.value,) if require_admin else _OWNER_ROLE_CODES

    if record.origin_event_id is not None:
        if get_user_event_roles(db, user, record.origin_event_id).intersection(wanted):
            return
        raise HTTPException(
            status_code=403,
            detail=(
                "No puedes gestionar este registro del banco: pertenece a otro "
                "ECOE y no tienes rol de administrador o coeditor en él."
            ),
        )

    summary = summary or summary_for(db, record)
    for event_id in summary["event_ids"]:
        if get_user_event_roles(db, user, event_id).intersection(wanted):
            return
    raise HTTPException(
        status_code=403,
        detail=(
            "Este registro del banco no está asociado a ningún ECOE en el que "
            "tengas permiso de gestión; solo un administrador global puede "
            "modificarlo."
        ),
    )


# ── Serialización ─────────────────────────────────────────────────────

def serialize_template(template: StationTemplate, reference_count: int) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "category": template.category,
        "description": template.description,
        "default_configuration": template.default_configuration or {},
        "created_by": template.created_by,
        "origin_event_id": template.origin_event_id,
        "archived": template.archived,
        "reference_count": reference_count,
    }


def serialize_patient(patient: SimulatedPatient, reference_count: int) -> dict:
    return {
        "id": patient.id,
        "character_name": patient.character_name,
        "summary_profile": patient.summary_profile,
        "base_story": patient.base_story,
        "key_answers": patient.key_answers,
        "emotional_tone": patient.emotional_tone,
        "special_instructions": patient.special_instructions,
        "created_by": patient.created_by,
        "origin_event_id": patient.origin_event_id,
        "archived": patient.archived,
        "reference_count": reference_count,
    }
