"""Purga opt-in de plantillas y pacientes simulados huérfanos del banco.

OPT-7b · análogo a ``purge_orphan_instruments`` (OPT-7). **No** se ejecuta en
``alembic upgrade``: es un comando manual que el equipo corre tras revisar el
dry-run.

A diferencia de los instrumentos, ``StationTemplate`` y ``SimulatedPatient`` no
se referencian por ``id`` en datos históricos (``EvaluatorRecord.answers``), así
que no hace falta el barrido defensivo de ``answers``.

Un candidato a purga cumple TODO:

1. ``archived == False`` (usa ``--include-archived`` para incluirlos).
2. 0 referencias en ``stations`` **y** ``station_bank``.
3. ``created_at`` anterior a ``--min-age-days`` (default 90).

Uso (desde ``backend/``):

    python -m scripts.purge_orphan_content --kind templates            # dry-run
    python -m scripts.purge_orphan_content --kind patients --apply
    python -m scripts.purge_orphan_content --kind templates --apply --include-archived

Cada registro purgado emite un ``AuditLog`` (``action="purge_orphan_content"``).
Las FK que lo referencian tienen ``ondelete=SET NULL`` (migración o5p6q7r8s9t0);
como el criterio exige 0 referencias, el borrado no toca ninguna estación.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.entities import (
    AuditLog,
    SimulatedPatient,
    Station,
    StationBank,
    StationTemplate,
)
from app.utils.clock import utcnow_naive

_KINDS = {
    "templates": {
        "model": StationTemplate,
        "label": lambda r: r.name,
        "station_col": Station.template_id,
        "bank_col": StationBank.template_id,
    },
    "patients": {
        "model": SimulatedPatient,
        "label": lambda r: r.character_name,
        "station_col": Station.simulated_patient_id,
        "bank_col": StationBank.simulated_patient_id,
    },
}


def find_candidates(db, *, kind: str, min_age_days: int, include_archived: bool) -> list[dict]:
    spec = _KINDS[kind]
    model = spec["model"]
    cutoff = utcnow_naive() - timedelta(days=min_age_days)

    referenced = set(
        db.scalars(select(spec["station_col"]).where(spec["station_col"].is_not(None)))
    ) | set(
        db.scalars(select(spec["bank_col"]).where(spec["bank_col"].is_not(None)))
    )

    query = select(model)
    if not include_archived:
        query = query.where(model.archived.is_(False))

    candidates: list[dict] = []
    for record in db.scalars(query.order_by(model.id)):
        if record.id in referenced:
            continue
        if record.created_at and record.created_at > cutoff:
            continue
        candidates.append({
            "id": record.id,
            "name": spec["label"](record),
            "created_at": record.created_at,
            "archived": record.archived,
        })
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", choices=sorted(_KINDS), required=True,
                        help="Qué banco purgar: templates | patients.")
    parser.add_argument("--apply", action="store_true",
                        help="Ejecuta el borrado. Sin esto, solo lista (dry-run).")
    parser.add_argument("--min-age-days", type=int, default=90,
                        help="Antigüedad mínima del registro para ser candidato (default 90).")
    parser.add_argument("--include-archived", action="store_true",
                        help="Incluye también los registros ya archivados.")
    args = parser.parse_args(argv)

    model = _KINDS[args.kind]["model"]

    with SessionLocal() as db:
        candidates = find_candidates(
            db, kind=args.kind, min_age_days=args.min_age_days,
            include_archived=args.include_archived,
        )

        if not candidates:
            print(f"Sin registros huérfanos ({args.kind}) que cumplan el criterio.")
            return 0

        mode = "APLICANDO" if args.apply else "dry-run (no se borra nada)"
        print(f"{len(candidates)} registro(s) huérfano(s) [{args.kind}] — {mode}:")
        for c in candidates:
            created = c["created_at"].date().isoformat() if c["created_at"] else "?"
            flag = " [archivado]" if c["archived"] else ""
            print(f"  #{c['id']:<5} {c['name'][:60]:<60} creado {created}{flag}")

        if not args.apply:
            print("\nRevisa la lista y vuelve a correr con --apply para borrar.")
            return 0

        for c in candidates:
            record = db.get(model, c["id"])
            db.add(AuditLog(
                user_email="system:purge_orphan_content",
                action="purge_orphan_content",
                target_type=model.__name__,
                target_id=str(record.id),
                payload={"kind": args.kind, "name": c["name"]},
            ))
            db.delete(record)
        db.commit()
        print(f"\nBorrados {len(candidates)} registro(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
