"""Pagination helpers for list endpoints."""

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def pagination_params(
    page: int = Query(default=1, ge=1, description="Número de página (base 1)"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items por página"),
) -> dict:
    return {"page": page, "page_size": page_size, "offset": (page - 1) * page_size}


def paginate_query(db: Session, stmt: Select, *, page: int, page_size: int) -> dict:
    """Execute a paginated query and return items + metadata."""
    offset = (page - 1) * page_size

    # Count total items
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Fetch page
    items = list(db.scalars(stmt.offset(offset).limit(page_size)).all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size) if total > 0 else 1,
    }
