"""Candados por estado del ECOE sobre la estructura y la nómina (PROC-5).

La máquina de estados decide *cuándo* se aceptan registros operativos
(`ensure_submission_stage`); este módulo decide cuándo se puede seguir
tocando aquello sobre lo que esos registros se calculan:

- **Estructura** (estaciones, formularios, pautas asignadas, multimedia,
  tiempos, numeración y borrado de estudiantes): bloqueada desde `publicado`.
  Para cambiarla hay que despublicar, lo que obliga a revalidar.
- **Todo lo demás** (equipo, altas de estudiantes, datos descriptivos):
  bloqueado sólo con el evento `cerrado` / `archivado`, cuando el acta ya
  está congelada.
"""

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import AuditLog, ECOEEvent
from app.models.enums import ECOEStatus
from app.services.validation import ECOE_STATUS_LABELS

STRUCTURE_LOCKED_STATUSES = {
    ECOEStatus.publicado.value,
    ECOEStatus.en_ejecucion.value,
    ECOEStatus.cerrado.value,
    ECOEStatus.archivado.value,
}
FROZEN_STATUSES = {ECOEStatus.cerrado.value, ECOEStatus.archivado.value}

# Campos del evento que gobiernan el cronómetro y el circuito.
EVENT_STRUCTURE_FIELDS = {
    "station_time_minutes",
    "transition_time_minutes",
    "inter_round_pause_minutes",
    "circuit_mode",
    "total_groups",
}


def _status_label(ecoe_event: ECOEEvent) -> str:
    return ECOE_STATUS_LABELS.get(str(ecoe_event.status), str(ecoe_event.status))


def ensure_structure_editable(db: Session, ecoe_event_id: int, what: str) -> ECOEEvent:
    """409 si el evento ya está publicado o más allá."""
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if ecoe_event is None:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    status = str(ecoe_event.status)
    if status in FROZEN_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"El ECOE está {_status_label(ecoe_event).lower()}: no se puede {what}.",
        )
    if status in STRUCTURE_LOCKED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El ECOE está {_status_label(ecoe_event).lower()}: no se puede {what}. "
                "La estructura queda bloqueada desde la publicación; "
                "despublica el ECOE para modificarla."
            ),
        )
    return ecoe_event


def ensure_event_not_frozen(db: Session, ecoe_event_id: int, what: str) -> ECOEEvent:
    """409 sólo si el evento está cerrado o archivado."""
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if ecoe_event is None:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    if str(ecoe_event.status) in FROZEN_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"El ECOE está {_status_label(ecoe_event).lower()}: no se puede {what}.",
        )
    return ecoe_event


def audit_change(
    db: Session, user, action: str, target_type: str, target_id, payload: dict
) -> None:
    """Rastro de un cambio de estructura o nómina (PROC-14)."""
    db.add(AuditLog(
        user_email=user.email,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        payload=payload,
    ))


def commit_or_conflict(db: Session, message: str) -> None:
    """`commit` que traduce una violación de integridad en un 409 legible
    (PROC-13) en vez de un 500: típicamente, borrar algo que ya tiene registros."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=message) from exc
