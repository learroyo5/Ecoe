"""Standalone UTC clock helper with no app-internal imports.

Kept separate from utils/helpers.py so app.models.entities can use it for
column defaults without a circular import (helpers.py imports from
models.entities).
"""

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Naive UTC now, comparable with DB timestamps (stored naive UTC).

    Replaces the deprecated datetime.utcnow() with the same value: the
    database columns are naive DateTime, so timezone-aware values would
    break equality/ordering comparisons against them.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
