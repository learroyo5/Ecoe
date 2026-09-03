from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    """Shape returned by utils.pagination.paginate_query."""

    items: list[ItemT]
    total: int
    page: int
    page_size: int
    pages: int


class Token(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    user: dict[str, Any]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class DashboardSummary(BaseModel):
    active_ecoe: dict[str, Any]
    totals: dict[str, int | float]
    validation: dict[str, Any]
    timeline: list[dict[str, Any]]
    live_panel: dict[str, Any]


class ECOEEventBase(BaseModel):
    name: str
    date: date
    course_name: str
    school_name: str
    responsible_teacher: str
    contact_email: EmailStr
    circuit_mode: str
    station_time_minutes: float = Field(ge=0.1)
    transition_time_minutes: float = Field(ge=0)
    # M1: pausa de cambio de estudiantes entre rondas del circuito automático.
    inter_round_pause_minutes: float = Field(default=5, ge=0)
    total_groups: int = Field(ge=1)
    passing_reference_percent: float = Field(default=60, ge=0, le=100)


class ECOEEventCreate(ECOEEventBase):
    pass


class ECOEEventUpdate(ECOEEventBase):
    status: str


class ECOEEventRead(ECOEEventBase, ORMBase):
    id: int
    status: str
    # OPT-11b: se derivan en el handler a partir de las filas reales — cantidad
    # de estaciones del evento y de estudiantes activos. No son input del
    # cliente ni se leen de las columnas homónimas legadas de `ecoe_events`.
    total_stations: int
    total_students: int
    created_at: datetime
    updated_at: datetime


class ECOETimingUpdate(BaseModel):
    station_time_minutes: float = Field(ge=0.1)
    transition_time_minutes: float = Field(ge=0)
    inter_round_pause_minutes: float | None = Field(default=None, ge=0)
    sync_existing_stations: bool = True


class ECOEDuplicateOptions(BaseModel):
    name: str = ""
    new_date: date | None = None
    copy_evaluators: bool = False


class StudentBase(BaseModel):
    ecoe_event_id: int
    name: str
    last_name: str
    rut: str
    email: EmailStr
    ecoe_number: str = ""
    group_name: str
    circuit_name: str


class StudentCreate(StudentBase):
    pass


class StudentRead(StudentBase, ORMBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StudentStatusUpdate(BaseModel):
    is_active: bool


class StaffBase(BaseModel):
    ecoe_event_id: int
    name: str
    last_name: str
    email: EmailStr
    role_code: str
    station_ids: list[int] = []


class StaffCreate(StaffBase):
    pass


class StaffRead(StaffBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime


class StaffUpdate(BaseModel):
    role_code: str
    station_ids: list[int] = []


class EventMemberInvite(BaseModel):
    ecoe_event_id: int
    # Only needed when the email has no institutional account yet: an existing
    # account owns its name, so the client is not asked to retype it.
    name: str = Field(default="", max_length=128)
    last_name: str = Field(default="", max_length=128)
    email: EmailStr
    role_code: str
    station_ids: list[int] = []


class EventMemberAccessReset(BaseModel):
    ecoe_event_id: int
    email: EmailStr


class InvitationActivation(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class AssessmentItemInput(BaseModel):
    # `id` opcional: en el PATCH identifica un ítem existente para actualizarlo
    # in-place (preservando la clave usada por EvaluatorRecord.answers). El POST
    # de creación ignora cualquier `id` entrante.
    id: int | None = None
    label: str
    score_per_item: float
    order_index: int


class AssessmentItemRead(ORMBase):
    id: int
    label: str
    score_per_item: float
    order_index: int


class AssessmentToolCreate(BaseModel):
    name: str
    tool_type: str
    max_score: float
    free_observation: bool = True
    items: list[AssessmentItemInput]


class AssessmentToolPatch(BaseModel):
    """PATCH parcial de un instrumento (OPT-7).

    Todos los campos son opcionales. Si ``items`` viene, reemplaza la lista con
    semántica in-place: los ítems con ``id`` conocido se actualizan, los nuevos
    se agregan y los ausentes se eliminan (ver ``services.instruments``).
    """

    name: str | None = None
    tool_type: str | None = None
    max_score: float | None = None
    free_observation: bool | None = None
    items: list[AssessmentItemInput] | None = None


class AssessmentToolRead(ORMBase):
    id: int
    name: str
    tool_type: str
    max_score: float
    free_observation: bool
    created_by: str | None = None
    origin_event_id: int | None = None
    archived: bool = False
    # Cantidad de referencias (estaciones + banco de estaciones); la UI decide
    # con esto si ofrece editar/purgar.
    reference_count: int = 0
    items: list[AssessmentItemRead]


class StationTemplateCreate(BaseModel):
    name: str
    category: str
    description: str
    default_configuration: dict[str, Any] = {}


class StationTemplateRead(StationTemplateCreate, ORMBase):
    id: int
    created_by: str | None = None
    origin_event_id: int | None = None
    archived: bool = False
    # Referencias (estaciones + banco de estaciones); la UI decide con esto si
    # ofrece purgar.
    reference_count: int = 0


class StationTemplatePatch(BaseModel):
    """PATCH parcial de una plantilla (OPT-7b). Todos los campos opcionales;
    UPDATE libre (sin gate de estado)."""

    name: str | None = None
    category: str | None = None
    description: str | None = None
    default_configuration: dict[str, Any] | None = None


class SimulatedPatientCreate(BaseModel):
    character_name: str
    summary_profile: str
    base_story: str
    key_answers: str
    emotional_tone: str
    special_instructions: str


class SimulatedPatientRead(SimulatedPatientCreate, ORMBase):
    id: int
    created_by: str | None = None
    origin_event_id: int | None = None
    archived: bool = False
    reference_count: int = 0


class SimulatedPatientPatch(BaseModel):
    """PATCH parcial de una ficha de paciente simulado (OPT-7b)."""

    character_name: str | None = None
    summary_profile: str | None = None
    base_story: str | None = None
    key_answers: str | None = None
    emotional_tone: str | None = None
    special_instructions: str | None = None


class StationCreate(BaseModel):
    ecoe_event_id: int
    template_id: int | None = None
    assessment_tool_id: int | None = None
    simulated_patient_id: int | None = None
    station_number: int
    name: str
    station_type: str
    circuit_name: str
    expected_outcomes: str
    student_activity: str
    student_station_instruction: str = ""
    pre_entry_instruction: str
    evaluator_instruction: str
    requires_evaluator: bool = True
    requires_student_form: bool = False
    requires_deferred_grading: bool = False
    uses_multimedia: bool = False
    uses_simulated_patient: bool = False
    uses_physical_resources: bool = False
    max_score: float = 0
    materials: str = ""
    clinical_equipment: str = ""
    simulator: str = ""
    ambience: str = ""
    multimedia_notes: str = ""
    student_form_definition: dict[str, Any] = {}
    contingency_ready: bool = True
    status: str = "en_diseno"


class StationRead(StationCreate, ORMBase):
    id: int
    # Server-computed from the parent ECOEEvent's timing, not client input
    # (see create_station/update_station) — absent from StationCreate.
    station_time_minutes: float
    transition_time_minutes: float


class StationBankBase(BaseModel):
    template_id: int | None = None
    assessment_tool_id: int | None = None
    simulated_patient_id: int | None = None
    name: str
    station_type: str
    circuit_name: str = "Circuito A"
    expected_outcomes: str
    student_activity: str
    student_station_instruction: str = ""
    pre_entry_instruction: str
    evaluator_instruction: str
    requires_evaluator: bool = True
    requires_student_form: bool = False
    requires_deferred_grading: bool = False
    uses_multimedia: bool = False
    uses_simulated_patient: bool = False
    uses_physical_resources: bool = False
    max_score: float = 0
    materials: str = ""
    clinical_equipment: str = ""
    simulator: str = ""
    ambience: str = ""
    multimedia_notes: str = ""
    student_form_definition: dict[str, Any] = {}
    contingency_ready: bool = True
    status: str = "en_diseno"


class StationBankCreate(StationBankBase):
    pass


class StationBankRead(StationBankBase, ORMBase):
    id: int


class StationBankStatusUpdate(BaseModel):
    status: str


class PilotRunCreate(BaseModel):
    ecoe_event_id: int
    name: str
    scope: str
    station_ids: list[int] = []
    notes: str = ""


class PilotRunNotesUpdate(BaseModel):
    notes: str


class TimerAction(BaseModel):
    ecoe_event_id: int
    action: str


class EvaluatorSubmission(BaseModel):
    checkin_id: int | None = None
    ecoe_event_id: int
    live_session_id: int | None = None
    station_id: int
    student_id: int
    evaluator_name: str
    mode: str = "ejecucion"
    score_obtained: float
    max_score: float
    observation: str = ""
    answers: dict[str, Any] = {}
    by_contingency: bool = False


class EvaluatorDraftUpsert(BaseModel):
    """Partial, server-side autosave of an evaluator record (OPT-20 F3, D3)."""

    checkin_id: int | None = None
    ecoe_event_id: int
    station_id: int
    student_id: int
    evaluator_name: str
    score_obtained: float = 0
    observation: str = ""
    answers: dict[str, Any] = {}


class StudentResponseCreate(BaseModel):
    checkin_id: int | None = None
    ecoe_event_id: int
    live_session_id: int | None = None
    station_id: int
    student_id: int
    mode: str = "ejecucion"
    answers: dict[str, Any]
    locked: bool = True
    by_contingency: bool = False


class StationCheckInCreate(BaseModel):
    ecoe_event_id: int
    station_id: int
    ecoe_number: str
    # El evaluador confirmó "hacer el check-in igual" pese al aviso de que el
    # estudiante ya tiene una evaluación registrada en esta estación.
    force: bool = False


class StudentAccessRequest(BaseModel):
    ecoe_event_id: int
    ecoe_number: str


class KioskSubmit(BaseModel):
    checkin_id: int
    answers: dict[str, Any]


class KioskDraftUpsert(BaseModel):
    checkin_id: int
    answers: dict[str, Any] = {}


class StudentDraftUpsert(BaseModel):
    ecoe_event_id: int
    station_id: int
    student_id: int
    checkin_id: int | None = None
    answers: dict[str, Any] = {}


class ManualGradeSubmit(BaseModel):
    scores: dict[str, float]


# ── Incidents ─────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    ecoe_event_id: int
    station_id: int | None = None
    title: str
    detail: str = ""
    severity: str = "media"


class IncidentResolve(BaseModel):
    resolved: bool = True


# ── User management ───────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role_code: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    role_code: str | None = None
    password: str = ""
    is_active: bool | None = None


class UserRead(ORMBase):
    id: int
    email: str
    full_name: str
    role_code: str = ""
    is_active: bool
    account_status: str

    @model_validator(mode="before")
    @classmethod
    def extract_role_code(cls, data: Any) -> Any:
        if hasattr(data, "role") and data.role:
            return {
                "id": data.id,
                "email": data.email,
                "full_name": data.full_name,
                "role_code": data.role.code,
                "is_active": data.is_active,
                "account_status": data.account_status,
            }
        return data


# ── Pilotage ──────────────────────────────────────────────────────────

class PilotRunRead(ORMBase):
    id: int
    ecoe_event_id: int
    name: str
    scope: str
    notes: str
    archived: bool
    created_at: datetime
    updated_at: datetime


# ── Incidents (read) ─────────────────────────────────────────────────

class IncidentRead(ORMBase):
    id: int
    ecoe_event_id: int
    station_id: int | None
    title: str
    detail: str
    severity: str
    resolved: bool
    resolved_at: datetime | None
    created_at: datetime


# ── Media ─────────────────────────────────────────────────────────────

class MediaAssetRead(ORMBase):
    id: int
    filename: str
    original_name: str
    content_type: str
    target_viewer: str
    station_id: int | None
    created_at: datetime
    # file_path (server disk path) intentionally excluded from responses.
