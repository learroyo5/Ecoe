"""ECOE services — re-exports from domain-specific modules for backward compatibility."""

from app.services.validation import compute_ecoe_validation, update_ecoe_status
from app.services.dashboard import build_dashboard
from app.services.results import (
    build_station_score_block,
    build_traceability_report,
    compute_results,
    compute_station_results,
    export_contingency_pdf,
    export_results_excel,
    persist_results,
    read_results,
    read_station_results,
    store_contingency_export,
)

__all__ = [
    "build_dashboard",
    "build_station_score_block",
    "build_traceability_report",
    "compute_ecoe_validation",
    "compute_results",
    "compute_station_results",
    "export_contingency_pdf",
    "export_results_excel",
    "persist_results",
    "read_results",
    "read_station_results",
    "store_contingency_export",
    "update_ecoe_status",
]
