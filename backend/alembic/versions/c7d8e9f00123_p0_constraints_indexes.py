"""p0_constraints_indexes

Revision ID: c7d8e9f00123
Revises: 95dccafb1304
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "c7d8e9f00123"
down_revision: Union[str, Sequence[str], None] = "95dccafb1304"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UNIQUE_CONSTRAINTS = [
    ("ecoe_permissions", "uq_ecoe_permission_event_user_role", ["ecoe_event_id", "user_id", "role_code"]),
    ("circuits", "uq_circuit_event_name", ["ecoe_event_id", "name"]),
    ("student_groups", "uq_student_group_event_name", ["ecoe_event_id", "name"]),
    ("students", "uq_student_event_rut", ["ecoe_event_id", "rut"]),
    ("students", "uq_student_event_ecoe_number", ["ecoe_event_id", "ecoe_number"]),
    ("staff_assignments", "uq_staff_event_email", ["ecoe_event_id", "email"]),
    ("assessment_items", "uq_assessment_item_tool_order", ["tool_id", "order_index"]),
    ("stations", "uq_station_event_number", ["ecoe_event_id", "station_number"]),
    ("pilot_records", "uq_pilot_record_run_station", ["pilot_run_id", "station_id"]),
    ("live_sessions", "uq_live_session_event", ["ecoe_event_id"]),
    ("evaluator_records", "uq_evaluator_record_event_station_student_mode", ["ecoe_event_id", "station_id", "student_id", "mode"]),
    ("student_responses", "uq_student_response_event_station_student_mode", ["ecoe_event_id", "station_id", "student_id", "mode"]),
    ("station_results", "uq_station_result_event_station_student", ["ecoe_event_id", "station_id", "student_id"]),
    ("ecoe_results", "uq_ecoe_result_event_student", ["ecoe_event_id", "student_id"]),
]

INDEXES = [
    ("ecoe_events", "ix_ecoe_events_status_date", ["status", "date"]),
    ("ecoe_permissions", "ix_ecoe_permissions_event_user", ["ecoe_event_id", "user_id"]),
    ("circuits", "ix_circuits_event", ["ecoe_event_id"]),
    ("student_groups", "ix_student_groups_event", ["ecoe_event_id"]),
    ("students", "ix_students_event_email", ["ecoe_event_id", "email"]),
    ("students", "ix_students_event_active", ["ecoe_event_id", "is_active"]),
    ("staff_assignments", "ix_staff_event_role", ["ecoe_event_id", "role_code"]),
    ("assessment_items", "ix_assessment_items_tool", ["tool_id"]),
    ("media_assets", "ix_media_assets_station_viewer", ["station_id", "target_viewer"]),
    ("stations", "ix_stations_event_status", ["ecoe_event_id", "status"]),
    ("stations", "ix_stations_event_circuit", ["ecoe_event_id", "circuit_name"]),
    ("station_resources", "ix_station_resources_station", ["station_id"]),
    ("pilot_runs", "ix_pilot_runs_event_archived", ["ecoe_event_id", "archived"]),
    ("pilot_records", "ix_pilot_records_station", ["station_id"]),
    ("live_sessions", "ix_live_sessions_event_status", ["ecoe_event_id", "status"]),
    ("station_checkins", "ix_station_checkins_event_station_status", ["ecoe_event_id", "station_id", "status"]),
    ("station_checkins", "ix_station_checkins_event_student_status", ["ecoe_event_id", "student_id", "status"]),
    ("evaluator_records", "ix_evaluator_records_event_student", ["ecoe_event_id", "student_id"]),
    ("evaluator_records", "ix_evaluator_records_event_station", ["ecoe_event_id", "station_id"]),
    ("student_responses", "ix_student_responses_event_student", ["ecoe_event_id", "student_id"]),
    ("student_responses", "ix_student_responses_event_station", ["ecoe_event_id", "station_id"]),
    ("station_results", "ix_station_results_event_student", ["ecoe_event_id", "student_id"]),
    ("ecoe_results", "ix_ecoe_results_event", ["ecoe_event_id"]),
    ("incidents", "ix_incidents_event_resolved", ["ecoe_event_id", "resolved"]),
    ("incidents", "ix_incidents_event_station", ["ecoe_event_id", "station_id"]),
    ("contingency_exports", "ix_contingency_exports_event_type", ["ecoe_event_id", "export_type"]),
    ("audit_logs", "ix_audit_logs_target", ["target_type", "target_id"]),
    ("audit_logs", "ix_audit_logs_user_action", ["user_email", "action"]),
]


def _constraint_exists(inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        item.get("name") == constraint_name
        for item in inspector.get_unique_constraints(table_name)
    )


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(
        item.get("name") == index_name
        for item in inspector.get_indexes(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if bind.dialect.name != "sqlite":
        for table_name, constraint_name, columns in UNIQUE_CONSTRAINTS:
            if not _constraint_exists(inspector, table_name, constraint_name):
                op.create_unique_constraint(constraint_name, table_name, columns)

    inspector = inspect(bind)
    for table_name, index_name, columns in INDEXES:
        if not _index_exists(inspector, table_name, index_name):
            op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for table_name, index_name, _columns in reversed(INDEXES):
        if _index_exists(inspector, table_name, index_name):
            op.drop_index(index_name, table_name=table_name)

    if bind.dialect.name != "sqlite":
        inspector = inspect(bind)
        for table_name, constraint_name, _columns in reversed(UNIQUE_CONSTRAINTS):
            if _constraint_exists(inspector, table_name, constraint_name):
                op.drop_constraint(constraint_name, table_name, type_="unique")
