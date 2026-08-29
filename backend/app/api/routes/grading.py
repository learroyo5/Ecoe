"""Manual grading of student form responses (content managers and correctores)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    ECOEEvent,
    StaffAssignment,
    Station,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, RoleCode, SessionMode
from app.schemas.common import ManualGradeSubmit
from app.services.authorization import ensure_event_access
from app.services.dependencies import require_roles
from app.services.grading import apply_manual_scores, pending_manual_keys
from app.utils.helpers import normalize_email
from app.utils.serializers import serialize_assessment_tool

router = APIRouter()

# admin_ecoe / coeditor_docente corrigen cualquier estación del evento; un
# `corrector` solo las estaciones de evaluación diferida que tiene asignadas.
GRADING_ROLES = (
    RoleCode.admin_ecoe.value,
    RoleCode.coeditor_docente.value,
    RoleCode.corrector.value,
)
FULL_GRADING_ROLES = {RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value}

# Una vez cerrado/archivado el evento, los resultados están consolidados: la
# corrección tardía queda prohibida. Para rectificar una nota hay que reabrir el
# evento con un retroceso de estado (permitido por el grafo).
CLOSED_EVENT_STATUSES = {ECOEStatus.cerrado.value, ECOEStatus.archivado.value}


def _corrector_station_scope(
    db: Session, user, ecoe_event_id: int, event_roles: set[str]
) -> set[int] | None:
    """Estaciones que el actor puede corregir, o None si puede corregir todas."""
    if event_roles & FULL_GRADING_ROLES:
        return None
    assignment = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalize_email(user.email),
            StaffAssignment.role_code == RoleCode.corrector.value,
        )
    )
    return {int(sid) for sid in (assignment.station_ids or []) if sid} if assignment else set()


def _grading_scope_payload(station_scope: set[int] | None) -> dict:
    """Objeto `scope` que la UI usa para diferenciar los empty-states.

    - `station_scope is None` → el actor es admin/coeditor: ve todo el evento.
    - `station_scope == set()` → es `corrector` pero sin `StaffAssignment`
      (o con `station_ids` vacío): H-corr-6, la UI le dice "pedí estaciones".
    - `station_scope` con ids → corrector con asignación real.
    """
    if station_scope is None:
        return {"is_corrector": False, "has_assignment": True, "assigned_station_ids": []}
    return {
        "is_corrector": True,
        "has_assignment": bool(station_scope),
        "assigned_station_ids": sorted(station_scope),
    }


def _scoped_pending_responses(
    db: Session, ecoe_event_id: int, station_scope: set[int] | None
) -> list[StudentResponse]:
    """Respuestas con corrección manual pendiente dentro del scope del actor,
    en el mismo orden FIFO que la cola (`submitted_at ASC, id ASC`)."""
    filters = [
        StudentResponse.ecoe_event_id == ecoe_event_id,
        StudentResponse.mode == SessionMode.ejecucion.value,
        StudentResponse.max_score.is_not(None),
    ]
    if station_scope is not None:
        filters.append(StudentResponse.station_id.in_(station_scope))
    responses = db.scalars(
        select(StudentResponse)
        .where(*filters)
        .order_by(StudentResponse.submitted_at.asc(), StudentResponse.id.asc())
    ).all()
    return [response for response in responses if pending_manual_keys(response)]


@router.get("/grading/{ecoe_event_id}")
def list_gradable_responses(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*GRADING_ROLES)),
):
    event_roles = ensure_event_access(db, user, ecoe_event_id, *GRADING_ROLES)
    station_scope = _corrector_station_scope(db, user, ecoe_event_id, event_roles)
    # La corrección diferida solo aplica a la ejecución real: las respuestas
    # de pilotaje no entran a la cola (corregirlas sería trabajo perdido y no
    # alimentan el consolidado).
    filters = [
        StudentResponse.ecoe_event_id == ecoe_event_id,
        StudentResponse.mode == SessionMode.ejecucion.value,
        StudentResponse.max_score.is_not(None),
    ]
    scope_payload = _grading_scope_payload(station_scope)
    if station_scope is not None:
        if not station_scope:
            # Corrector sin estaciones asignadas: devolvemos la lista vacía pero
            # con el objeto `scope` para que la UI lo distinga de "todo corregido".
            return {
                "responses": [],
                "pending_count": 0,
                "scope": scope_payload,
                "pending_by_station": {},
            }
        filters.append(StudentResponse.station_id.in_(station_scope))
    responses = db.scalars(
        select(StudentResponse)
        .where(*filters)
        .order_by(StudentResponse.submitted_at.asc(), StudentResponse.id.asc())
    ).all()
    students = {
        student.id: student
        for student in db.scalars(
            select(Student).where(Student.ecoe_event_id == ecoe_event_id)
        ).all()
    }
    stations = {
        station.id: station
        for station in db.scalars(
            select(Station).where(Station.ecoe_event_id == ecoe_event_id)
        ).all()
    }
    # La pauta (AssessmentTool) de la estación viaja como referencia visual —
    # NO cambia la puntuación (FASE1 §Decisión 4: `apply_manual_scores` sigue
    # siendo número libre `[0, max]`). Se cachea por `station_id` para no
    # repetir el SELECT en cada fila de la misma estación.
    tool_cache: dict[int, dict | None] = {}

    def _assessment_tool_for(station: Station | None) -> dict | None:
        if station is None or not station.assessment_tool_id:
            return None
        if station.id not in tool_cache:
            tool_cache[station.id] = serialize_assessment_tool(db, station.assessment_tool_id)
        return tool_cache[station.id]

    pending_by_station: dict[int, dict] = {}
    rows = []
    for response in responses:
        student = students.get(response.student_id)
        station = stations.get(response.station_id)
        pending = pending_manual_keys(response)
        if station is not None:
            bucket = pending_by_station.setdefault(
                station.id,
                {
                    "station_number": station.station_number,
                    "station_name": station.name,
                    "pending": 0,
                    "total": 0,
                },
            )
            bucket["total"] += 1
            if pending:
                bucket["pending"] += 1
        rows.append({
            "response_id": response.id,
            "mode": str(response.mode),
            # OPT-20 F4 (D4): origen del envío para que el corrector sepa si la
            # respuesta fue automática/en blanco y no una entrega deliberada.
            "submission_kind": response.submission_kind or "manual",
            "by_contingency": response.by_contingency,
            "student_id": response.student_id,
            "student_name": f"{student.name} {student.last_name}" if student else "",
            "student_ecoe_number": student.ecoe_number if student else "",
            "station_id": response.station_id,
            "station_number": station.station_number if station else None,
            "station_name": station.name if station else "",
            "submitted_at": response.submitted_at.isoformat(),
            "answers": response.answers,
            "grading": response.grading,
            "pending_questions": pending,
            "score_obtained": response.score_obtained,
            "max_score": response.max_score,
            "graded_by_email": response.graded_by_email,
            "graded_at": response.graded_at.isoformat() if response.graded_at else None,
            "questions": (
                (station.student_form_definition or {}).get("questions", []) if station else []
            ),
            "assessment_tool": _assessment_tool_for(station),
        })
    pending_count = sum(1 for row in rows if row["pending_questions"])
    return {
        "responses": rows,
        "pending_count": pending_count,
        "scope": scope_payload,
        "pending_by_station": pending_by_station,
    }


@router.post("/grading/responses/{response_id}")
def grade_response(
    response_id: int,
    payload: ManualGradeSubmit,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*GRADING_ROLES)),
):
    response = db.get(StudentResponse, response_id)
    if not response:
        raise HTTPException(status_code=404, detail="Respuesta no encontrada")
    ecoe_event = db.get(ECOEEvent, response.ecoe_event_id)
    if ecoe_event is not None and str(ecoe_event.status) in CLOSED_EVENT_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="El ECOE está cerrado; los resultados están consolidados",
        )
    event_roles = ensure_event_access(db, user, response.ecoe_event_id, *GRADING_ROLES)
    station_scope = _corrector_station_scope(db, user, response.ecoe_event_id, event_roles)
    if station_scope is not None and response.station_id not in station_scope:
        raise HTTPException(
            status_code=403,
            detail="No tienes esta estación asignada para corrección diferida",
        )
    apply_manual_scores(response, payload.scores, graded_by_email=user.email)
    db.add(response)
    db.add(AuditLog(
        user_email=user.email,
        action="grade_student_response",
        target_type="StudentResponse",
        target_id=str(response.id),
        payload={
            "ecoe_event_id": response.ecoe_event_id,
            "scores": payload.scores,
            "score_obtained": response.score_obtained,
        },
    ))
    db.commit()
    db.refresh(response)

    # El cliente ya no re-fetchea la lista entera tras guardar: le devolvemos
    # la próxima fila pendiente en su scope (FIFO, después de la recién
    # corregida) y cuántas le quedan. Misma query scopeada que la cola.
    remaining = _scoped_pending_responses(db, response.ecoe_event_id, station_scope)
    after = [
        pending
        for pending in remaining
        if (pending.submitted_at, pending.id) > (response.submitted_at, response.id)
    ]
    next_row = after[0] if after else None
    return {
        "graded": True,
        "response_id": response.id,
        "score_obtained": response.score_obtained,
        "max_score": response.max_score,
        "next": {"response_id": next_row.id} if next_row else None,
        "pending_remaining": len(remaining),
    }


def _is_blank_auto(response: StudentResponse) -> bool:
    """¿Es un autoenvío realmente en blanco (todas las manuales pendientes sin
    responder)? Una respuesta `auto` con al menos un ítem manual respondido —o
    ya corregida— NO entra al bulk: la revisa el corrector a mano."""
    if (response.submission_kind or "manual") != "auto":
        return False
    pending = pending_manual_keys(response)
    if not pending:
        return False
    grading = response.grading or {}
    return all(
        isinstance(grading.get(key), dict) and grading[key].get("answered") is False
        for key in pending
    )


@router.post("/grading/{ecoe_event_id}/stations/{station_id}/zero-blank")
def zero_blank_auto_responses(
    ecoe_event_id: int,
    station_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*GRADING_ROLES)),
):
    """Puntúa 0 los autoenvíos en blanco de una estación de una sola pasada.

    Espejo del gate de `grade_response`: solo bloquea `cerrado`/`archivado`
    (la corrección diferida es legítima con el evento `en_ejecucion`). Respeta
    el scope del corrector y deja un `AuditLog` por respuesta —trazabilidad
    idéntica a la corrección individual—. Selección estricta: `mode=ejecucion`,
    `submission_kind="auto"`, y todas las preguntas manuales pendientes con
    `answered is False`.
    """
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if ecoe_event is None:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    if str(ecoe_event.status) in CLOSED_EVENT_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="El ECOE está cerrado; los resultados están consolidados",
        )
    event_roles = ensure_event_access(db, user, ecoe_event_id, *GRADING_ROLES)
    station_scope = _corrector_station_scope(db, user, ecoe_event_id, event_roles)
    if station_scope is not None and station_id not in station_scope:
        raise HTTPException(
            status_code=403,
            detail="No tienes esta estación asignada para corrección diferida",
        )
    station = db.get(Station, station_id)
    if station is None or station.ecoe_event_id != ecoe_event_id:
        raise HTTPException(status_code=404, detail="La estación no pertenece a este ECOE")

    candidates = db.scalars(
        select(StudentResponse)
        .where(
            StudentResponse.ecoe_event_id == ecoe_event_id,
            StudentResponse.station_id == station_id,
            StudentResponse.mode == SessionMode.ejecucion.value,
            StudentResponse.max_score.is_not(None),
            StudentResponse.submission_kind == "auto",
        )
        .order_by(StudentResponse.submitted_at.asc(), StudentResponse.id.asc())
    ).all()

    zeroed_ids: list[int] = []
    for response in candidates:
        if not _is_blank_auto(response):
            continue
        pending = pending_manual_keys(response)
        apply_manual_scores(
            response, {key: 0.0 for key in pending}, graded_by_email=user.email
        )
        db.add(response)
        db.add(AuditLog(
            user_email=user.email,
            action="grade_student_response",
            target_type="StudentResponse",
            target_id=str(response.id),
            payload={
                "ecoe_event_id": ecoe_event_id,
                "station_id": station_id,
                "bulk": "zero_blank",
                "scores": {key: 0.0 for key in pending},
                "score_obtained": response.score_obtained,
            },
        ))
        zeroed_ids.append(response.id)

    db.commit()

    pending_remaining = len(
        _scoped_pending_responses(db, ecoe_event_id, station_scope)
    )
    return {
        "zeroed": len(zeroed_ids),
        "response_ids": zeroed_ids,
        "pending_remaining": pending_remaining,
    }
