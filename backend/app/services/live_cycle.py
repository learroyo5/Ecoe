"""M1 · Máquina de fases explícita del circuito automático (F1).

Cuando ``LiveSession.auto_mode`` está activo, este módulo avanza el circuito
sin acción del operador:

    running(estación i) → transition → running(estación i+1) → …
    → running(estación N) → round_pause → running(estación 1, ronda+1) → …
    → running(estación N, última ronda) → circuit_complete

``advance_if_expired`` es determinista, idempotente y hace *fast-forward*: si
nadie polleó en un rato, una sola llamada recorre todas las fases vencidas
hasta la actual. NO es la autoridad del reloj —``phase_started_at`` + duración
lo es (``compute_remaining_seconds``)— sólo decide la siguiente fase.

Deliberadamente sin scheduler: el avance lo dispara el mismo polling que ya
existe en los context endpoints operativos (patrón OPT-20 F2) y en
``POST /live/control``. Un ticker best-effort para el timbre puntual es F2.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import ECOEEvent, LiveSession, Station, Student
from app.models.enums import ECOEStatus
from app.services.live_sweep import sweep_expired_phases
from app.utils.clock import utcnow_naive
from app.utils.helpers import SUBMISSION_GRACE_SECONDS

# Fases sobre las que el ciclo automático puede avanzar. Fuera de estas
# (idle/ready/paused/circuit_complete) el operador tiene el control.
AUTO_ADVANCE_STATUSES = {"running", "transition", "round_pause"}
_RUNNABLE_EVENT_STATUSES = {
    ECOEStatus.en_pilotaje.value,
    ECOEStatus.en_ejecucion.value,
}
_MAX_FASTFORWARD_STEPS = 500


def station_slot_count(db: Session, ecoe_event_id: int) -> int:
    """Número de estaciones del circuito (station_number distintos)."""
    return db.scalar(
        select(func.count(func.distinct(Station.station_number))).where(
            Station.ecoe_event_id == ecoe_event_id
        )
    ) or 0


def active_student_count(db: Session, ecoe_event_id: int) -> int:
    return db.scalar(
        select(func.count(Student.id)).where(
            Student.ecoe_event_id == ecoe_event_id,
            Student.is_active.is_(True),
        )
    ) or 0


def compute_total_rounds(db: Session, ecoe_event_id: int) -> int:
    """⌈estudiantes_activos / nº estaciones⌉ — nunca menos de 1."""
    slots = station_slot_count(db, ecoe_event_id) or 1
    students = active_student_count(db, ecoe_event_id)
    if students <= 0:
        return 1
    return max(1, -(-students // slots))  # ceil division


def _phase_deadline(session: LiveSession):
    """Instante nominal de fin de la fase automática actual, o ``None``."""
    if session.phase_started_at is None:
        return None
    if str(session.status) not in AUTO_ADVANCE_STATUSES:
        return None
    return session.phase_started_at + timedelta(seconds=session.remaining_seconds or 0)


def _advance_one(session: LiveSession, *, slots: int, now) -> tuple[bool, str | None]:
    """Aplica exactamente una transición de fase si la actual ya venció.

    Devuelve ``(avanzó, timbre)`` donde ``timbre`` es ``"end"`` / ``"start"`` /
    ``None``. No toca la BD: el llamador persiste y barre.
    """
    status = str(session.status)
    deadline = _phase_deadline(session)
    if deadline is None or now < deadline:
        return False, None

    total_rounds = session.total_rounds or 1

    if status == "running":
        if session.current_station_index < slots:
            session.status = "transition"
            session.current_station_index += 1
            session.remaining_seconds = session.transition_time_seconds
            session.phase_started_at = deadline
            return True, "end"
        # Terminó la última estación de la ronda.
        if session.current_round < total_rounds:
            session.status = "round_pause"
            session.current_station_index = 1
            session.remaining_seconds = session.inter_round_pause_seconds
            session.phase_started_at = deadline
            return True, "end"
        session.status = "circuit_complete"
        session.remaining_seconds = 0
        session.phase_started_at = None
        return True, "end"

    if status == "transition":
        session.status = "running"
        session.remaining_seconds = session.station_time_seconds
        session.phase_started_at = deadline
        return True, "start"

    if status == "round_pause":
        session.status = "running"
        session.current_round += 1
        session.current_station_index = 1
        session.remaining_seconds = session.station_time_seconds
        session.phase_started_at = deadline
        return True, "start"

    return False, None


def advance_if_expired(
    db: Session, ecoe_event: ECOEEvent, *, now=None, commit: bool = False
) -> dict:
    """Avanza el circuito automático mientras la fase en curso esté vencida.

    No-op si ``auto_mode`` está apagado, si el evento no está en
    pilotaje/ejecución, si el operador pausó, o si la fase todavía no vence.

    Con ``commit=False`` (por defecto) el llamador es dueño de la transacción
    (``POST /live/control``). Los lectores perezosos (context endpoints) pasan
    ``commit=True`` para persistir el avance ellos mismos.
    """
    result = {"advanced": 0, "bells": [], "status": None}

    session = db.scalar(
        select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event.id).limit(1)
    )
    if session is None:
        return result
    result["status"] = session.status
    if not session.auto_mode:
        return result
    if str(ecoe_event.status) not in _RUNNABLE_EVENT_STATUSES:
        return result
    if str(session.status) not in AUTO_ADVANCE_STATUSES:
        return result

    now = now or utcnow_naive()
    slots = station_slot_count(db, ecoe_event.id) or 1

    steps = 0
    while steps < _MAX_FASTFORWARD_STEPS:
        left_running = str(session.status) == "running"
        advanced, bell = _advance_one(session, slots=slots, now=now)
        if not advanced:
            break
        steps += 1
        if bell:
            result["bells"].append(bell)
        if left_running:
            # Una fase de trabajo acaba de cerrar: finalizar sus check-ins
            # ahora, mientras la sesión aún refleja "fase terminada"
            # (transition / round_pause / circuit_complete), antes de rodar
            # hacia la siguiente fase de estación.
            db.add(session)
            db.flush()
            sweep_expired_phases(
                db,
                ecoe_event,
                force=False,
                grace_seconds=SUBMISSION_GRACE_SECONDS,
                commit=False,
            )
        if str(session.status) not in AUTO_ADVANCE_STATUSES:
            break

    if steps:
        db.add(session)
        db.flush()
        if commit:
            db.commit()
            db.refresh(session)

    result["advanced"] = steps
    result["status"] = session.status
    return result


def advance_and_sweep(db: Session, ecoe_event: ECOEEvent) -> dict:
    """Uso perezoso desde los context endpoints: avanza el ciclo (si aplica) y
    luego corre el barrido OPT-20 F2 estándar. Preserva el comportamiento de
    barrido cuando ``auto_mode`` está apagado.
    """
    advance_if_expired(db, ecoe_event)
    return sweep_expired_phases(db, ecoe_event)
