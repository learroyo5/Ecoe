from datetime import date, datetime

from sqlalchemy import (
    Index,
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ECOEStatus, InstrumentType, RoleCode, SessionMode, StationStatus
from app.utils.clock import utcnow_naive


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, onupdate=utcnow_naive
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
    account_status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    # Bumped on deactivation/password change: invalidates every JWT issued
    # with the previous value.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    role: Mapped["Role"] = relationship()


class UserInvitation(Base, TimestampMixin):
    __tablename__ = "user_invitations"
    __table_args__ = (
        Index("ix_user_invitations_user_status", "user_id", "accepted_at"),
        Index("ix_user_invitations_event", "ecoe_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by_email: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    __table_args__ = (
        Index("ix_auth_rate_limits_window", "window_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bucket_key: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, onupdate=utcnow_naive
    )


class ECOEPermission(Base):
    __tablename__ = "ecoe_permissions"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "user_id", "role_code", name="uq_ecoe_permission_event_user_role"),
        Index("ix_ecoe_permissions_event_user", "ecoe_event_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False)


class ECOEEvent(Base, TimestampMixin):
    __tablename__ = "ecoe_events"
    __table_args__ = (
        Index("ix_ecoe_events_status_date", "status", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    responsible_teacher: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    circuit_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    total_stations: Mapped[int] = mapped_column(Integer, default=0)
    station_time_minutes: Mapped[float] = mapped_column(Float, default=8)
    transition_time_minutes: Mapped[float] = mapped_column(Float, default=2)
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
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "name", name="uq_circuit_event_name"),
        Index("ix_circuits_event", "ecoe_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_mirror: Mapped[bool] = mapped_column(Boolean, default=False)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="circuits")


class StudentGroup(Base):
    __tablename__ = "student_groups"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "name", name="uq_student_group_event_name"),
        Index("ix_student_groups_event", "ecoe_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    circuit_id: Mapped[int | None] = mapped_column(ForeignKey("circuits.id"))

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="student_groups")


class Student(Base, TimestampMixin):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "rut", name="uq_student_event_rut"),
        UniqueConstraint("ecoe_event_id", "ecoe_number", name="uq_student_event_ecoe_number"),
        Index("ix_students_event_email", "ecoe_event_id", "email"),
        Index("ix_students_event_active", "ecoe_event_id", "is_active"),
    )

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
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "email", name="uq_staff_event_email"),
        Index("ix_staff_event_role", "ecoe_event_id", "role_code"),
    )

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
    __table_args__ = (
        UniqueConstraint("tool_id", "order_index", name="uq_assessment_item_tool_order"),
        Index("ix_assessment_items_tool", "tool_id"),
    )

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
    __table_args__ = (
        Index("ix_media_assets_station_viewer", "station_id", "target_viewer"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    target_viewer: Mapped[str] = mapped_column(String(64), nullable=False)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"))


class Station(Base, TimestampMixin):
    __tablename__ = "stations"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "station_number", name="uq_station_event_number"),
        Index("ix_stations_event_status", "ecoe_event_id", "status"),
        Index("ix_stations_event_circuit", "ecoe_event_id", "circuit_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("station_templates.id"))
    assessment_tool_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_tools.id"))
    simulated_patient_id: Mapped[int | None] = mapped_column(ForeignKey("simulated_patients.id"))
    station_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    station_type: Mapped[str] = mapped_column(String(64), nullable=False)
    circuit_name: Mapped[str] = mapped_column(String(64), nullable=False)
    station_time_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    transition_time_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    expected_outcomes: Mapped[str] = mapped_column(Text, nullable=False)
    student_activity: Mapped[str] = mapped_column(Text, nullable=False)
    student_station_instruction: Mapped[str] = mapped_column(Text, default="")
    pre_entry_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    evaluator_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    requires_evaluator: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_student_form: Mapped[bool] = mapped_column(Boolean, default=False)
    # Corrección diferida: un `corrector` puntúa las respuestas del formulario
    # después de la rotación, sin estar presente en la estación (ver
    # docs/architecture/EVALUACION_DIFERIDA_FASE1.md).
    requires_deferred_grading: Mapped[bool] = mapped_column(Boolean, default=False)
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


class StationBank(Base, TimestampMixin):
    __tablename__ = "station_bank"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("station_templates.id"))
    assessment_tool_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_tools.id"))
    simulated_patient_id: Mapped[int | None] = mapped_column(ForeignKey("simulated_patients.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    station_type: Mapped[str] = mapped_column(String(64), nullable=False)
    circuit_name: Mapped[str] = mapped_column(String(64), default="Circuito A")
    expected_outcomes: Mapped[str] = mapped_column(Text, nullable=False)
    student_activity: Mapped[str] = mapped_column(Text, nullable=False)
    student_station_instruction: Mapped[str] = mapped_column(Text, default="")
    pre_entry_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    evaluator_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    requires_evaluator: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_student_form: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_deferred_grading: Mapped[bool] = mapped_column(Boolean, default=False)
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
    status: Mapped[str] = mapped_column(String(64), default="en_diseno")


class StationResource(Base):
    __tablename__ = "station_resources"
    __table_args__ = (
        Index("ix_station_resources_station", "station_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class PilotRun(Base, TimestampMixin):
    __tablename__ = "pilot_runs"
    __table_args__ = (
        Index("ix_pilot_runs_event_archived", "ecoe_event_id", "archived"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    # Hallazgos operativos del pilotaje (tiempos reales, problemas, ajustes):
    # lo que convierte el registro en insumo de mejora antes de publicar.
    notes: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="pilot_runs")
    records: Mapped[list["PilotRecord"]] = relationship(
        back_populates="pilot_run", cascade="all, delete-orphan"
    )


class PilotRecord(Base, TimestampMixin):
    __tablename__ = "pilot_records"
    __table_args__ = (
        UniqueConstraint("pilot_run_id", "station_id", name="uq_pilot_record_run_station"),
        Index("ix_pilot_records_station", "station_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pilot_run_id: Mapped[int] = mapped_column(ForeignKey("pilot_runs.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    is_test: Mapped[bool] = mapped_column(Boolean, default=True)

    pilot_run: Mapped["PilotRun"] = relationship(back_populates="records")


class LiveSession(Base, TimestampMixin):
    __tablename__ = "live_sessions"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", name="uq_live_session_event"),
        Index("ix_live_sessions_event_status", "ecoe_event_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    mode: Mapped[SessionMode] = mapped_column(String(32), default=SessionMode.ejecucion)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    station_time_seconds: Mapped[int] = mapped_column(Integer, default=480)
    transition_time_seconds: Mapped[int] = mapped_column(Integer, default=120)
    current_station_index: Mapped[int] = mapped_column(Integer, default=1)
    # remaining_seconds is the value frozen at the last state change; while
    # the timer runs, the authoritative remaining time is computed from
    # phase_started_at (see live_session_state in operational routes).
    remaining_seconds: Mapped[int] = mapped_column(Integer, default=480)
    phase_started_at: Mapped[datetime | None] = mapped_column(DateTime)

    ecoe_event: Mapped["ECOEEvent"] = relationship(back_populates="live_sessions")


class StationKioskSession(Base, TimestampMixin):
    """Device-level session for the shared tablet installed at a station.

    The kiosk never authenticates a person: it holds a station-scoped token
    (hashed here, shown once at issue time) and the student identity always
    derives from the station's active check-in. Issuing a new token for the
    station revokes the previous ones.
    """

    __tablename__ = "station_kiosk_sessions"
    __table_args__ = (
        Index("ix_station_kiosk_sessions_station", "station_id", "revoked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    issued_by_email: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StationCheckIn(Base, TimestampMixin):
    __tablename__ = "station_checkins"
    __table_args__ = (
        Index("ix_station_checkins_event_station_status", "ecoe_event_id", "station_id", "status"),
        Index("ix_station_checkins_event_student_status", "ecoe_event_id", "student_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    evaluator_email: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="confirmado")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class EvaluatorRecord(Base, TimestampMixin):
    __tablename__ = "evaluator_records"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "station_id", "student_id", "mode", name="uq_evaluator_record_event_station_student_mode"),
        Index("ix_evaluator_records_event_student", "ecoe_event_id", "student_id"),
        Index("ix_evaluator_records_event_station", "ecoe_event_id", "station_id"),
    )

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
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "station_id", "student_id", "mode", name="uq_student_response_event_station_student_mode"),
        Index("ix_student_responses_event_student", "ecoe_event_id", "student_id"),
        Index("ix_student_responses_event_station", "ecoe_event_id", "station_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    live_session_id: Mapped[int | None] = mapped_column(ForeignKey("live_sessions.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    mode: Mapped[SessionMode] = mapped_column(String(32), default=SessionMode.ejecucion)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    locked: Mapped[bool] = mapped_column(Boolean, default=True)
    by_contingency: Mapped[bool] = mapped_column(Boolean, default=False)
    # Puntuacion del formulario: score_obtained queda NULL mientras haya
    # preguntas de correccion manual pendientes; solo las respuestas con
    # puntaje resuelto entran al consolidado (ver services/grading.py).
    score_obtained: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    grading: Mapped[dict] = mapped_column(JSON, default=dict)
    graded_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StationResult(Base, TimestampMixin):
    __tablename__ = "station_results"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "station_id", "student_id", name="uq_station_result_event_station_student"),
        Index("ix_station_results_event_student", "ecoe_event_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    obtained_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    percent_score: Mapped[float] = mapped_column(Float, nullable=False)


class ECOEResult(Base, TimestampMixin):
    __tablename__ = "ecoe_results"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "student_id", name="uq_ecoe_result_event_student"),
        Index("ix_ecoe_results_event", "ecoe_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    equivalent_grade: Mapped[float] = mapped_column(Float, nullable=False)


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_event_resolved", "ecoe_event_id", "resolved"),
        Index("ix_incidents_event_station", "ecoe_event_id", "station_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="media")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class ContingencyExport(Base, TimestampMixin):
    __tablename__ = "contingency_exports"
    __table_args__ = (
        Index("ix_contingency_exports_event_type", "ecoe_event_id", "export_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecoe_event_id: Mapped[int] = mapped_column(ForeignKey("ecoe_events.id"), nullable=False)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"))
    export_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_target", "target_type", "target_id"),
        Index("ix_audit_logs_user_action", "user_email", "action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
