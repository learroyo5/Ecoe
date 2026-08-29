"""Analítica del ECOE — endpoints de solo lectura sobre los datos servidos.

Hoy: psicometría (OPT-18). La puerta de autorización es la misma que `/results`
(`ensure_event_access(*ADMIN_EVENT_ROLE_CODES)`): coordinación / coeditor /
admin del evento. `corrector`, `evaluador` y `estudiante` no acceden.
"""

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.authorization import ADMIN_EVENT_ROLE_CODES, ensure_event_access
from app.services.dependencies import get_current_user
from app.services.psychometrics import build_psychometrics_block

router = APIRouter()


@router.get("/analytics/{ecoe_event_id}/psychometrics")
def get_psychometrics(
    ecoe_event_id: int,
    mode: Literal["ejecucion", "pilotaje"] = "ejecucion",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Métricas psicométricas del evento para `mode` (default `ejecucion`).

    `mode=ejecucion` usa la nota por estación snapshot-aware (congelada si el
    evento está cerrado); `mode=pilotaje` siempre calcula en vivo sobre los
    registros de pilotaje. Un `mode` fuera de `{ejecucion, pilotaje}` → 422.
    """
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return build_psychometrics_block(db, ecoe_event_id, mode)
