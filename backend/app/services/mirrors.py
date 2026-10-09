"""Circuitos espejo.

Un ECOE en espejo corre el mismo circuito varias veces en paralelo (p. ej.
circuito A en el 4.º piso y circuito B en el 5.º): cada estación de diseño
existe una vez por circuito, con evaluador, tablet y sala propios, pero con
la MISMA pauta, formulario, puntaje e instrucciones.

Modelo: el circuito original se diseña normalmente; cada estación de un
circuito espejo es una fila ``Station`` con ``mirror_of_id`` apuntando a su
original. El diseño se copia al crear el espejo y se vuelve a copiar cada vez
que se edita la original; una estación espejo no se edita por separado.

- **Estación de diseño** de una estación = su original, o ella misma.
- Resultados y análisis se agregan por estación de diseño (1A + 1B).
- La multimedia vive en la original y la leen todos sus espejos.
"""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Station

# Campos de diseño: idénticos entre una estación y sus espejos.
SHARED_DESIGN_FIELDS = (
    "template_id",
    "assessment_tool_id",
    "name",
    "station_type",
    "expected_outcomes",
    "student_activity",
    "student_station_instruction",
    "pre_entry_instruction",
    "evaluator_instruction",
    "requires_evaluator",
    "requires_student_form",
    "requires_deferred_grading",
    "uses_multimedia",
    "uses_simulated_patient",
    "uses_physical_resources",
    "max_score",
    "materials",
    "clinical_equipment",
    "simulator",
    "ambience",
    "multimedia_notes",
    "student_form_definition",
    "contingency_ready",
    "station_time_minutes",
    "transition_time_minutes",
)
# Propios de cada estación física (no se copian ni se comparan):
# circuit_name, station_number, simulated_patient_id (otro actor), status.


def circuit_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def design_station_id(station: Station) -> int:
    """Id de la estación de diseño: la original, o la propia si no es espejo."""
    return station.mirror_of_id or station.id


def design_station_map(db: Session, ecoe_event_id: int) -> dict[int, int]:
    """``{station_id: id de su estación de diseño}`` para todo el evento."""
    return {
        station_id: mirror_of_id or station_id
        for station_id, mirror_of_id in db.execute(
            select(Station.id, Station.mirror_of_id).where(Station.ecoe_event_id == ecoe_event_id)
        ).all()
    }


def station_family_ids(db: Session, station: Station) -> set[int]:
    """La estación de diseño y todos sus espejos (incluida la propia)."""
    design_id = design_station_id(station)
    mirrors = db.scalars(select(Station.id).where(Station.mirror_of_id == design_id)).all()
    return {design_id, *mirrors}


def mirrors_of(db: Session, station: Station) -> list[Station]:
    return list(db.scalars(
        select(Station).where(Station.mirror_of_id == station.id).order_by(Station.station_number)
    ))


def copy_design(source: Station, target: Station) -> None:
    for field in SHARED_DESIGN_FIELDS:
        value = getattr(source, field)
        if isinstance(value, (dict, list)):
            import copy

            value = copy.deepcopy(value)
        setattr(target, field, value)


def propagate_design_to_mirrors(db: Session, source: Station) -> int:
    """Tras editar la original: sus espejos reciben el mismo diseño."""
    mirrors = mirrors_of(db, source)
    for mirror in mirrors:
        copy_design(source, mirror)
        mirror.status = source.status
        db.add(mirror)
    return len(mirrors)


def _circuit_names(db: Session, ecoe_event_id: int) -> dict[str, str]:
    """``{clave: nombre tal como se escribió}`` de los circuitos del evento."""
    names: dict[str, str] = {}
    for (name,) in db.execute(
        select(Station.circuit_name).where(Station.ecoe_event_id == ecoe_event_id).distinct()
    ).all():
        names.setdefault(circuit_key(name), name)
    return names


