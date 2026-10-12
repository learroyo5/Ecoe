"""Student management routes."""

import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import EvaluatorRecord, Student, StudentResponse
from app.models.enums import ECOEStatus, RoleCode, SessionMode
from app.schemas.common import Page, StudentCreate, StudentRead, StudentStatusUpdate
from app.services.dependencies import get_current_user, require_roles
from app.utils.files import MAX_IMPORT_FILE_BYTES
from app.services.student_import import apply_import_plan, build_import_plan, read_roster
from app.services.authorization import ensure_event_access
from app.utils.helpers import (
    format_ecoe_number,
    normalize_ecoe_lookup,
    normalize_email,
    normalize_rut,
    next_student_ecoe_number,
)
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, paginate_query

from app.services.event_lock import (
    audit_change,
    commit_or_conflict,
    ensure_event_not_frozen,
    ensure_structure_editable,
)

router = APIRouter()


def _student_has_execution_records(db: Session, student: Student) -> bool:
    for model in (EvaluatorRecord, StudentResponse):
        if db.scalar(
            select(func.count()).select_from(model).where(
                model.ecoe_event_id == student.ecoe_event_id,
                model.student_id == student.id,
                model.mode == SessionMode.ejecucion.value,
            )
        ):
            return True
    return False



@router.get("/students/{ecoe_event_id}", response_model=Page[StudentRead])
def list_students(
    ecoe_event_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    stmt = (
        select(Student)
        .where(Student.ecoe_event_id == ecoe_event_id)
        .order_by(Student.is_active.desc(), Student.ecoe_number.asc(), Student.id.asc())
    )
    return paginate_query(db, stmt, page=page, page_size=page_size)


@router.post("/students", response_model=StudentRead)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    ensure_event_not_frozen(db, payload.ecoe_event_id, "agregar estudiantes")
    rut = normalize_rut(payload.rut)
    email = normalize_email(payload.email)
    # Se compara en forma canónica: «12.345.678-9» y «12345678-9» son el mismo.
    existing = any(
        normalize_rut(other) == rut
        for other in db.scalars(
            select(Student.rut).where(Student.ecoe_event_id == payload.ecoe_event_id)
        ).all()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un estudiante con ese RUT en este ECOE")
    student = Student(**payload.model_dump(exclude={"rut", "email", "ecoe_number", "registration_number"}),
                      rut=rut, email=email,
                      registration_number=(payload.registration_number or "").strip()[:32] or None,
                      ecoe_number=next_student_ecoe_number(db, payload.ecoe_event_id))
    db.add(student)
    db.flush()
    audit_change(db, user, "create_student", "Student", student.id,
                 {"ecoe_event_id": student.ecoe_event_id, "ecoe_number": student.ecoe_number})
    db.commit()
    db.refresh(student)
    return student


@router.patch("/students/{student_id}/status", response_model=StudentRead)
def update_student_status(
    student_id: int,
    payload: StudentStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    ensure_event_access(db, user, student.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    ecoe_event = ensure_event_not_frozen(db, student.ecoe_event_id, "cambiar el estado de un estudiante")
    if (
        str(ecoe_event.status) == ECOEStatus.en_ejecucion.value
        and not payload.is_active
        and _student_has_execution_records(db, student)
    ):
        # Suspender saca al estudiante de Resultados: con registros de la
        # ejecución real eso haría desaparecer notas ya tomadas.
        raise HTTPException(
            status_code=409,
            detail=(
                "Este estudiante ya tiene registros en la ejecución; "
                "no se puede suspender mientras el ECOE está en ejecución."
            ),
        )
    previous_active = student.is_active
    student.is_active = payload.is_active
    db.add(student)
    audit_change(db, user, "update_student_status", "Student", student.id,
                 {"ecoe_event_id": student.ecoe_event_id, "from": previous_active, "to": payload.is_active})
    db.commit()
    db.refresh(student)
    return student


@router.delete("/students/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    ensure_event_access(db, user, student.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    ensure_structure_editable(db, student.ecoe_event_id, "borrar estudiantes (suspéndelo en su lugar)")
    audit_change(db, user, "delete_student", "Student", student.id,
                 # Sólo identificadores internos y el número ECOE: el rastro no
                 # debe duplicar datos personales (RUT, nombre) — H13.
                 {"ecoe_event_id": student.ecoe_event_id, "ecoe_number": student.ecoe_number})
    db.delete(student)
    commit_or_conflict(
        db, "El estudiante tiene registros asociados y no puede borrarse; suspéndelo en su lugar.")
    return {"deleted": True}


@router.post("/students/{ecoe_event_id}/deduplicate-rut")
def deduplicate_students_by_rut(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    ensure_structure_editable(db, ecoe_event_id, "depurar la nómina")
    students = db.scalars(
        select(Student)
        .where(Student.ecoe_event_id == ecoe_event_id)
        .order_by(Student.created_at.asc(), Student.id.asc())
    ).all()
    seen_ruts: set[str] = set()
    removed = 0
    for student in students:
        rut = normalize_rut(student.rut)
        if not rut:
            continue
        if rut in seen_ruts:
            db.delete(student)
            removed += 1
            continue
        seen_ruts.add(rut)
    audit_change(db, user, "deduplicate_students", "ECOEEvent", ecoe_event_id,
                 {"ecoe_event_id": ecoe_event_id, "removed": removed})
    commit_or_conflict(
        db, "Hay estudiantes duplicados con registros asociados; resuélvelos manualmente.")
    return {"removed": removed}


@router.post("/students/{ecoe_event_id}/renumber")
def renumber_students(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    ensure_structure_editable(db, ecoe_event_id, "renumerar a los estudiantes")
    students = db.scalars(
        select(Student)
        .where(Student.ecoe_event_id == ecoe_event_id)
        .order_by(Student.created_at.asc(), Student.id.asc())
    ).all()
    if not students:
        return {"updated": 0}
    width = max(3, len(str(len(students))))
    for index, student in enumerate(students, start=1):
        student.ecoe_number = format_ecoe_number(index, width)
        db.add(student)
    audit_change(db, user, "renumber_students", "ECOEEvent", ecoe_event_id,
                 {"ecoe_event_id": ecoe_event_id, "updated": len(students)})
    db.commit()
    return {"updated": len(students)}


@router.post("/students/import")
async def import_students(
    ecoe_event_id: int,
    dry_run: bool = False,
    distribution: str | None = Query(default=None, pattern="^(file|halves|first)$"),
    use_list_numbers: bool | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    """Carga la nómina desde la plantilla o desde el listado oficial de curso.

    Con ``dry_run`` devuelve el plan (qué se cargaría, con qué número y en
    qué circuito) sin escribir nada; la carga real aplica ese mismo plan.
    """
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    ensure_event_not_frozen(db, ecoe_event_id, "importar estudiantes")
    content = await file.read(MAX_IMPORT_FILE_BYTES + 1)
    roster = read_roster(file.filename or "", content)
    plan = build_import_plan(
        db, ecoe_event_id, roster,
        distribution=distribution, use_list_numbers=use_list_numbers,
    )
    counts = plan["counts"]
    summary = {
        "skipped_rut_duplicate": counts.get("ya_cargado", 0) + counts.get("repetido", 0),
        "skipped_missing_data": counts.get("sin_rut", 0) + counts.get("sin_correo", 0)
        + counts.get("sin_nombre", 0),
    }
    summary["skipped"] = summary["skipped_rut_duplicate"] + summary["skipped_missing_data"]
    if dry_run:
        return {"dry_run": True, "imported": 0, **summary, **plan}
    imported = apply_import_plan(db, ecoe_event_id, plan)
    audit_change(db, user, "import_students", "ECOEEvent", ecoe_event_id,
                 {"ecoe_event_id": ecoe_event_id, "imported": len(imported),
                  "filename": (file.filename or "")[:255], "source": plan["source"],
                  "distribution": plan["distribution"], "per_circuit": plan["per_circuit"],
                  "use_list_numbers": plan["use_list_numbers"]})
    commit_or_conflict(db, "La nómina cambió mientras se importaba. Vuelve a cargar el archivo.")
    return {
        "dry_run": False,
        "imported": len(imported),
        **summary,
        "per_circuit": plan["per_circuit"],
        "with_warnings": plan["with_warnings"],
    }
