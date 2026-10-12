"""Carga de la nómina de estudiantes desde un archivo.

Acepta dos formatos sin que el usuario tenga que elegir:

- la **plantilla propia** (títulos en la primera fila: nombre, apellidos,
  rut, correo, grupo, circuito), y
- el **listado oficial de curso** de la universidad, tal como se descarga:
  varias filas de encabezado (asignatura, sección, profesores), y luego
  CORRELATIVO · RUT · DV · REGISTRO · AP.PATERNO · AP.MATERNO · NOMBRES · EMAIL.

``build_import_plan`` decide, fila por fila, qué pasaría (estado, número ECOE,
circuito). La vista previa (``dry_run``) y la carga real usan el mismo plan,
así lo que se muestra es exactamente lo que se guarda.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Station, Student
from app.utils.files import MAX_IMPORT_FILE_BYTES, MAX_IMPORT_ROWS, normalize_header
from app.utils.helpers import (
    format_ecoe_number,
    next_student_ecoe_number,
    normalize_email,
    normalize_rut,
    rut_is_valid,
)

HEADER_SEARCH_ROWS = 60
DEFAULT_GROUP = "Grupo 1"
DEFAULT_CIRCUIT = "Circuito A"
DISTRIBUTIONS = ("file", "halves", "first")

# Título de columna normalizado → campo. El primero que aparezca gana.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "rut": ("rut", "run"),
    "dv": ("dv", "digito", "digito_verificador"),
    "registration": ("registro", "matricula", "n_matricula", "nro_matricula", "numero_matricula",
                     "numero_de_matricula", "registration_number"),
    "paternal": ("ap_paterno", "apellido_paterno", "paterno"),
    "maternal": ("ap_materno", "apellido_materno", "materno"),
    "last_name": ("apellidos", "apellido", "last_name"),
    "name": ("nombres", "nombre", "name"),
    "email": ("email", "correo", "correo_electronico", "e_mail", "mail"),
    "list_number": ("correlativo", "n", "nro", "no", "numero", "numero_lista", "n_lista"),
    "group": ("grupo", "group_name"),
    "circuit": ("circuito", "circuit_name"),
}
_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Datos del curso en el encabezado del listado oficial. No se leen los
# profesores: no hacen falta para cargar la nómina.
_META_PATTERNS = {
    "course": re.compile(r"ASIGNATURA\s*:\s*(.+)", re.IGNORECASE),
    "section": re.compile(r"SECCI[ÓO]N\s*:\s*(.+)", re.IGNORECASE),
    "year": re.compile(r"A[ÑN]O\s*:\s*(\d{4})", re.IGNORECASE),
    "semester": re.compile(r"SEMESTRE\s*:\s*(.+)", re.IGNORECASE),
    "school": re.compile(r"UNID\.?\s*ACAD[ÉE]MICA\s*:\s*(.+)", re.IGNORECASE),
}


@dataclass
class Roster:
    rows: list[dict[str, str]]
    columns: list[str]
    meta: dict[str, str] = field(default_factory=dict)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        if value.is_integer():
            return str(int(value))
    text = str(value).replace(" ", " ").strip()
    return "" if text.lower() == "nan" else text


def _read_grid(filename: str, content: bytes) -> list[list[str]]:
    if len(content) > MAX_IMPORT_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo de importación excede el máximo de {MAX_IMPORT_FILE_BYTES // (1024 * 1024)} MB",
        )
    try:
        if (filename or "").lower().endswith(".csv"):
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = content.decode("latin-1")
            frame = pd.read_csv(
                BytesIO(text.encode("utf-8")), header=None, dtype=str, sep=None, engine="python",
                keep_default_na=False, skip_blank_lines=False,
            )
        else:
            frame = pd.read_excel(BytesIO(content), header=None, dtype=object)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="No se pudo leer el archivo. Verifica que sea un CSV o Excel válido.",
        ) from exc
    if len(frame) > MAX_IMPORT_ROWS + HEADER_SEARCH_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo tiene {len(frame)} filas; el máximo permitido es {MAX_IMPORT_ROWS}",
        )
    return [[_cell(value) for value in row] for row in frame.itertuples(index=False, name=None)]


def _map_columns(header: list[str]) -> dict[str, int]:
    normalized = [normalize_header(cell) for cell in header]
    mapping: dict[str, int] = {}
    for field_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[field_name] = normalized.index(alias)
                break
    return mapping


def read_roster(filename: str, content: bytes) -> Roster:
    grid = _read_grid(filename, content)
    header_index = None
    mapping: dict[str, int] = {}
    for index, row in enumerate(grid[:HEADER_SEARCH_ROWS]):
        candidate = _map_columns(row)
        if "rut" in candidate and ("email" in candidate or "name" in candidate):
            header_index, mapping = index, candidate
            break
    if header_index is None or "email" not in mapping:
        first = next((row for row in grid if any(row)), [])
        detected = [cell for cell in (grid[header_index] if header_index is not None else first) if cell]
        raise HTTPException(
            status_code=400,
            detail=(
                "No se encontró la fila de títulos con las columnas requeridas (RUT y correo/EMAIL). "
                f"Columnas detectadas: {', '.join(detected[:12]) or 'ninguna'}. "
                "Usa la plantilla o el listado oficial de curso sin modificar."
            ),
        )

    meta: dict[str, str] = {}
    for row in grid[:header_index]:
        line = " ".join(cell for cell in row if cell)
        for key, pattern in _META_PATTERNS.items():
            match = pattern.search(line)
            if match and key not in meta:
                value = re.split(r"\s{2,}|\s+SEMESTRE\s*:", match.group(1))[0].strip(" :-")
                if value:
                    meta[key] = value[:120]

    def value(row: list[str], field_name: str) -> str:
        position = mapping.get(field_name)
        return row[position] if position is not None and position < len(row) else ""

    rows: list[dict[str, str]] = []
    for row in grid[header_index + 1:]:
        if not any(row):
            continue
        last_name = value(row, "last_name") or " ".join(
            part for part in (value(row, "paternal"), value(row, "maternal")) if part
        )
        rows.append({
            "rut": normalize_rut(value(row, "rut"), value(row, "dv")),
            "registration_number": value(row, "registration")[:32],
            "name": value(row, "name")[:128],
            "last_name": last_name[:128],
            "email": normalize_email(value(row, "email")),
            "list_number": value(row, "list_number"),
            "group_name": value(row, "group")[:64],
            "circuit_name": value(row, "circuit")[:64],
        })
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo tiene {len(rows)} filas; el máximo permitido es {MAX_IMPORT_ROWS}",
        )
    return Roster(rows=rows, columns=sorted(mapping), meta=meta)


def event_circuits(db: Session, ecoe_event_id: int) -> list[str]:
    """Circuitos del ECOE en orden de estación (el original antes que su espejo)."""
    rows = db.execute(
        select(Station.circuit_name, func.min(Station.station_number))
        .where(Station.ecoe_event_id == ecoe_event_id)
        .group_by(Station.circuit_name)
    ).all()
    seen: dict[str, str] = {}
    for name, _ in sorted(rows, key=lambda row: row[1] or 0):
        seen.setdefault(str(name or "").strip().lower(), str(name or "").strip())
    return [name for name in seen.values() if name]


def build_import_plan(
    db: Session,
    ecoe_event_id: int,
    roster: Roster,
    *,
    distribution: str | None = None,
    use_list_numbers: bool | None = None,
) -> dict[str, Any]:
    existing = db.scalars(select(Student.rut).where(Student.ecoe_event_id == ecoe_event_id)).all()
    existing_keys = {normalize_rut(rut) for rut in existing}
    circuits = event_circuits(db, ecoe_event_id)
    circuit_by_key = {name.lower(): name for name in circuits}
    file_has_circuit = any(row["circuit_name"] for row in roster.rows)

    # 1. Estado de cada fila.
    planned: list[dict[str, Any]] = []
    seen_in_file: set[str] = set()
    for position, row in enumerate(roster.rows, start=1):
        entry: dict[str, Any] = {**row, "row": position, "warnings": []}
        if not row["rut"]:
            entry["status"] = "sin_rut"
        elif not row["email"] or not _EMAIL_SHAPE.match(row["email"]):
            entry["status"] = "sin_correo"
        elif not (row["name"] or row["last_name"]):
            entry["status"] = "sin_nombre"
        elif row["rut"] in existing_keys:
            entry["status"] = "ya_cargado"
        elif row["rut"] in seen_in_file:
            entry["status"] = "repetido"
        else:
            entry["status"] = "nuevo"
            seen_in_file.add(row["rut"])
            if not rut_is_valid(row["rut"]):
                # No bloquea: puede ser un pasaporte o un identificador provisorio.
                entry["warnings"].append("El RUT no tiene un dígito verificador válido: revísalo.")
        planned.append(entry)
    new_rows = [entry for entry in planned if entry["status"] == "nuevo"]

    # 2. Circuito.
    options = ["first"]
    if len(circuits) > 1:
        options.insert(0, "halves")
    if file_has_circuit:
        options.insert(0, "file")
    if distribution not in options:
        distribution = options[0]
    target_circuits = circuits or [DEFAULT_CIRCUIT]
    if distribution == "halves":
        # Partes iguales en el orden de la lista: 1–26 al A, 27–52 al B.
        size = -(-len(new_rows) // len(target_circuits)) or 1
        for index, entry in enumerate(new_rows):
            entry["circuit_name"] = target_circuits[min(index // size, len(target_circuits) - 1)]
    elif distribution == "file":
        for entry in new_rows:
            requested = entry["circuit_name"] or target_circuits[0]
            entry["circuit_name"] = circuit_by_key.get(requested.lower(), requested)
            if circuits and requested.lower() not in circuit_by_key:
                entry["warnings"].append(f"El circuito «{requested}» no existe en este ECOE.")
    else:
        for entry in new_rows:
            entry["circuit_name"] = target_circuits[0]

    # 3. Número ECOE: el correlativo de la lista si el ECOE parte vacío y la
    # lista lo trae limpio; si no, se continúa la numeración existente.
    list_numbers = [int(entry["list_number"]) for entry in new_rows if entry["list_number"].isdigit()]
    can_use_list_numbers = (
        not existing
        and bool(new_rows)
        and len(list_numbers) == len(new_rows)
        and len(set(list_numbers)) == len(list_numbers)
        and min(list_numbers) > 0
    )
    use_list_numbers = can_use_list_numbers and use_list_numbers is not False
    if use_list_numbers:
        width = max(3, len(str(max(list_numbers))))
        for entry in new_rows:
            entry["ecoe_number"] = format_ecoe_number(int(entry["list_number"]), width)
    else:
        next_number = next_student_ecoe_number(db, ecoe_event_id)
        value = int(re.sub(r"\D", "", next_number) or 0)
        width = len(re.sub(r"\D", "", next_number))
        for entry in new_rows:
            entry["ecoe_number"] = format_ecoe_number(value, width)
            value += 1
    for entry in planned:
        entry.setdefault("ecoe_number", "")
        if entry["status"] == "nuevo":
            entry["group_name"] = entry["group_name"] or DEFAULT_GROUP
        entry.pop("list_number", None)

    counts: dict[str, int] = {}
    for entry in planned:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    per_circuit: dict[str, int] = {}
    for entry in new_rows:
        per_circuit[entry["circuit_name"]] = per_circuit.get(entry["circuit_name"], 0) + 1
    return {
        "source": {
            "format": "listado_oficial" if roster.meta or "dv" in roster.columns else "plantilla",
            **roster.meta,
        },
        "rows": planned,
        "total_rows": len(planned),
        "counts": counts,
        "to_import": len(new_rows),
        "with_warnings": sum(1 for entry in new_rows if entry["warnings"]),
        "per_circuit": per_circuit,
        "circuits": circuits,
        "distribution": distribution,
        "distribution_options": options,
        "can_use_list_numbers": can_use_list_numbers,
        "use_list_numbers": use_list_numbers,
        "existing_students": len(existing),
    }


def apply_import_plan(db: Session, ecoe_event_id: int, plan: dict[str, Any]) -> list[Student]:
    students: list[Student] = []
    for entry in plan["rows"]:
        if entry["status"] != "nuevo":
            continue
        student = Student(
            ecoe_event_id=ecoe_event_id,
            name=entry["name"],
            last_name=entry["last_name"],
            rut=entry["rut"],
            registration_number=entry["registration_number"] or None,
            email=entry["email"],
            ecoe_number=entry["ecoe_number"],
            group_name=entry["group_name"],
            circuit_name=entry["circuit_name"],
        )
        db.add(student)
        students.append(student)
    return students
