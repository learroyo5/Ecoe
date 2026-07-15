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
    total_stations: int = Field(ge=1)
    station_time_minutes: float = Field(ge=0.1)
    transition_time_minutes: float = Field(ge=0)
    total_students: int = Field(ge=0)
    total_groups: int = Field(ge=1)
    passing_reference_percent: float = Field(default=60, ge=0, le=100)


class ECOEEventCreate(ECOEEventBase):
    pass


class ECOEEventUpdate(ECOEEventBase):
    status: str


class ECOEEventRead(ECOEEventBase, ORMBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime


class ECOETimingUpdate(BaseModel):
    station_time_minutes: float = Field(ge=0.1)
    transition_time_minutes: float = Field(ge=0)
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
    name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    role_code: str
    station_ids: list[int] = []


class InvitationActivation(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class AssessmentItemInput(BaseModel):
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


class AssessmentToolRead(ORMBase):
    id: int
    name: str
    tool_type: str
    max_score: float
    free_observation: bool
    items: list[AssessmentItemRead]


class StationTemplateCreate(BaseModel):
    name: str
    category: str
    description: str
    default_configuration: dict[str, Any] = {}


class StationTemplateRead(StationTemplateCreate, ORMBase):
    id: int


class SimulatedPatientCreate(BaseModel):
    character_name: str
    summary_profile: str
    base_story: str
    key_answers: str
    emotional_tone: str
    special_instructions: str


class SimulatedPatientRead(SimulatedPatientCreate, ORMBase):
    id: int


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


class StudentAccessRequest(BaseModel):
    ecoe_event_id: int
    ecoe_number: str


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
