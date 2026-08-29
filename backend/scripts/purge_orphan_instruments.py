"""Purga opt-in de instrumentos huérfanos del banco (`AssessmentTool`).

OPT-7 · decisión del usuario #6. **No** se ejecuta en `alembic upgrade`: es un
comando manual que el equipo corre tras revisar el dry-run.

Un candidato a purga cumple TODO:

1. ``archived == False`` (los archivados se dejan como están; usa
   ``--include-archived`` para incluirlos).
2. 0 referencias en ``stations`` **y** ``station_bank``.
3. ``created_at`` anterior a ``--min-age-days`` (default 90).
4. Ninguno de los ``AssessmentItem.id`` del tool aparece como clave en
   ``EvaluatorRecord.answers`` de ningún registro (barrido defensivo: cubre el
   caso de un ``EvaluatorRecord`` histórico de una estación que **antes**
   apuntaba a ese tool). Es O(registros) pero es un one-shot.

Uso (desde ``backend/``):

    python -m scripts.purge_orphan_instruments                # dry-run (default)
    python -m scripts.purge_orphan_instruments --min-age-days 120
    python -m scripts.purge_orphan_instruments --apply        # ejecuta el borrado
    python -m scripts.purge_orphan_instruments --apply --include-archived

Cada tool purgado emite un ``AuditLog`` (``action="purge_orphan_instrument"``).
El borrado arrastra sus ``AssessmentItem`` por el ``ondelete=CASCADE`` /
``cascade="all, delete-orphan"``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    AuditLog,
    EvaluatorRecord,
    Station,
    StationBank,
)
from app.utils.clock import utcnow_naive


def _answer_item_ids(db) -> set[str]:
    """Todas las claves usadas en algún ``EvaluatorRecord.answers`` (como str)."""
    keys: set[str] = set()
    for (answers,) in db.execute(select(EvaluatorRecord.answers)):
        if isinstance(answers, dict):
            keys.update(str(k) for k in answers.keys())
    return keys


def find_candidates(db, *, min_age_days: int, include_archived: bool) -> list[dict]:
    cutoff = utcnow_naive() - timedelta(days=min_age_days)

    referenced_station = set(
        db.scalars(select(Station.assessment_tool_id).where(
            Station.assessment_tool_id.is_not(None)))
    )
    referenced_bank = set(
        db.scalars(select(StationBank.assessment_tool_id).where(
            StationBank.assessment_tool_id.is_not(None)))
    )
    referenced = referenced_station | referenced_bank

    answer_keys = _answer_item_ids(db)

    query = select(AssessmentTool)
    if not include_archived:
        query = query.where(AssessmentTool.archived.is_(False))

    candidates: list[dict] = []
    for tool in db.scalars(query.order_by(AssessmentTool.id)):
        if tool.id in referenced:
            continue
        if tool.created_at and tool.created_at > cutoff:
            continue
        item_ids = set(
            db.scalars(select(AssessmentItem.id).where(AssessmentItem.tool_id == tool.id))
        )
        if {str(i) for i in item_ids} & answer_keys:
            continue
        candidates.append({
            "id": tool.id,
            "name": tool.name,
            "created_at": tool.created_at,
            "archived": tool.archived,
            "items": len(item_ids),
        })
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true",
                        help="Ejecuta el borrado. Sin esto, solo lista (dry-run).")
    parser.add_argument("--min-age-days", type=int, default=90,
                        help="Antigüedad mínima del tool para ser candidato (default 90).")
    parser.add_argument("--include-archived", action="store_true",
                        help="Incluye también los tools ya archivados.")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        candidates = find_candidates(
            db,
            min_age_days=args.min_age_days,
            include_archived=args.include_archived,
        )

        if not candidates:
            print("Sin instrumentos huérfanos que cumplan el criterio.")
            return 0

        mode = "APLICANDO" if args.apply else "dry-run (no se borra nada)"
        print(f"{len(candidates)} instrumento(s) huérfano(s) — {mode}:")
        for c in candidates:
            created = c["created_at"].date().isoformat() if c["created_at"] else "?"
            flag = " [archivado]" if c["archived"] else ""
            print(f"  #{c['id']:<5} {c['name'][:60]:<60} creado {created}  "
                  f"{c['items']} ítem(s){flag}")

        if not args.apply:
            print("\nRevisa la lista y vuelve a correr con --apply para borrar.")
            return 0

        for c in candidates:
            tool = db.get(AssessmentTool, c["id"])
            db.add(AuditLog(
                user_email="system:purge_orphan_instruments",
                action="purge_orphan_instrument",
                target_type="AssessmentTool",
                target_id=str(tool.id),
                payload={"name": tool.name, "items": c["items"]},
            ))
            db.delete(tool)
        db.commit()
        print(f"\nBorrados {len(candidates)} instrumento(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
