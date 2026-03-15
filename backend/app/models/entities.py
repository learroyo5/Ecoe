from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ECOEStatus, InstrumentType, RoleCode, SessionMode, StationStatus


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[RoleCode] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    role: Mapped["Role"] = relationship()


class ECOEPermission(Base):
    __tablename__ = "ecoe_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False)


class ECOEEvent(Base, TimestampMixin):
    __tablename__ = "ecoe_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    responsible_teacher: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    circuit_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    total_stations: Mapped[int] = mapped_column(Integer, default=0)
    station_time_minutes: Mapped[int] = mapped_column(Integer, default=8)
    transition_time_minutes: Mapped[int] = mapped_column(Integer, default=2)
    total_students: Mapped[int] = mapped_column(Integer, default=0)
    total_groups: Mapped[int] = mapped_column(Integer, default=1)
    passing_reference_percent: Mapped[float] = mapped_column(Float, default=60.0)
    status: Mapped[ECOEStatus] = mapped_column(String(64), default=ECOEStatus.borrador)
    timer_sound_asset_id: Mapped[int | None] = mapped_column(ForeignKey("media_assets.id"))

    circuits: Mapped[list["Circuit"]] = relationship(back_populates="ecoe_event")
    student_groups: Mapped[list["StudentGroup"]] = relationship(back_populates="ecoe_event")
    students: Mapped[list["Student"]] = relationship(back_populates="ecoe_event")
    staff_assignments: Mapped[list["StaffAssignment"]] = relationship(back_populates="ecoe_event")
    stations: Mapped[list["Station"]] = relationship(back_populates="ecoe_event")
    pilot_runs: Mapped[list["PilotRun"]] = relationship(back_populates="ecoe_event")
    live_sessions: Mapped[list["LiveSession"]] = relationship(back_populates="ecoe_event")


class Circuit(Base):
    __tablename__ = "circuits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_mirror: Mapped[bool] = mapped_column(Boolean, default=False)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="circuits")


class StudentGroup(Base):
    __tablename__ = "student_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    circuit_id: Mapped[int | None] = mapped_column(ForeignKey("circuits.id"))

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="student_groups")


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    rut: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    ecoe_number: Mapped[str] = mapped_column(String(32), nullable=False)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    circuit_name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="students")


class StaffAssignment(Base, TimestampMixin):
    __tablename__ = "staff_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    station_ids: Mapped[list[int]] = mapped_column(JSON, default=list)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="staff_assignments")


class StationTemplate(Base, TimestampMixin):
    __tablename__ = "station_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_configuration: Mapped[dict] = mapped_column(JSON, default=dict)


class AssessmentTool(Base, TimestampMixin):
    __tablename__ = "assessment_tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_type: Mapped[InstrumentType] = mapped_column(String(64), nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    free_observation: Mapped[bool] = mapped_column(Boolean, default=True)
    items: Mapped[list["AssessmentItem"]] = relationship(
        back_populates="tool", cascade="all, delete-orphan"
    )


