"""Business rules for the institutional instrument bank (``AssessmentTool``).

OPT-7. The bank is cross-event and has no owner column beyond ``created_by`` /
``origin_event_id`` (see ``models/entities.py``). These helpers concentrate the
three things the CRUD endpoints need and must not diverge on:

- **who references a tool** (``tool_reference_summary``) — stations *and* the
  station bank, plus the status of every referencing event;
- **whether a tool may still be edited** (``ensure_tool_editable``) — a tool
  whose items are already referenced by ``EvaluatorRecord.answers`` (keyed by
  ``AssessmentItem.id``) of a pilot/live/closed event must not change shape;
- **whether the actor owns the tool** (``ensure_tool_manage_permission``) — the
  ownership + legacy grace rule (decisión del usuario 2026-08-29).

``apply_tool_patch`` updates items **in place, preserving ``AssessmentItem.id``**
so historical ``EvaluatorRecord.answers`` keys keep resolving.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEEvent,
    Station,
    StationBank,
    User,
)
from app.models.enums import ECOEStatus, RoleCode
from app.services.authorization import get_user_event_roles

# Estados de ECOE en los que el instrumento ya está "en uso real": los ids de
# sus ítems pueden estar referenciados por EvaluatorRecord.answers / PilotRecord.
# `en_pilotaje` bloquea aunque el grafo lo ponga antes de `pilotaje_validado`:
# una vez registrada actividad de pilotaje, los ids ya viajaron a `answers`.
EDIT_BLOCKING_STATUSES: set[str] = {
    ECOEStatus.en_pilotaje.value,
    ECOEStatus.publicado.value,
    ECOEStatus.en_ejecucion.value,
    ECOEStatus.cerrado.value,
    ECOEStatus.archivado.value,
}

_OWNER_ROLE_CODES = (RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)


# ── Referencias ────────────────────────────────────────────────────────

def tool_reference_summary(db: Session, tool_id: int) -> dict:
    """Where a tool is used, and the status of each referencing event.

    A reference from ``station_bank`` (institutional, no event) counts toward
    ``reference_count`` but never contributes an event / a blocking status.
    """
    station_rows = db.execute(
        select(Station.id, Station.ecoe_event_id, ECOEEvent.name, ECOEEvent.status)
        .join(ECOEEvent, ECOEEvent.id == Station.ecoe_event_id)
        .where(Station.assessment_tool_id == tool_id)
    ).all()
    bank_ids = list(
        db.scalars(
            select(StationBank.id).where(StationBank.assessment_tool_id == tool_id)
        ).all()
    )

    events: dict[int, dict] = {}
    for _sid, event_id, event_name, event_status in station_rows:
        events.setdefault(
            event_id, {"id": event_id, "name": event_name, "status": event_status}
        )

    return {
        "station_ids": [row[0] for row in station_rows],
        "bank_ids": bank_ids,
        "event_ids": list(events.keys()),
        "events": list(events.values()),
        "event_statuses": {event["status"] for event in events.values()},
        "reference_count": len(station_rows) + len(bank_ids),
    }


def reference_counts(db: Session, tool_ids: list[int]) -> dict[int, int]:
    """Batched ``reference_count`` (stations + bank) for a list of tools."""
    if not tool_ids:
        return {}
    counts: dict[int, int] = defaultdict(int)
    for tid in db.scalars(
        select(Station.assessment_tool_id).where(
            Station.assessment_tool_id.in_(tool_ids)
        )
    ):
        counts[tid] += 1
    for tid in db.scalars(
        select(StationBank.assessment_tool_id).where(
            StationBank.assessment_tool_id.in_(tool_ids)
        )
    ):
        counts[tid] += 1
    return counts


# ── Gate de edición ───────────────────────────────────────────────────

def ensure_tool_editable(db: Session, tool: AssessmentTool, summary: dict | None = None) -> dict:
    summary = summary or tool_reference_summary(db, tool.id)
    blocking = [
        event
        for event in summary["events"]
        if event["status"] in EDIT_BLOCKING_STATUSES
    ]
    if blocking:
        detail = ", ".join(
            sorted(f"{event['name']} ({event['status']})" for event in blocking)
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "No se puede editar ni archivar este instrumento: lo usa una "
                f"estación de un ECOE en etapa avanzada ({detail}). Duplica la "
                "pauta si necesitas una versión corregida."
            ),
        )
    return summary


# ── Permiso de propiedad ──────────────────────────────────────────────

def ensure_tool_manage_permission(
    db: Session,
    user: User,
    tool: AssessmentTool,
    summary: dict | None = None,
    *,
    require_admin: bool = False,
) -> None:
    """Editar / archivar / restaurar / purgar un instrumento exige una de:

    1. ``admin_global`` (bypass universal).
    2. Rol ``admin_ecoe`` / ``coeditor_docente`` en ``tool.origin_event_id``.
    3. Regla de gracia para tools legados (``origin_event_id IS NULL``): rol
       ``admin_ecoe`` / ``coeditor_docente`` en al menos un evento que hoy
       referencia el tool. Si el tool legado no tiene ninguna referencia con
       evento → solo ``admin_global``.

    ``require_admin`` (purge) restringe las reglas 2 y 3 a ``admin_ecoe``.
    """
    if str(user.role.code) == RoleCode.admin_global.value:
        return

    wanted = (
        (RoleCode.admin_ecoe.value,) if require_admin else _OWNER_ROLE_CODES
    )

    if tool.origin_event_id is not None:
        roles = get_user_event_roles(db, user, tool.origin_event_id)
        if roles.intersection(wanted):
            return
        raise HTTPException(
            status_code=403,
            detail=(
                "No puedes gestionar este instrumento: pertenece a otro ECOE "
                "y no tienes rol de administrador o coeditor en él."
            ),
        )

    # Tool legado: regla de gracia sobre los eventos que hoy lo referencian.
    summary = summary or tool_reference_summary(db, tool.id)
    for event_id in summary["event_ids"]:
        if get_user_event_roles(db, user, event_id).intersection(wanted):
            return
    raise HTTPException(
        status_code=403,
        detail=(
            "Este instrumento no está asociado a ningún ECOE en el que tengas "
            "permiso de gestión; solo un administrador global puede modificarlo."
        ),
    )


# ── Patch de ítems in-place ───────────────────────────────────────────

def apply_tool_patch(db: Session, tool: AssessmentTool, payload) -> None:
    """Aplica el PATCH preservando ``AssessmentItem.id``.

    - cabecera (``name``, ``tool_type``, ``free_observation``, ``max_score``):
      solo los campos presentes en el payload.
    - ``items`` (si viene): update in-place por ``id``, alta de los nuevos,
      baja explícita de los ausentes. Nunca ``clear()`` + reinsert.
    """
    data = payload.model_dump(exclude_unset=True)
    for field in ("name", "tool_type", "free_observation", "max_score"):
        if field in data and data[field] is not None:
            setattr(tool, field, data[field])

    if payload.items is None:
        return

    existing = {item.id: item for item in tool.items}

    # Paso 1: mover los order_index vigentes a un rango negativo temporal para
    # no chocar con UniqueConstraint(tool_id, order_index) al reordenar.
    for offset, item in enumerate(tool.items, start=1):
        item.order_index = -offset
    db.flush()

    # Paso 2: aplicar el payload (id conocido → update; sin id o id ajeno → alta).
    seen_ids: set[int] = set()
    for spec in payload.items:
        if spec.id is not None and spec.id in existing:
            item = existing[spec.id]
            item.label = spec.label
            item.score_per_item = spec.score_per_item
            item.order_index = spec.order_index
            seen_ids.add(spec.id)
        else:
            tool.items.append(
                AssessmentItem(
                    label=spec.label,
                    score_per_item=spec.score_per_item,
                    order_index=spec.order_index,
                )
            )

    # Paso 3: baja de los ítems que estaban en BD y ya no vienen en el payload.
    for item in list(tool.items):
        if item.id is not None and item.id in existing and item.id not in seen_ids:
            tool.items.remove(item)

    db.flush()


# ── Serialización ─────────────────────────────────────────────────────

def serialize_instrument(tool: AssessmentTool, reference_count: int) -> dict:
    return {
        "id": tool.id,
        "name": tool.name,
        "tool_type": tool.tool_type,
        "max_score": tool.max_score,
        "free_observation": tool.free_observation,
        "created_by": tool.created_by,
        "origin_event_id": tool.origin_event_id,
        "archived": tool.archived,
        "reference_count": reference_count,
        "items": [
            {
                "id": item.id,
                "label": item.label,
                "score_per_item": item.score_per_item,
                "order_index": item.order_index,
            }
            for item in sorted(tool.items, key=lambda i: (i.order_index, i.id or 0))
        ],
    }