def sync_mirror_circuit(
    db: Session, ecoe_event_id: int, source_circuit: str, mirror_circuit: str
) -> dict:
    """Crea (o completa) ``mirror_circuit`` como espejo de ``source_circuit``.

    Idempotente: cada estación original del circuito fuente que todavía no
    tenga espejo en el circuito destino recibe uno; las que ya lo tienen se
    re-sincronizan. No hace commit.
    """
    source_key, mirror_key = circuit_key(source_circuit), circuit_key(mirror_circuit)
    if not mirror_key:
        raise HTTPException(status_code=400, detail="Indica el nombre del circuito espejo")
    if source_key == mirror_key:
        raise HTTPException(status_code=400, detail="El circuito espejo debe tener otro nombre")
    stations = db.scalars(
        select(Station).where(Station.ecoe_event_id == ecoe_event_id).order_by(Station.station_number)
    ).all()
    sources = [s for s in stations if circuit_key(s.circuit_name) == source_key]
    if not sources:
        raise HTTPException(status_code=404, detail="El circuito de origen no tiene estaciones")
    if any(s.mirror_of_id for s in sources):
        raise HTTPException(
            status_code=409,
            detail="El circuito de origen ya es un espejo; duplica el circuito original",
        )
    in_target = [s for s in stations if circuit_key(s.circuit_name) == mirror_key]
    source_ids = {s.id for s in sources}
    foreign = [s for s in in_target if s.mirror_of_id not in source_ids]
    if foreign:
        raise HTTPException(
            status_code=409,
            detail=(
                f"«{mirror_circuit}» ya tiene estaciones propias que no son espejo de "
                f"«{source_circuit}». Elige otro nombre o elimina esas estaciones."
            ),
        )
    existing = {s.mirror_of_id: s for s in in_target}
    next_number = (
        db.scalar(select(func.max(Station.station_number)).where(Station.ecoe_event_id == ecoe_event_id))
        or 0
    )
    created = 0
    for source in sources:
        mirror = existing.get(source.id)
        if mirror is None:
            next_number += 1
            mirror = Station(
                ecoe_event_id=ecoe_event_id,
                mirror_of_id=source.id,
                station_number=next_number,
                circuit_name=mirror_circuit.strip(),
            )
            created += 1
        copy_design(source, mirror)
        mirror.status = source.status
        db.add(mirror)
    db.flush()
    return {"created": created, "synced": len(sources), "mirror_circuit": mirror_circuit.strip()}


def mirror_structure_issues(db: Session, ecoe_event_id: int) -> list[str]:
    """Problemas que impiden usar los circuitos del evento como espejos.

    Con un solo circuito no hay nada que comprobar. Con varios, TODOS deben
    ser espejo exacto del circuito original: mismas estaciones y mismo diseño.
    """
    stations = db.scalars(
        select(Station).where(Station.ecoe_event_id == ecoe_event_id).order_by(Station.station_number)
    ).all()
    by_circuit: dict[str, list[Station]] = {}
    labels: dict[str, str] = {}
    for station in stations:
        key = circuit_key(station.circuit_name)
        by_circuit.setdefault(key, []).append(station)
        labels.setdefault(key, station.circuit_name)
    if len(by_circuit) <= 1:
        return []
    originals = [key for key, items in by_circuit.items() if all(s.mirror_of_id is None for s in items)]
    if len(originals) != 1:
        return [
            "Hay más de un circuito con estaciones propias. En un ECOE en espejo se diseña UN "
            "circuito y los demás se crean con «Crear circuito espejo»: "
            + ", ".join(labels[key] for key in originals or by_circuit)
            + "."
        ]
    base_key = originals[0]
    base = {s.id: s for s in by_circuit[base_key]}
    issues: list[str] = []
    for key, items in by_circuit.items():
        if key == base_key:
            continue
        label = labels[key]
        mirrored = {s.mirror_of_id: s for s in items if s.mirror_of_id in base}
        strays = [s for s in items if s.mirror_of_id not in base]
        if strays:
            issues.append(
                f"«{label}» tiene estaciones que no son espejo de «{labels[base_key]}»: "
                + ", ".join(s.name for s in strays) + "."
            )
        missing = [s for sid, s in base.items() if sid not in mirrored]
        if missing:
            issues.append(
                f"A «{label}» le faltan estaciones espejo: "
                + ", ".join(f"{s.station_number}. {s.name}" for s in missing)
                + ". Usa «Sincronizar espejo»."
            )
        for source_id, mirror in mirrored.items():
            source = base[source_id]
            different = [f for f in SHARED_DESIGN_FIELDS if getattr(source, f) != getattr(mirror, f)]
            if different:
                issues.append(
                    f"La estación «{mirror.name}» de «{label}» difiere de su original "
                    f"({', '.join(different)}). Usa «Sincronizar espejo»."
                )
    return issues