class AssessmentItem(Base):
    __tablename__ = "assessment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("assessment_tools.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    score_per_item: Mapped[float] = mapped_column(Float, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    tool: Mapped["AssessmentTool"] = relationship(back_populates="items")


class SimulatedPatient(Base, TimestampMixin):
    __tablename__ = "simulated_patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary_profile: Mapped[str] = mapped_column(Text, nullable=False)
    base_story: Mapped[str] = mapped_column(Text, nullable=False)
    key_answers: Mapped[str] = mapped_column(Text, nullable=False)
    emotional_tone: Mapped[str] = mapped_column(String(255), nullable=False)
    special_instructions: Mapped[str] = mapped_column(Text, nullable=False)


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    target_viewer: Mapped[str] = mapped_column(String(64), nullable=False)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"))


class Station(Base, TimestampMixin):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("station_templates.id"))
    assessment_tool_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_tools.id"))
    simulated_patient_id: Mapped[int | None] = mapped_column(ForeignKey("simulated_patients.id"))
    station_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    station_type: Mapped[str] = mapped_column(String(64), nullable=False)
    circuit_name: Mapped[str] = mapped_column(String(64), nullable=False)
    station_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    transition_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_outcomes: Mapped[str] = mapped_column(Text, nullable=False)
    student_activity: Mapped[str] = mapped_column(Text, nullable=False)
    student_station_instruction: Mapped[str] = mapped_column(Text, default="")
    pre_entry_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    evaluator_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    requires_evaluator: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_student_form: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_multimedia: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_simulated_patient: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_physical_resources: Mapped[bool] = mapped_column(Boolean, default=False)
    max_score: Mapped[float] = mapped_column(Float, default=0)
    materials: Mapped[str] = mapped_column(Text, default="")
    clinical_equipment: Mapped[str] = mapped_column(Text, default="")
    simulator: Mapped[str] = mapped_column(Text, default="")
    ambience: Mapped[str] = mapped_column(Text, default="")
    multimedia_notes: Mapped[str] = mapped_column(Text, default="")
    student_form_definition: Mapped[dict] = mapped_column(JSON, default=dict)
    contingency_ready: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[StationStatus] = mapped_column(String(64), default=StationStatus.en_diseno)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="stations")


class StationResource(Base):
    __tablename__ = "station_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class PilotRun(Base, TimestampMixin):
    __tablename__ = "pilot_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="pilot_runs")
    records: Mapped[list["PilotRecord"]] = relationship(
        back_populates="pilot_run", cascade="all, delete-orphan"
    )


class PilotRecord(Base, TimestampMixin):
    __tablename__ = "pilot_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pilot_run_id: Mapped[int] = mapped_column(ForeignKey("pilot_runs.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    is_test: Mapped[bool] = mapped_column(Boolean, default=True)

    pilot_run: Mapped["PilotRun"] = relationship(back_populates="records")


class LiveSession(Base, TimestampMixin):
    __tablename__ = "live_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    mode: Mapped[SessionMode] = mapped_column(String(32), default=SessionMode.ejecucion)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    station_time_seconds: Mapped[int] = mapped_column(Integer, default=480)
    transition_time_seconds: Mapped[int] = mapped_column(Integer, default=120)
    current_station_index: Mapped[int] = mapped_column(Integer, default=1)
    remaining_seconds: Mapped[int] = mapped_column(Integer, default=480)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="live_sessions")


class StationCheckIn(Base, TimestampMixin):
    __tablename__ = "station_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    evaluator_email: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="confirmado")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvaluatorRecord(Base, TimestampMixin):
    __tablename__ = "evaluator_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    live_session_id: Mapped[int | None] = mapped_column(ForeignKey("live_sessions.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    evaluator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[SessionMode] = mapped_column(String(32), default=SessionMode.ejecucion)
    score_obtained: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    observation: Mapped[str] = mapped_column(Text, default="")
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    by_contingency: Mapped[bool] = mapped_column(Boolean, default=False)


class StudentResponse(Base, TimestampMixin):
    __tablename__ = "student_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    live_session_id: Mapped[int | None] = mapped_column(ForeignKey("live_sessions.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    mode: Mapped[SessionMode] = mapped_column(String(32), default=SessionMode.ejecucion)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    locked: Mapped[bool] = mapped_column(Boolean, default=True)
    by_contingency: Mapped[bool] = mapped_column(Boolean, default=False)


class StationResult(Base, TimestampMixin):
    __tablename__ = "station_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    obtained_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    percent_score: Mapped[float] = mapped_column(Float, nullable=False)


class ECOEResult(Base, TimestampMixin):
    __tablename__ = "ecoe_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    equivalent_grade: Mapped[float] = mapped_column(Float, nullable=False)


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="media")


class ContingencyExport(Base, TimestampMixin):
    __tablename__ = "contingency_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"))
    export_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
