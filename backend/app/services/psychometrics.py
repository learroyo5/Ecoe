"""Analítica psicométrica del ECOE (OPT-18).

Deriva métricas de calidad de la medición a partir de la matriz de
%-de-logro por estación que ya produce `compute_station_results` (OPT-16):

- **Por estación**: n, media/DE del % y del puntaje crudo, min/max, histograma
  de nota 1.0–7.0.
- **Inter-estación**: α de Cronbach (análisis por caso completo / *listwise*) y
  discriminación estación-total corregida (correlación de la estación con el
  total del circuito menos esa estación).
- **Por criterio de pauta** (F2): índice de dificultad y punto-biserial de cada
  `AssessmentItem` (estaciones con evaluador) o `question_<n>` puntuable
  (estaciones con formulario).

Todo se calcula **en vivo** en cada request (sin cacheo). Los casos degenerados
(n < 2, varianza 0, menos de 2 estaciones) devuelven `None`, nunca una
excepción. `scipy` no está disponible: las correlaciones y varianzas se calculan
con `numpy`.

Ver `docs/optimizacion/PLANES/OPT-18__psicometria.md`.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEEvent,
    EvaluatorRecord,
    Station,
    Student,
    StudentResponse,
)
from app.models.enums import SessionMode
from app.services.results import (
    compute_equivalent_grade,
    compute_station_results,
    read_station_results,
)

# Umbrales por defecto. Todo lo que cae fuera de estos rangos genera una
# **advertencia** (nunca un bloqueo). Si más adelante se quieren configurables
# por evento → columna JSON en `ecoe_events` → migración → gate (no en OPT-18).
PSYCHO_THRESHOLDS: dict[str, float] = {
    "cronbach_alpha_min": 0.6,
    "station_discrimination_min": 0.2,
    "difficulty_min": 0.2,
    "difficulty_max": 0.9,
    "point_biserial_min": 0.2,
    # No es un umbral de calidad: por debajo de este n las métricas son poco
    # fiables y se agrega un caveat de muestra.
    "small_sample_n": 10,
}

VALID_MODES = {SessionMode.ejecucion.value, SessionMode.pilotaje.value}


def _sample_sd(values: list[float]) -> float | None:
    """DE muestral (n−1). `None` con menos de dos observaciones."""
    if len(values) < 2:
        return None
    return round(statistics.stdev(values), 4)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.fmean(values), 4)


def _pearson(x: list[float], y: list[float]) -> float | None:
    """Correlación de Pearson. `None` si n < 2 o varianza 0 en cualquier vector."""
    if len(x) < 2 or len(y) < 2 or len(x) != len(y):
        return None
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    if float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return None
    r = float(np.corrcoef(a, b)[0, 1])
    if not math.isfinite(r):
        return None
    return round(r, 4)


def _population_variance(values: list[float]) -> float:
    if not values:
        return 0.0
    arr = np.asarray(values, dtype=float)
    return float(np.var(arr))  # ddof=0 → poblacional


def _grade_histogram(percents: list[float], passing_reference_percent: float) -> list[dict]:
    """Histograma por tramo de nota 1.0–7.0 (no por decil de %).

    Cada % de logro de la estación se convierte a nota con
    `compute_equivalent_grade` y se agrupa por parte entera (7.0 cae en el
    tramo 7). Siempre devuelve los 7 tramos, con `count = 0` si están vacíos.
    """
    buckets = {grade: 0 for grade in range(1, 8)}
    for percent in percents:
        grade = compute_equivalent_grade(percent, passing_reference_percent)
        bucket = min(7, max(1, int(math.floor(grade))))
        buckets[bucket] += 1
    return [
        {"grade": grade, "label": f"{grade}.0–{grade}.9" if grade < 7 else "7.0", "count": count}
        for grade, count in sorted(buckets.items())
    ]


def _gather_station_rows(
    db: Session, ecoe_event_id: int, mode: str
) -> tuple[list[dict], bool]:
    """Filas `(student_id, station_id, obtained, max, percent)` según el modo.

    `mode == ejecucion`: usa `read_station_results` (snapshot-aware, OPT-16): si
    el evento está cerrado/archivado con snapshot `StationResult`, las métricas
    se derivan del snapshot congelado; si no, cálculo en vivo.
    `mode == pilotaje`: **siempre** en vivo (no hay snapshot de pilotaje).
    """
    if mode == SessionMode.pilotaje.value:
        return compute_station_results(db, ecoe_event_id, mode=mode), False
    return read_station_results(db, ecoe_event_id)


def station_stats(
    station_rows: list[dict],
    stations: list[Station],
    passing_reference_percent: float,
) -> list[dict]:
    """Agregado por estación: n, media/DE de % y puntaje, min/max, histograma."""
    rows_by_station: dict[int, list[dict]] = defaultdict(list)
    for row in station_rows:
        rows_by_station[row["station_id"]].append(row)

    out: list[dict] = []
    for station in stations:
        rows = rows_by_station.get(station.id, [])
        percents = [row["percent_score"] for row in rows]
        scores = [row["obtained_score"] for row in rows]
        maxes = [row["max_score"] for row in rows]
        out.append({
            "station_id": station.id,
            "station_number": station.station_number,
            "station_name": station.name,
            "circuit_name": station.circuit_name,
            "n": len(rows),
            "mean_percent": _mean(percents),
            "sd_percent": _sample_sd(percents),
            "mean_score": _mean(scores),
            "sd_score": _sample_sd(scores),
            "mean_max": _mean(maxes),
            "min_percent": round(min(percents), 4) if percents else None,
            "max_percent": round(max(percents), 4) if percents else None,
            "grade_histogram": _grade_histogram(percents, passing_reference_percent),
        })
    out.sort(key=lambda item: (item["station_number"], item["station_id"]))
    return out


def reliability(station_rows: list[dict], stations: list[Station]) -> dict:
    """α de Cronbach y discriminación estación-total, ambos *listwise*.

    Un estudiante entra al cálculo solo si tiene % en **todas** las estaciones
    del circuito que registraron actividad (solo estaciones con `max > 0`).
    Se reporta `n_complete` (los que entraron) y `n_total` (los que tienen al
    menos un %). Casos degenerados → `cronbach_alpha`/`r` en `None`.
    """
    # P[student_id][station_id] = % de logro; solo celdas con max > 0.
    matrix: dict[int, dict[int, float]] = defaultdict(dict)
    for row in station_rows:
        if row["max_score"] and row["max_score"] > 0:
            matrix[row["student_id"]][row["station_id"]] = row["percent_score"]

    considered = [
        station
        for station in stations
        if any(station.id in cols for cols in matrix.values())
    ]
    considered.sort(key=lambda s: (s.station_number, s.id))
    considered_ids = [s.id for s in considered]
    k = len(considered_ids)

    n_total = len(matrix)
    complete_students = [
        student_id
        for student_id, cols in matrix.items()
        if all(station_id in cols for station_id in considered_ids)
    ]
    n_complete = len(complete_students)

    # Matriz densa n_complete × k para las cuentas vectoriales.
    dense = [
        [matrix[student_id][station_id] for station_id in considered_ids]
        for student_id in complete_students
    ]

    cronbach_alpha: float | None = None
    if k >= 2 and n_complete >= 2:
        columns = [[row[j] for row in dense] for j in range(k)]
        totals = [sum(row) for row in dense]
        var_total = _population_variance(totals)
        if var_total > 0:
            var_items = sum(_population_variance(col) for col in columns)
            cronbach_alpha = round(
                (k / (k - 1)) * (1 - var_items / var_total), 4
            )

    discrimination: list[dict] = []
    for j, station in enumerate(considered):
        r: float | None = None
        if n_complete >= 2 and k >= 2:
            station_vec = [row[j] for row in dense]
            rest_vec = [sum(v for m, v in enumerate(row) if m != j) for row in dense]
            r = _pearson(station_vec, rest_vec)
        discrimination.append({
            "station_id": station.id,
            "station_number": station.station_number,
            "station_name": station.name,
            "r": r,
        })

    return {
        "cronbach_alpha": cronbach_alpha,
        "n_complete": n_complete,
        "n_total": n_total,
        "k_stations": k,
        "station_discrimination": discrimination,
    }


def _evaluate_thresholds(
    stats: list[dict], reliability_block: dict, item_analysis: list[dict]
) -> list[dict]:
    """Traduce las métricas fuera de umbral a advertencias no bloqueantes."""
    warnings: list[dict] = []
    small_n = PSYCHO_THRESHOLDS["small_sample_n"]

    alpha = reliability_block.get("cronbach_alpha")
    if alpha is not None and alpha < PSYCHO_THRESHOLDS["cronbach_alpha_min"]:
        warnings.append({
            "code": "cronbach_alpha_low",
            "severity": "warning",
            "metric": "cronbach_alpha",
            "value": alpha,
            "message": (
                f"Consistencia interna baja (α = {alpha:.2f}): las estaciones no "
                "miden un constructo común."
            ),
        })

    for entry in reliability_block.get("station_discrimination", []):
        r = entry.get("r")
        if r is None:
            continue
        number = entry.get("station_number")
        if r < 0:
            warnings.append({
                "code": "station_discrimination_negative",
                "severity": "warning",
                "metric": "station_discrimination",
                "value": r,
                "station_id": entry.get("station_id"),
                "station_number": number,
                "message": (
                    f"La estación {number} discrimina en sentido inverso "
                    f"(r = {r:.2f}): revisar pauta o dificultad."
                ),
            })
        elif r < PSYCHO_THRESHOLDS["station_discrimination_min"]:
            warnings.append({
                "code": "station_discrimination_low",
                "severity": "warning",
                "metric": "station_discrimination",
                "value": r,
                "station_id": entry.get("station_id"),
                "station_number": number,
                "message": (
                    f"La estación {number} discrimina poco (r = {r:.2f}): su "
                    "resultado casi no se relaciona con el desempeño global."
                ),
            })

    for entry in stats:
        n = entry.get("n") or 0
        if 0 < n < small_n:
            warnings.append({
                "code": "small_sample",
                "severity": "caveat",
                "metric": "n",
                "value": n,
                "station_id": entry.get("station_id"),
                "station_number": entry.get("station_number"),
                "message": (
                    f"Estación {entry.get('station_number')}: métricas poco fiables "
                    f"con n = {n} (< {small_n})."
                ),
            })

    for entry in item_analysis:
        label = entry.get("criterion_label") or entry.get("criterion_key")
        number = entry.get("station_number")
        difficulty = entry.get("difficulty")
        if difficulty is not None and not (
            PSYCHO_THRESHOLDS["difficulty_min"]
            <= difficulty
            <= PSYCHO_THRESHOLDS["difficulty_max"]
        ):
            hard_or_easy = "muy difícil" if difficulty < PSYCHO_THRESHOLDS["difficulty_min"] else "muy fácil"
            warnings.append({
                "code": "item_difficulty_out_of_range",
                "severity": "warning",
                "metric": "difficulty",
                "value": difficulty,
                "station_id": entry.get("station_id"),
                "station_number": number,
                "criterion_key": entry.get("criterion_key"),
                "message": (
                    f"Estación {number} · «{label}»: criterio {hard_or_easy} "
                    f"(p = {difficulty:.2f})."
                ),
            })
        rpb = entry.get("point_biserial")
        if rpb is None:
            continue
        if rpb < 0:
            warnings.append({
                "code": "item_point_biserial_negative",
                "severity": "warning",
                "metric": "point_biserial",
                "value": rpb,
                "station_id": entry.get("station_id"),
                "station_number": number,
                "criterion_key": entry.get("criterion_key"),
                "message": (
                    f"Estación {number} · «{label}»: criterio invertido "
                    f"(r_pb = {rpb:.2f}); quienes rinden peor lo obtienen más."
                ),
            })
        elif rpb < PSYCHO_THRESHOLDS["point_biserial_min"]:
            warnings.append({
                "code": "item_point_biserial_low",
                "severity": "warning",
                "metric": "point_biserial",
                "value": rpb,
                "station_id": entry.get("station_id"),
                "station_number": number,
                "criterion_key": entry.get("criterion_key"),
                "message": (
                    f"Estación {number} · «{label}»: criterio discrimina poco "
                    f"(r_pb = {rpb:.2f})."
                ),
            })

    return warnings


# ── F2 · Item analysis por criterio de pauta ─────────────────────────────


def _evaluator_item_scores(answers: dict | None) -> dict[str, float]:
    """Extrae `{clave_criterio: puntaje}` de `EvaluatorRecord.answers`.

    Forma habitual: `{"tool_id", "tool_name", "tool_type", "item_scores": {...}}`
    (ver `frontend/src/app/(app)/evaluator/page.tsx`). Algunos registros
    históricos guardan el mapa plano directamente en `answers`. La clave puede
    ser el `AssessmentItem.id` o su `order_index` (el front usa
    `String(item.id ?? item.order_index ?? index)`); ambas se resuelven después.
    """
    if not isinstance(answers, dict):
        return {}
    raw = answers.get("item_scores")
    if not isinstance(raw, dict):
        # Fallback: `answers` es el mapa plano (registros antiguos / scripts).
        raw = {
            key: value
            for key, value in answers.items()
            if key not in {"tool_id", "tool_name", "tool_type", "item_scores"}
        }
    scores: dict[str, float] = {}
    for key, value in raw.items():
        try:
            scores[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return scores


def item_analysis(db: Session, ecoe_event_id: int, mode: str) -> list[dict]:
    """Dificultad y punto-biserial por criterio de pauta (best-effort).

    Solo cubre estaciones con **pauta estructurada**:
    - Estación con `assessment_tool_id`: criterios = `AssessmentItem`; puntaje
      del alumno leído de `EvaluatorRecord.answers["item_scores"]`
      (`is_draft == False`, `mode` dado). El `score_obtained` del evaluador es
      *client-supplied* y `item_scores` no se valida contra él en el backend →
      el análisis es **best-effort** y solo para pautas usadas de forma
      estructurada (no el campo de puntaje libre).
    - Estación con formulario puntuable: criterios = cada `question_<n>` con
      `max > 0` en `StudentResponse.grading` (`score_obtained IS NOT NULL`).

    Métricas por criterio (sobre los alumnos con dato en ese criterio — análisis
    *pairwise*, se reporta `n`):
    - **dificultad** `p` = media de `earned / max`.
    - **punto-biserial** = `pearson(earned_i, T_i − earned_i)` con `T_i` el
      puntaje total del alumno en **esa estación** (corrección ítem-resto).
      `None` si varianza 0 (p. ej. todos al máximo).
    """
    stations = db.scalars(
        select(Station)
        .where(Station.ecoe_event_id == ecoe_event_id)
        .order_by(Station.station_number.asc(), Station.id.asc())
    ).all()
    if not stations:
        return []

    tool_ids = [s.assessment_tool_id for s in stations if s.assessment_tool_id]
    items_by_tool: dict[int, list[AssessmentItem]] = defaultdict(list)
    if tool_ids:
        tools = db.scalars(
            select(AssessmentTool).where(AssessmentTool.id.in_(tool_ids))
        ).all()
        for tool in tools:
            items_by_tool[tool.id] = sorted(tool.items, key=lambda it: it.order_index)

    out: list[dict] = []

    for station in stations:
        # (criterion_key, criterion_label, max) -> {student_id: earned}
        criteria: dict[tuple[str, str, float], dict[int, float]] = {}

        if station.assessment_tool_id and items_by_tool.get(station.assessment_tool_id):
            items = items_by_tool[station.assessment_tool_id]
            by_id = {str(it.id): it for it in items}
            by_order = {str(it.order_index): it for it in items}
            records = db.scalars(
                select(EvaluatorRecord).where(
                    EvaluatorRecord.ecoe_event_id == ecoe_event_id,
                    EvaluatorRecord.station_id == station.id,
                    EvaluatorRecord.mode == mode,
                    EvaluatorRecord.is_draft.is_(False),
                )
            ).all()
            for item in items:
                criteria[(str(item.id), item.label, float(item.score_per_item))] = {}
            for record in records:
                scores = _evaluator_item_scores(record.answers)
                for key, value in scores.items():
                    item = by_id.get(key) or by_order.get(key)
                    if item is None:
                        continue
                    criteria[(str(item.id), item.label, float(item.score_per_item))][
                        record.student_id
                    ] = value

        elif station.requires_student_form:
            responses = db.scalars(
                select(StudentResponse).where(
                    StudentResponse.ecoe_event_id == ecoe_event_id,
                    StudentResponse.station_id == station.id,
                    StudentResponse.mode == mode,
                    StudentResponse.score_obtained.is_not(None),
                )
            ).all()
            for response in responses:
                grading = response.grading or {}
                for key, cell in grading.items():
                    if not isinstance(cell, dict):
                        continue
                    try:
                        cell_max = float(cell.get("max") or 0)
                        earned = float(cell.get("earned"))
                    except (TypeError, ValueError):
                        continue
                    if cell_max <= 0:
                        continue
                    criteria.setdefault((key, key, cell_max), {})[response.student_id] = earned

        if not criteria:
            continue

        # Totales por alumno en ESTA estación (corrección ítem-resto).
        totals: dict[int, float] = defaultdict(float)
        for (_key, _label, _max), per_student in criteria.items():
            for student_id, earned in per_student.items():
                totals[student_id] += earned

        for (key, label, crit_max), per_student in criteria.items():
            if not per_student:
                continue
            student_ids = sorted(per_student)
            earned_vec = [per_student[sid] for sid in student_ids]
            rest_vec = [totals[sid] - per_student[sid] for sid in student_ids]
            difficulty = (
                round(statistics.fmean(earned_vec) / crit_max, 4) if crit_max > 0 else None
            )
            out.append({
                "station_id": station.id,
                "station_number": station.station_number,
                "station_name": station.name,
                "criterion_key": key,
                "criterion_label": label,
                "max": crit_max,
                "n": len(student_ids),
                "difficulty": difficulty,
                "point_biserial": _pearson(earned_vec, rest_vec),
            })

    return out


def build_psychometrics_block(db: Session, ecoe_event_id: int, mode: str) -> dict:
    """Orquesta el bloque completo de analítica psicométrica para un modo."""
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    passing_reference_percent = (
        ecoe_event.passing_reference_percent if ecoe_event else 60.0
    )
    station_rows, frozen = _gather_station_rows(db, ecoe_event_id, mode)
    stations = db.scalars(
        select(Station)
        .where(Station.ecoe_event_id == ecoe_event_id)
        .order_by(Station.station_number.asc(), Station.id.asc())
    ).all()
    students = {
        s.id: s
        for s in db.scalars(
            select(Student).where(Student.ecoe_event_id == ecoe_event_id)
        ).all()
    }

    stats = station_stats(station_rows, list(stations), passing_reference_percent)
    reliability_block = reliability(station_rows, list(stations))
    items = item_analysis(db, ecoe_event_id, mode)
    warnings = _evaluate_thresholds(stats, reliability_block, items)

    return {
        "mode": mode,
        "frozen": frozen,
        "passing_reference_percent": passing_reference_percent,
        "student_count": len(students),
        "station_stats": stats,
        "reliability": reliability_block,
        "item_analysis": items,
        "warnings": warnings,
        "thresholds": PSYCHO_THRESHOLDS,
    }
