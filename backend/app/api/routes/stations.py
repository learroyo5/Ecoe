"""Station management, templates, instruments, patients, bank, pilotage routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AssessmentTool,
    AssessmentItem,
    Station,
    StationTemplate,
    SimulatedPatient,
    StationBank,
    PilotRun,
    PilotRecord,
    AuditLog,
    LiveSession,
    ECOEEvent,
)
from app.models.enums import ECOEStatus, RoleCode, StationStatus
from app.schemas.common import (
    AssessmentToolCreate,
    AssessmentToolPatch,
    AssessmentToolRead,
    PilotRunCreate,
    PilotRunNotesUpdate,
    PilotRunRead,
    SimulatedPatientCreate,
    SimulatedPatientPatch,
    SimulatedPatientRead,
    StationBankCreate,
    StationBankRead,
    StationBankStatusUpdate,
    StationCreate,
    StationRead,
    StationTemplateCreate,
    StationTemplatePatch,
    StationTemplateRead,
)
from app.services.dependencies import get_current_user, require_roles
from app.services.ecoe import compute_ecoe_validation
from app.services.authorization import (
    ADMIN_EVENT_ROLE_CODES,
    ensure_event_access,
)
from app.services import content_bank
from app.services.instruments import (
    apply_tool_patch,
    ensure_tool_editable,
    ensure_tool_manage_permission,
    reference_counts,
    serialize_instrument,
    tool_reference_summary,
)

router = APIRouter()

# Roles that may read exam design content (templates, instruments,
# simulated patients, station bank). Students/evaluators receive only
# what they need through /student/access and /evaluator/context.
CONTENT_MANAGER_ROLES = ("admin_ecoe", "coeditor_docente", "coordinador_operativo")


def _reject_archived_tool(db: Session, assessment_tool_id: int | None) -> None:
    """Un instrumento archivado (OPT-7) no puede asignarse a estaciones nuevas
    ni re-asignarse; las estaciones que ya lo usan siguen funcionando."""
    if assessment_tool_id is None:
        return
    tool = db.get(AssessmentTool, assessment_tool_id)
    if tool and tool.archived:
        raise HTTPException(
            status_code=400,
            detail="El instrumento seleccionado está archivado. Restáuralo o elige otro.",
        )


def _reject_archived_template(db: Session, template_id: int | None) -> None:
    """Una plantilla archivada (OPT-7b) no puede asignarse a estaciones nuevas
    ni re-asignarse; las estaciones que ya la usan siguen funcionando."""
    if template_id is None:
        return
    template = db.get(StationTemplate, template_id)
    if template and template.archived:
        raise HTTPException(
            status_code=400,
            detail="La plantilla seleccionada está archivada. Restáurala o elige otra.",
        )


def _reject_archived_patient(db: Session, simulated_patient_id: int | None) -> None:
    """Una ficha de paciente simulado archivada (OPT-7b) no puede asignarse a
    estaciones nuevas ni re-asignarse."""
    if simulated_patient_id is None:
        return
    patient = db.get(SimulatedPatient, simulated_patient_id)
    if patient and patient.archived:
        raise HTTPException(
            status_code=400,
            detail="El paciente simulado seleccionado está archivado. Restáuralo o elige otro.",
        )

# ── Station Templates ───────────────────────────────────────────────────

@router.get("/templates", response_model=list[StationTemplateRead])
def list_templates(
    ecoe_event_id: int,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTENT_MANAGER_ROLES)),
):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    query = select(StationTemplate)
    if not include_archived:
        query = query.where(StationTemplate.archived.is_(False))
    templates = db.scalars(query.order_by(StationTemplate.id.desc())).all()
    counts = content_bank.reference_counts(db, "template", [t.id for t in templates])
    return [content_bank.serialize_template(t, counts.get(t.id, 0)) for t in templates]


@router.get("/templates/{template_id}", response_model=StationTemplateRead)
def get_template(
    template_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTENT_MANAGER_ROLES)),
):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    template = db.get(StationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    summary = content_bank.summary_for(db, template)
    return content_bank.serialize_template(template, summary["reference_count"])


@router.post("/templates", response_model=StationTemplateRead)
def create_template(
    payload: StationTemplateCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    template = StationTemplate(
        **payload.model_dump(),
        created_by=user.email,
        origin_event_id=ecoe_event_id,
    )
    db.add(template)
    db.flush()
    db.add(AuditLog(
        user_email=user.email, action="create_template",
        target_type="StationTemplate", target_id=str(template.id),
        payload={"ecoe_event_id": ecoe_event_id, "name": template.name},
    ))
    db.commit()
    db.refresh(template)
    return content_bank.serialize_template(template, 0)


@router.patch("/templates/{template_id}", response_model=StationTemplateRead)
def patch_template(
    template_id: int,
    payload: StationTemplatePatch,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    """UPDATE libre (sin gate de estado): el contenido no llega a runtime. La
    edición afecta a lo que verá el próximo diseñador que aplique la plantilla,
    no a las estaciones ya creadas (el Constructor copió los campos al aplicarla).
    """
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    template = db.get(StationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    summary = content_bank.summary_for(db, template)
    content_bank.ensure_content_manage_permission(db, user, template, summary)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.add(AuditLog(
        user_email=user.email, action="patch_template",
        target_type="StationTemplate", target_id=str(template.id),
        payload={"ecoe_event_id": ecoe_event_id},
    ))
    db.commit()
    db.refresh(template)
    summary = content_bank.summary_for(db, template)
    return content_bank.serialize_template(template, summary["reference_count"])


@router.delete("/templates/{template_id}", response_model=StationTemplateRead)
def archive_template(
    template_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    """Soft-delete: ``archived = True``. Idempotente."""
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    template = db.get(StationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    summary = content_bank.summary_for(db, template)
    content_bank.ensure_content_manage_permission(db, user, template, summary)
    if not template.archived:
        template.archived = True
        db.add(AuditLog(
            user_email=user.email, action="archive_template",
            target_type="StationTemplate", target_id=str(template.id),
            payload={"ecoe_event_id": ecoe_event_id},
        ))
        db.commit()
        db.refresh(template)
    return content_bank.serialize_template(template, summary["reference_count"])


@router.post("/templates/{template_id}/restore", response_model=StationTemplateRead)
def restore_template(
    template_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    template = db.get(StationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    summary = content_bank.summary_for(db, template)
    content_bank.ensure_content_manage_permission(db, user, template, summary)
    if template.archived:
        template.archived = False
        db.add(AuditLog(
            user_email=user.email, action="restore_template",
            target_type="StationTemplate", target_id=str(template.id),
            payload={"ecoe_event_id": ecoe_event_id},
        ))
        db.commit()
        db.refresh(template)
    return content_bank.serialize_template(template, summary["reference_count"])


@router.delete("/templates/{template_id}/purge")
def purge_template(
    template_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe")),
):
    """Hard-delete. Solo ``admin_ecoe`` / ``admin_global`` y solo si la plantilla
    tiene 0 referencias en ``stations`` y ``station_bank`` (si no → 409)."""
    ensure_event_access(db, user, ecoe_event_id, RoleCode.admin_ecoe.value)
    template = db.get(StationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    summary = content_bank.summary_for(db, template)
    content_bank.ensure_content_manage_permission(db, user, template, summary, require_admin=True)
    if summary["reference_count"] > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "No se puede eliminar definitivamente: la plantilla está "
                f"referenciada por {len(summary['station_ids'])} estación(es) y "
                f"{len(summary['bank_ids'])} entrada(s) del banco. Archívala."
            ),
        )
    db.add(AuditLog(
        user_email=user.email, action="purge_template",
        target_type="StationTemplate", target_id=str(template.id),
        payload={"ecoe_event_id": ecoe_event_id, "name": template.name},
    ))
    db.delete(template)
    db.commit()
    return {"deleted": True}


# ── Assessment Tools / Instruments ──────────────────────────────────────

@router.get("/instruments", response_model=list[AssessmentToolRead])
def list_instruments(
    ecoe_event_id: int,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTENT_MANAGER_ROLES)),
):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    query = select(AssessmentTool)
    if not include_archived:
        query = query.where(AssessmentTool.archived.is_(False))
    tools = db.scalars(query.order_by(AssessmentTool.id.desc())).all()
    counts = reference_counts(db, [tool.id for tool in tools])
    return [serialize_instrument(tool, counts.get(tool.id, 0)) for tool in tools]


@router.get("/instruments/{tool_id}", response_model=AssessmentToolRead)
def get_instrument(
    tool_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTENT_MANAGER_ROLES)),
):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    tool = db.get(AssessmentTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    summary = tool_reference_summary(db, tool.id)
    return serialize_instrument(tool, summary["reference_count"])


@router.post("/instruments", response_model=AssessmentToolRead)
def create_instrument(
    payload: AssessmentToolCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    tool = AssessmentTool(
        name=payload.name,
        tool_type=payload.tool_type,
        max_score=payload.max_score,
        free_observation=payload.free_observation,
        created_by=user.email,
        origin_event_id=ecoe_event_id,
    )
    db.add(tool)
    db.flush()
    for item in payload.items:
        db.add(AssessmentItem(
            tool_id=tool.id,
            label=item.label,
            score_per_item=item.score_per_item,
            order_index=item.order_index,
        ))
    db.add(AuditLog(
        user_email=user.email, action="create_instrument",
        target_type="AssessmentTool", target_id=str(tool.id),
        payload={"ecoe_event_id": ecoe_event_id, "name": tool.name},
    ))
    db.commit()
    db.refresh(tool)
    return serialize_instrument(tool, 0)


@router.patch("/instruments/{tool_id}", response_model=AssessmentToolRead)
def patch_instrument(
    tool_id: int,
    payload: AssessmentToolPatch,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    """Editar una pauta preservando ``AssessmentItem.id``.

    El banco es compartido: la edición afecta a toda estación que apunte al
    tool. El gate ``ensure_tool_editable`` lo acota a eventos aún en
    diseño/config (``EDIT_BLOCKING_STATUSES``), donde un cambio compartido es
    esperado. Un tool usado por un ECOE en pilotaje/publicado/ejecución/cerrado
    devuelve 409: hay que duplicar la pauta.
    """
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    tool = db.get(AssessmentTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    summary = tool_reference_summary(db, tool.id)
    ensure_tool_manage_permission(db, user, tool, summary)
    ensure_tool_editable(db, tool, summary)
    apply_tool_patch(db, tool, payload)
    db.add(AuditLog(
        user_email=user.email, action="patch_instrument",
        target_type="AssessmentTool", target_id=str(tool.id),
        payload={"ecoe_event_id": ecoe_event_id},
    ))
    db.commit()
    db.refresh(tool)
    summary = tool_reference_summary(db, tool.id)
    return serialize_instrument(tool, summary["reference_count"])


@router.delete("/instruments/{tool_id}", response_model=AssessmentToolRead)
def archive_instrument(
    tool_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    """Soft-delete: ``archived = True``. Idempotente."""
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    tool = db.get(AssessmentTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    summary = tool_reference_summary(db, tool.id)
    ensure_tool_manage_permission(db, user, tool, summary)
    if not tool.archived:
        ensure_tool_editable(db, tool, summary)
        tool.archived = True
        db.add(AuditLog(
            user_email=user.email, action="archive_instrument",
            target_type="AssessmentTool", target_id=str(tool.id),
            payload={"ecoe_event_id": ecoe_event_id},
        ))
        db.commit()
        db.refresh(tool)
    return serialize_instrument(tool, summary["reference_count"])


@router.post("/instruments/{tool_id}/restore", response_model=AssessmentToolRead)
def restore_instrument(
    tool_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    tool = db.get(AssessmentTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    summary = tool_reference_summary(db, tool.id)
    ensure_tool_manage_permission(db, user, tool, summary)
    if tool.archived:
        tool.archived = False
        db.add(AuditLog(
            user_email=user.email, action="restore_instrument",
            target_type="AssessmentTool", target_id=str(tool.id),
            payload={"ecoe_event_id": ecoe_event_id},
        ))
        db.commit()
        db.refresh(tool)
    return serialize_instrument(tool, summary["reference_count"])


@router.delete("/instruments/{tool_id}/purge")
def purge_instrument(
    tool_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe")),
):
    """Hard-delete. Solo ``admin_ecoe`` / ``admin_global`` y solo si el tool
    tiene 0 referencias en ``stations`` y ``station_bank`` (si no → 409)."""
    ensure_event_access(db, user, ecoe_event_id, RoleCode.admin_ecoe.value)
    tool = db.get(AssessmentTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    summary = tool_reference_summary(db, tool.id)
    ensure_tool_manage_permission(db, user, tool, summary, require_admin=True)
    if summary["reference_count"] > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "No se puede eliminar definitivamente: el instrumento está "
                f"referenciado por {len(summary['station_ids'])} estación(es) y "
                f"{len(summary['bank_ids'])} entrada(s) del banco. Archívalo."
            ),
        )
    db.add(AuditLog(
        user_email=user.email, action="purge_instrument",
        target_type="AssessmentTool", target_id=str(tool.id),
        payload={"ecoe_event_id": ecoe_event_id, "name": tool.name},
    ))
    db.delete(tool)
    db.commit()
    return {"deleted": True}


# ── Simulated Patients ─────────────────────────────────────────────────

@router.get("/simulated-patients", response_model=list[SimulatedPatientRead])
def list_patients(
    ecoe_event_id: int,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTENT_MANAGER_ROLES)),
):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    query = select(SimulatedPatient)
    if not include_archived:
        query = query.where(SimulatedPatient.archived.is_(False))
    patients = db.scalars(query.order_by(SimulatedPatient.id.desc())).all()
    counts = content_bank.reference_counts(db, "patient", [p.id for p in patients])
    return [content_bank.serialize_patient(p, counts.get(p.id, 0)) for p in patients]


@router.get("/simulated-patients/{patient_id}", response_model=SimulatedPatientRead)
def get_patient(
    patient_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTENT_MANAGER_ROLES)),
):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    patient = db.get(SimulatedPatient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente simulado no encontrado")
    summary = content_bank.summary_for(db, patient)
    return content_bank.serialize_patient(patient, summary["reference_count"])


@router.post("/simulated-patients", response_model=SimulatedPatientRead)
def create_patient(
    payload: SimulatedPatientCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    patient = SimulatedPatient(
        **payload.model_dump(),
        created_by=user.email,
        origin_event_id=ecoe_event_id,
    )
    db.add(patient)
    db.flush()
    db.add(AuditLog(
        user_email=user.email, action="create_simulated_patient",
        target_type="SimulatedPatient", target_id=str(patient.id),
        payload={"ecoe_event_id": ecoe_event_id, "character_name": patient.character_name},
    ))
    db.commit()
    db.refresh(patient)
    return content_bank.serialize_patient(patient, 0)


@router.patch("/simulated-patients/{patient_id}", response_model=SimulatedPatientRead)
def patch_patient(
    patient_id: int,
    payload: SimulatedPatientPatch,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    """UPDATE libre (sin gate de estado): la ficha no entra al cálculo de notas."""
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    patient = db.get(SimulatedPatient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente simulado no encontrado")
    summary = content_bank.summary_for(db, patient)
    content_bank.ensure_content_manage_permission(db, user, patient, summary)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.add(AuditLog(
        user_email=user.email, action="patch_simulated_patient",
        target_type="SimulatedPatient", target_id=str(patient.id),
        payload={"ecoe_event_id": ecoe_event_id},
    ))
    db.commit()
    db.refresh(patient)
    summary = content_bank.summary_for(db, patient)
    return content_bank.serialize_patient(patient, summary["reference_count"])


@router.delete("/simulated-patients/{patient_id}", response_model=SimulatedPatientRead)
def archive_patient(
    patient_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    """Soft-delete: ``archived = True``. Idempotente."""
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    patient = db.get(SimulatedPatient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente simulado no encontrado")
    summary = content_bank.summary_for(db, patient)
    content_bank.ensure_content_manage_permission(db, user, patient, summary)
    if not patient.archived:
        patient.archived = True
        db.add(AuditLog(
            user_email=user.email, action="archive_simulated_patient",
            target_type="SimulatedPatient", target_id=str(patient.id),
            payload={"ecoe_event_id": ecoe_event_id},
        ))
        db.commit()
        db.refresh(patient)
    return content_bank.serialize_patient(patient, summary["reference_count"])


@router.post("/simulated-patients/{patient_id}/restore", response_model=SimulatedPatientRead)
def restore_patient(
    patient_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    patient = db.get(SimulatedPatient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente simulado no encontrado")
    summary = content_bank.summary_for(db, patient)
    content_bank.ensure_content_manage_permission(db, user, patient, summary)
    if patient.archived:
        patient.archived = False
        db.add(AuditLog(
            user_email=user.email, action="restore_simulated_patient",
            target_type="SimulatedPatient", target_id=str(patient.id),
            payload={"ecoe_event_id": ecoe_event_id},
        ))
        db.commit()
        db.refresh(patient)
    return content_bank.serialize_patient(patient, summary["reference_count"])


@router.delete("/simulated-patients/{patient_id}/purge")
def purge_patient(
    patient_id: int,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe")),
):
    """Hard-delete. Solo ``admin_ecoe`` / ``admin_global`` y solo si la ficha
    tiene 0 referencias en ``stations`` y ``station_bank`` (si no → 409)."""
    ensure_event_access(db, user, ecoe_event_id, RoleCode.admin_ecoe.value)
    patient = db.get(SimulatedPatient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente simulado no encontrado")
    summary = content_bank.summary_for(db, patient)
    content_bank.ensure_content_manage_permission(db, user, patient, summary, require_admin=True)
    if summary["reference_count"] > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "No se puede eliminar definitivamente: el paciente simulado está "
                f"referenciado por {len(summary['station_ids'])} estación(es) y "
                f"{len(summary['bank_ids'])} entrada(s) del banco. Archívalo."
            ),
        )
    db.add(AuditLog(
        user_email=user.email, action="purge_simulated_patient",
        target_type="SimulatedPatient", target_id=str(patient.id),
        payload={"ecoe_event_id": ecoe_event_id, "character_name": patient.character_name},
    ))
    db.delete(patient)
    db.commit()
    return {"deleted": True}


# ── Station Bank ────────────────────────────────────────────────────────

@router.get("/station-bank", response_model=list[StationBankRead])
def list_station_bank(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(require_roles(*CONTENT_MANAGER_ROLES))):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(StationBank).order_by(StationBank.updated_at.desc(), StationBank.id.desc())).all()


@router.post("/station-bank", response_model=StationBankRead)
def create_station_bank(
    payload: StationBankCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    _reject_archived_tool(db, payload.assessment_tool_id)
    _reject_archived_template(db, payload.template_id)
    _reject_archived_patient(db, payload.simulated_patient_id)
    bank_station = StationBank(**payload.model_dump())
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


@router.put("/station-bank/{bank_station_id}", response_model=StationBankRead)
def update_station_bank(
    bank_station_id: int,
    payload: StationBankCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    bank_station = db.get(StationBank, bank_station_id)
    if not bank_station:
        raise HTTPException(status_code=404, detail="Estación de banco no encontrada")
    if (payload.assessment_tool_id is not None
            and payload.assessment_tool_id != bank_station.assessment_tool_id):
        _reject_archived_tool(db, payload.assessment_tool_id)
    if (payload.template_id is not None
            and payload.template_id != bank_station.template_id):
        _reject_archived_template(db, payload.template_id)
    if (payload.simulated_patient_id is not None
            and payload.simulated_patient_id != bank_station.simulated_patient_id):
        _reject_archived_patient(db, payload.simulated_patient_id)
    for field, value in payload.model_dump().items():
        setattr(bank_station, field, value)
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


@router.patch("/station-bank/{bank_station_id}/status", response_model=StationBankRead)
def update_station_bank_status(
    bank_station_id: int,
    payload: StationBankStatusUpdate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    bank_station = db.get(StationBank, bank_station_id)
    if not bank_station:
        raise HTTPException(status_code=404, detail="Estación de banco no encontrada")
    bank_station.status = payload.status
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


# ── Stations ────────────────────────────────────────────────────────────

@router.get("/stations/{ecoe_event_id}", response_model=list[StationRead])
def list_stations(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()


@router.post("/stations", response_model=StationRead)
def create_station(
    payload: StationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    _reject_archived_tool(db, payload.assessment_tool_id)
    _reject_archived_template(db, payload.template_id)
    _reject_archived_patient(db, payload.simulated_patient_id)
    next_station_number = (
        db.scalar(
            select(func.max(Station.station_number)).where(Station.ecoe_event_id == payload.ecoe_event_id)
        ) or 0
    ) + 1
    station = Station(
        **payload.model_dump(exclude={"station_number"}),
        station_number=next_station_number,
        station_time_minutes=ecoe_event.station_time_minutes,
        transition_time_minutes=ecoe_event.transition_time_minutes,
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.put("/stations/{station_id}", response_model=StationRead)
def update_station(
    station_id: int,
    payload: StationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estación no encontrada")
    ensure_event_access(db, user, station.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    if payload.ecoe_event_id != station.ecoe_event_id:
        raise HTTPException(
            status_code=400,
            detail="Una estación no puede trasladarse a otro ECOE mediante una actualización",
        )
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    if (payload.assessment_tool_id is not None
            and payload.assessment_tool_id != station.assessment_tool_id):
        _reject_archived_tool(db, payload.assessment_tool_id)
    if (payload.template_id is not None
            and payload.template_id != station.template_id):
        _reject_archived_template(db, payload.template_id)
    if (payload.simulated_patient_id is not None
            and payload.simulated_patient_id != station.simulated_patient_id):
        _reject_archived_patient(db, payload.simulated_patient_id)
    for field, value in payload.model_dump(exclude={"ecoe_event_id"}).items():
        setattr(station, field, value)
    station.station_time_minutes = ecoe_event.station_time_minutes
    station.transition_time_minutes = ecoe_event.transition_time_minutes
    # Solo recalcular el estado estructural (incompleta/lista_para_pilotaje) mientras
    # la estacion sigue en construccion. Una vez publicada (o en un estado operativo
    # posterior), editarla en el Constructor no debe regresarla a un estado previo:
    # eso desincroniza su badge del resto de las estaciones ya publicadas.
    if station.status in {
        StationStatus.en_diseno.value,
        StationStatus.incompleta.value,
        StationStatus.lista_para_pilotaje.value,
    } and station.expected_outcomes and station.pre_entry_instruction:
        station.status = (
            StationStatus.lista_para_pilotaje.value
            if station.assessment_tool_id or not station.requires_evaluator
            else StationStatus.incompleta.value
        )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.delete("/stations/{station_id}")
def delete_station(
    station_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estación no encontrada")
    ensure_event_access(db, user, station.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    db.delete(station)
    db.commit()
    return {"deleted": True}


# ── Pilotage ────────────────────────────────────────────────────────────

@router.post("/pilotage", response_model=PilotRunRead)
def create_pilotage(
    payload: PilotRunCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    validation = compute_ecoe_validation(db, ecoe_event)
    if not validation["can_pilot"]:
        raise HTTPException(status_code=400,
                            detail="El ECOE aún no cumple condiciones mínimas para pilotaje.")
    scope = payload.scope.strip().lower()
    if scope not in {"estacion", "circuito_completo"}:
        raise HTTPException(status_code=400, detail="Alcance de pilotaje no permitido.")
    event_station_ids = set(
        db.scalars(select(Station.id).where(Station.ecoe_event_id == payload.ecoe_event_id)).all()
    )
    if scope == "estacion":
        if len(payload.station_ids) != 1:
            raise HTTPException(status_code=400,
                                detail="Para pilotar una estación debes seleccionar exactamente una estación.")
        station_id = int(payload.station_ids[0])
        if station_id not in event_station_ids:
            raise HTTPException(status_code=400, detail="La estación seleccionada no pertenece a este ECOE.")
        station_issue = next(
            (issue for issue in validation["station_issues"] if int(issue["station_id"]) == station_id), None
        )
        if not station_issue or not station_issue["ready_for_pilot"]:
            raise HTTPException(status_code=400,
                                detail="La estación seleccionada aún no está lista para pilotaje individual.")
        station_ids = [station_id]
    else:
        has_station_pilot = db.scalar(
            select(func.count(PilotRun.id)).where(
                PilotRun.ecoe_event_id == payload.ecoe_event_id,
                PilotRun.scope == "estacion",
                PilotRun.archived.is_(False),
            )
        )
        if not has_station_pilot:
            raise HTTPException(status_code=400,
                                detail="No puedes pilotear el circuito completo sin haber realizado antes al menos un pilotaje individual de estación.")
        station_ids = list(event_station_ids)
    pilot_run = PilotRun(
        ecoe_event_id=payload.ecoe_event_id,
        name=payload.name,
        scope=scope,
        notes=payload.notes.strip(),
    )
    db.add(pilot_run)
    db.flush()
    for sid in station_ids:
        db.add(PilotRecord(pilot_run_id=pilot_run.id, station_id=sid,
                           payload={"status": "prueba"}, is_test=True))
    db.add(AuditLog(
        user_email=user.email, action="create_pilotage", target_type="PilotRun",
        target_id=str(pilot_run.id),
        payload={"ecoe_event_id": payload.ecoe_event_id, "scope": scope,
                 "station_ids": station_ids, "name": payload.name},
    ))
    db.commit()
    return pilot_run


@router.get("/pilotage/{ecoe_event_id}", response_model=list[PilotRunRead])
def list_pilotage(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(PilotRun).where(PilotRun.ecoe_event_id == ecoe_event_id)).all()


@router.patch("/pilotage/{pilot_run_id}/notes", response_model=PilotRunRead)
def update_pilotage_notes(
    pilot_run_id: int,
    payload: PilotRunNotesUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    run = db.get(PilotRun, pilot_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pilotaje no encontrado")
    ensure_event_access(db, user, run.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    run.notes = payload.notes.strip()
    db.add(run)
    db.add(AuditLog(
        user_email=user.email,
        action="update_pilotage_notes",
        target_type="PilotRun",
        target_id=str(run.id),
        payload={"ecoe_event_id": run.ecoe_event_id},
    ))
    db.commit()
    db.refresh(run)
    return run


@router.post("/pilotage/{pilot_run_id}/archive")
def archive_pilotage(
    pilot_run_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    run = db.get(PilotRun, pilot_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pilotaje no encontrado")
    ensure_event_access(db, user, run.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    run.archived = True
    db.add(run)
    db.commit()
    return {"archived": True}


@router.delete("/pilotage/{pilot_run_id}")
def delete_pilotage(
    pilot_run_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe")),
):
    run = db.get(PilotRun, pilot_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pilotaje no encontrado")
    ensure_event_access(db, user, run.ecoe_event_id, RoleCode.admin_ecoe.value)
    db.delete(run)
    db.commit()
    return {"deleted": True}
