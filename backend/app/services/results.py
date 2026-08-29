"""Results computation, persistence, traceability, and export services."""

import statistics
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datetime import datetime

from app.core.config import get_settings
from app.models.entities import (
    AuditLog,
    ContingencyExport,
    ECOEEvent,
    ECOEResult,
    EvaluatorRecord,
    PilotRun,
    StaffAssignment,
    Station,
    StationCheckIn,
    StationResult,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, RoleCode, SessionMode

# Una vez cerrado/archivado el evento, los resultados oficiales son el snapshot
# `ECOEResult` escrito al cierre: ninguna edición posterior de respuestas o
# registros debe mover el número que sirve `/results` o el export.
FROZEN_RESULT_STATUSES = {ECOEStatus.cerrado.value, ECOEStatus.archivado.value}


def compute_equivalent_grade(percentage: float, passing_reference_percent: float) -> float:
    """Chilean 1.0-7.0 grading scale ("escala de exigencia").

    `passing_reference_percent` maps to exactly 4.0 (the minimum passing
    grade); the scale is piecewise-linear below and above that point, so a
    stricter or looser passing threshold per ECOE actually changes grades
    instead of being decorative.
    """
    passing = min(max(passing_reference_percent, 0.01), 99.99)
    if percentage >= passing:
        return 4.0 + (percentage - passing) / (100 - passing) * 3.0
    return 1.0 + (percentage / passing) * 3.0


def compute_results(db: Session, ecoe_event_id: int) -> list[dict]:
    """Nota agregada por estudiante.

    OPT-17 — normalización por estación: `percentage` es el **promedio de los
    porcentajes de logro por estación** del estudiante (cada estación
    normalizada a su propio máximo → todas pesan igual), no la razón de sumas
    crudas `sum(obtenido)/sum(máx)*100` de antes. El estándar sigue siendo
    **compensatorio**: un solo umbral global (`passing_reference_percent`) sobre
    ese promedio, sin lógica conjuntiva ni umbral por estación.

    `total_score` / `max_score` se mantienen como **suma cruda** de los
    registros del estudiante (informativos; el analista externo los espera). A
    partir de OPT-17, para eventos con estaciones de máximo heterogéneo,
    `percentage` deja de ser `total_score / max_score * 100`.

    Se reescribe sobre `compute_station_results` (OPT-16), que aplica
    exactamente los mismos filtros que antes usaba `compute_results`
    (`mode == ejecucion`, `EvaluatorRecord.is_draft == False`,
    `StudentResponse.score_obtained IS NOT NULL`). OPT-17 no introduce filtros
    nuevos; sólo cambia cómo se combinan las filas.
    """
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    passing_reference_percent = ecoe_event.passing_reference_percent if ecoe_event else 60.0
    students = db.scalars(
        select(Student).where(Student.ecoe_event_id == ecoe_event_id, Student.is_active.is_(True))
    ).all()
    station_rows_by_student: dict[int, list[dict]] = defaultdict(list)
    for row in compute_station_results(db, ecoe_event_id):
        station_rows_by_student[row["student_id"]].append(row)
    results = []
    for student in students:
        rows = station_rows_by_student.get(student.id, [])
        # Sólo las estaciones con máximo > 0 pueden aportar un % de logro; una
        # fila con `max == 0` entra igual a las sumas crudas pero no a la media.
        scored = [row for row in rows if row["max_score"] and row["max_score"] > 0]
        raw_obtained = sum(row["obtained_score"] for row in rows)
        raw_max = sum(row["max_score"] for row in rows)
        if scored:
            percentage = sum(row["percent_score"] for row in scored) / len(scored)
        else:
            # Estudiante sin ninguna estación puntuable (ausente / sin
            # actividad): 0 %, nota mínima — igual que antes de OPT-17.
            percentage = 0.0
        grade = compute_equivalent_grade(percentage, passing_reference_percent)
        results.append({
            "student_id": student.id,
            "student_name": f"{student.name} {student.last_name}",
            "ecoe_number": student.ecoe_number,
            "total_score": round(raw_obtained, 2),
            "max_score": round(raw_max, 2),
            "percentage": round(percentage, 2),
            "equivalent_grade": round(grade, 2),
            # OPT-17: nº de estaciones con actividad puntuable que entraron al
            # promedio (el divisor de `percentage`). Campo del dict, no de BD.
            "stations_counted": len(scored),
        })
    return results


def compute_station_results(
    db: Session,
    ecoe_event_id: int,
    *,
    mode: str = SessionMode.ejecucion.value,
) -> list[dict]:
    """Nota cruda por (estudiante, estación) — desglose de `compute_results`.

    Reusa **exactamente los mismos filtros** que `compute_results`, cambiando el
    `GROUP BY student_id` por `GROUP BY student_id, station_id`:

    - `EvaluatorRecord`: `mode == mode`, `is_draft == False`.
    - `StudentResponse`: `mode == mode`, `score_obtained IS NOT NULL`
      (los pendientes de corrección diferida no entran hasta que se corrigen).

    Solo emite una fila por par (estudiante, estación) con **al menos una
    contribución** — nunca 0/0 para cada estudiante × cada estación.

    `mode` es aditivo: el default `"ejecucion"` preserva el comportamiento de
    OPT-16. OPT-18 lo llamará con `mode="pilotaje"`; su salida **no** se
    persiste en `station_results` (la constraint única no tiene columna `mode`).

    Función de módulo reutilizable: OPT-17 la usará para reescribir
    `compute_results`.
    """
    combined: dict[tuple[int, int], list[float]] = {}
    for source, extra_filters in (
        (
            (
                EvaluatorRecord.student_id,
                EvaluatorRecord.station_id,
                func.sum(EvaluatorRecord.score_obtained),
                func.sum(EvaluatorRecord.max_score),
                EvaluatorRecord.ecoe_event_id == ecoe_event_id,
                EvaluatorRecord.mode == mode,
            ),
            (EvaluatorRecord.is_draft.is_(False),),
        ),
        (
            (
                StudentResponse.student_id,
                StudentResponse.station_id,
                func.sum(StudentResponse.score_obtained),
                func.sum(StudentResponse.max_score),
                StudentResponse.ecoe_event_id == ecoe_event_id,
                StudentResponse.mode == mode,
            ),
            (StudentResponse.score_obtained.is_not(None),),
        ),
    ):
        student_col, station_col, sum_obtained, sum_max, event_pred, mode_pred = source
        rows = db.execute(
            select(student_col, station_col, sum_obtained, sum_max)
            .where(event_pred, mode_pred, *extra_filters)
            .group_by(student_col, station_col)
        ).all()
        for student_id, station_id, obtained, max_score in rows:
            acc = combined.setdefault((int(student_id), int(station_id)), [0.0, 0.0])
            acc[0] += obtained or 0
            acc[1] += max_score or 0

    results: list[dict] = []
    for (student_id, station_id), (obtained, max_score) in combined.items():
        percent = (obtained / max_score * 100) if max_score else 0.0
        results.append({
            "student_id": student_id,
            "station_id": station_id,
            "obtained_score": round(obtained, 2),
            "max_score": round(max_score, 2),
            "percent_score": round(percent, 2),
        })
    results.sort(key=lambda item: (item["student_id"], item["station_id"]))
    return results


def read_station_results(
    db: Session, ecoe_event_id: int
) -> tuple[list[dict], bool]:
    """Vista de nota por estación para lectura (`/results`, export).

    Análoga a `read_results`: si el evento está `cerrado`/`archivado` **y** hay
    filas `StationResult`, sirve el snapshot congelado (`frozen=True`). En
    cualquier otro estado —o si el cierre no dejó filas (cierre previo a
    OPT-16)— recalcula en vivo con `compute_station_results` y `frozen=False`.
    """
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if ecoe_event is not None and str(ecoe_event.status) in FROZEN_RESULT_STATUSES:
        snapshots = db.scalars(
            select(StationResult)
            .where(StationResult.ecoe_event_id == ecoe_event_id)
            .order_by(StationResult.student_id.asc(), StationResult.station_id.asc())
        ).all()
        if snapshots:
            return [
                {
                    "student_id": snap.student_id,
                    "station_id": snap.station_id,
                    "obtained_score": round(snap.obtained_score, 2),
                    "max_score": round(snap.max_score, 2),
                    "percent_score": round(snap.percent_score, 2),
                }
                for snap in snapshots
            ], True
    return compute_station_results(db, ecoe_event_id), False


def build_station_score_block(
    station_rows: list[dict],
    stations: list[Station],
    students: dict[int, Student],
) -> dict:
    """Bloque `by_station` del payload de `/results` — puro Python, sin BD.

    Toma la nota cruda por (estudiante, estación) (`compute_station_results` o el
    snapshot) + los `Station` del evento + el mapa de estudiantes y arma:

    - `stations`: agregado por estación. `n` estudiantes con nota, media/DE del
      puntaje crudo (`mean_score`/`sd_score`), media del máximo (`mean_max`) y
      media/DE/min/max del porcentaje (`*_percent`). La DE es **muestral**
      (`statistics.stdev`, n−1); `None` cuando `n < 2`. Estaciones sin ninguna
      nota → fila con `n=0` y agregados `None`.
    - `students`: formato largo, una fila por (estudiante, estación) con nota.

    Como el agregado se deriva del conjunto servido (snapshot o vivo), hereda la
    inmutabilidad de OPT-1 sin necesidad de almacenarse.
    """
    stations_by_id = {station.id: station for station in stations}
    rows_by_station: dict[int, list[dict]] = {}
    for row in station_rows:
        rows_by_station.setdefault(row["station_id"], []).append(row)

    stations_block: list[dict] = []
    for station in stations:
        rows = rows_by_station.get(station.id, [])
        n = len(rows)
        obtained = [row["obtained_score"] for row in rows]
        maxes = [row["max_score"] for row in rows]
        percents = [row["percent_score"] for row in rows]
        stations_block.append({
            "station_id": station.id,
            "station_number": station.station_number,
            "station_name": station.name,
            "circuit_name": station.circuit_name,
            "n": n,
            "mean_score": round(statistics.fmean(obtained), 2) if n else None,
            "sd_score": round(statistics.stdev(obtained), 2) if n >= 2 else None,
            "mean_max": round(statistics.fmean(maxes), 2) if n else None,
            "mean_percent": round(statistics.fmean(percents), 2) if n else None,
            "sd_percent": round(statistics.stdev(percents), 2) if n >= 2 else None,
            "min_percent": round(min(percents), 2) if n else None,
            "max_percent": round(max(percents), 2) if n else None,
        })
    stations_block.sort(key=lambda item: (item["station_number"], item["station_id"]))

    students_block: list[dict] = []
    for row in station_rows:
        student = students.get(row["student_id"])
        station = stations_by_id.get(row["station_id"])
        students_block.append({
            "student_id": row["student_id"],
            "ecoe_number": student.ecoe_number if student else None,
            "student_name": f"{student.name} {student.last_name}" if student else "",
            "station_id": row["station_id"],
            "station_number": station.station_number if station else None,
            "station_name": station.name if station else "",
            "obtained_score": row["obtained_score"],
            "max_score": row["max_score"],
            "percent_score": row["percent_score"],
        })
    students_block.sort(
        key=lambda item: (
            item["ecoe_number"] or "",
            item["station_number"] or 0,
        )
    )
    return {"stations": stations_block, "students": students_block}


def read_results(
    db: Session, ecoe_event_id: int
) -> tuple[list[dict], bool, datetime | None]:
    """Vista de resultados para lectura (`/results`, export).

    Si el evento está `cerrado`/`archivado` **y** existe snapshot `ECOEResult`,
    devuelve el snapshot congelado (misma forma que `compute_results`) junto con
    `frozen=True` y la fecha de consolidación (`ECOEResult.updated_at`). En
    cualquier otro estado —o si el cierre no dejó snapshot— recalcula en vivo con
    `compute_results` y `frozen=False`.

    OPT-17: el snapshot `ECOEResult` no persiste `stations_counted` (no hay
    columna; sin migración), así que las filas congeladas no llevan esa clave —
    sólo el recálculo en vivo. Un evento `cerrado`/`archivado` **sin** snapshot
    cae al recálculo en vivo y por lo tanto ya sirve la fórmula nueva de OPT-17.
    """
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if ecoe_event is not None and str(ecoe_event.status) in FROZEN_RESULT_STATUSES:
        snapshots = db.scalars(
            select(ECOEResult)
            .where(ECOEResult.ecoe_event_id == ecoe_event_id)
            .order_by(ECOEResult.student_id.asc())
        ).all()
        if snapshots:
            students = {
                student.id: student
                for student in db.scalars(
                    select(Student).where(Student.ecoe_event_id == ecoe_event_id)
                ).all()
            }
            consolidated_at = max(
                (snap.updated_at for snap in snapshots if snap.updated_at is not None),
                default=None,
            )
            results = []
            for snap in snapshots:
                student = students.get(snap.student_id)
                results.append({
                    "student_id": snap.student_id,
                    "student_name": (
                        f"{student.name} {student.last_name}" if student else ""
                    ),
                    "ecoe_number": student.ecoe_number if student else None,
                    "total_score": round(snap.total_score, 2),
                    "max_score": round(snap.max_score, 2),
                    "percentage": round(snap.percentage, 2),
                    "equivalent_grade": round(snap.equivalent_grade, 2),
                })
            return results, True, consolidated_at
    return compute_results(db, ecoe_event_id), False, None


def persist_results(
    db: Session,
    ecoe_event_id: int,
    *,
    commit: bool = True,
    actor_email: str | None = None,
) -> list[dict]:
    results = compute_results(db, ecoe_event_id)
    db.query(ECOEResult).filter(ECOEResult.ecoe_event_id == ecoe_event_id).delete()
    for item in results:
        db.add(ECOEResult(
            ecoe_event_id=ecoe_event_id,
            student_id=item["student_id"],
            total_score=item["total_score"],
            max_score=item["max_score"],
            percentage=item["percentage"],
            equivalent_grade=item["equivalent_grade"],
        ))
    # OPT-16: congelar la nota por estación igual que `ECOEResult`
    # (delete-then-insert idempotente; respeta
    # `UniqueConstraint(ecoe_event_id, station_id, student_id)`). El
    # `AuditLog(action="consolidate_results")` de OPT-1 ya cubre la
    # consolidación completa; no se agrega otro registro.
    db.query(StationResult).filter(
        StationResult.ecoe_event_id == ecoe_event_id
    ).delete()
    for item in compute_station_results(db, ecoe_event_id):
        db.add(StationResult(
            ecoe_event_id=ecoe_event_id,
            student_id=item["student_id"],
            station_id=item["station_id"],
            obtained_score=item["obtained_score"],
            max_score=item["max_score"],
            percent_score=item["percent_score"],
        ))
    if actor_email:
        db.add(AuditLog(
            user_email=actor_email,
            action="consolidate_results",
            target_type="ECOEEvent",
            target_id=str(ecoe_event_id),
            payload={"student_count": len(results)},
        ))
    if commit:
        db.commit()
    return results


def build_traceability_report(
    db: Session,
    ecoe_event_id: int,
    consolidated_results: list[dict] | None = None,
) -> dict:
    students = db.scalars(
        select(Student).where(Student.ecoe_event_id == ecoe_event_id, Student.is_active.is_(True))
    ).all()
    stations = db.scalars(
        select(Station).where(Station.ecoe_event_id == ecoe_event_id)
        .order_by(Station.station_number.asc(), Station.id.asc())
    ).all()
    checkins = db.scalars(
        select(StationCheckIn).where(
            StationCheckIn.ecoe_event_id == ecoe_event_id,
            StationCheckIn.mode == SessionMode.ejecucion.value,
        )
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    ).all()
    # Trazabilidad y checklist de cierre son sobre la EJECUCIÓN REAL: los
    # registros de pilotaje no cuentan para completitud, faltantes ni el
    # consolidado (mismo criterio que `compute_results`). Un estudiante que
    # solo pilotó y faltó a la ejecución debe verse como "sin actividad".
    all_evaluator_rows = db.scalars(
        select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == ecoe_event_id,
            EvaluatorRecord.mode == SessionMode.ejecucion.value,
        )
        .order_by(EvaluatorRecord.created_at.desc(), EvaluatorRecord.id.desc())
    ).all()
    # OPT-20 F3 (D3): only a finalized record counts as a completed evaluation
    # and shows up in the activity log; a draft is tracked apart as pending
    # work to be finalized in the contingency window.
    evaluator_records = [row for row in all_evaluator_rows if not row.is_draft]
    evaluator_drafts = [row for row in all_evaluator_rows if row.is_draft]
    student_responses = db.scalars(
        select(StudentResponse).where(
            StudentResponse.ecoe_event_id == ecoe_event_id,
            StudentResponse.mode == SessionMode.ejecucion.value,
        )
        .order_by(StudentResponse.submitted_at.desc(), StudentResponse.id.desc())
    ).all()
    pilot_runs = db.scalars(
        select(PilotRun).where(PilotRun.ecoe_event_id == ecoe_event_id)
        .order_by(PilotRun.created_at.desc(), PilotRun.id.desc())
    ).all()
    evaluator_assignments = db.scalars(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.role_code == RoleCode.evaluador.value,
        )
    ).all()

    results = consolidated_results if consolidated_results is not None else compute_results(db, ecoe_event_id)
    results_by_student = {int(item["student_id"]): item for item in results}
    students_by_id = {student.id: student for student in students}
    stations_by_id = {station.id: station for station in stations}

    station_primary_evaluator: dict[int, str] = {}
    for assignment in evaluator_assignments:
        full_name = " ".join(part for part in [assignment.name, assignment.last_name] if part).strip()
        for station_id in assignment.station_ids or []:
            if station_id and station_id not in station_primary_evaluator:
                station_primary_evaluator[int(station_id)] = full_name or assignment.email

    # Expected counts are per CIRCUIT: in mirrored circuits each student only
    # visits their own circuit's stations, so counting every station of the
    # event would inflate "missing" metrics and completion would never close.
    def _circuit_key(value: str | None) -> str:
        return str(value or "").strip().lower()

    evaluator_required_by_circuit: dict[str, int] = {}
    student_form_required_by_circuit: dict[str, int] = {}
    for station in stations:
        key = _circuit_key(station.circuit_name)
        if station.requires_evaluator:
            evaluator_required_by_circuit[key] = evaluator_required_by_circuit.get(key, 0) + 1
        if station.requires_student_form:
            student_form_required_by_circuit[key] = student_form_required_by_circuit.get(key, 0) + 1
    total_evaluator_required = sum(evaluator_required_by_circuit.values())
    total_student_form_required = sum(student_form_required_by_circuit.values())
    station_circuit_keys = {_circuit_key(station.circuit_name) for station in stations}

    def _required_for_student(student: Student) -> tuple[int, int]:
        key = _circuit_key(student.circuit_name)
        if key not in station_circuit_keys:
            # Circuito sin correspondencia textual con las estaciones:
            # fallback conservador al total del evento.
            return total_evaluator_required, total_student_form_required
        return (
            evaluator_required_by_circuit.get(key, 0),
            student_form_required_by_circuit.get(key, 0),
        )

    expected_evaluations_total = 0
    expected_student_submissions_total = 0

    deferred_grading_station_ids = {
        station.id for station in stations if station.requires_deferred_grading
    }

    student_traceability: list[dict] = []
    for student in students:
        required_evaluator_station_count, required_student_form_station_count = (
            _required_for_student(student)
        )
        expected_evaluations_total += required_evaluator_station_count
        expected_student_submissions_total += required_student_form_station_count
        student_checkins = [item for item in checkins if item.student_id == student.id]
        student_evaluations = [item for item in evaluator_records if item.student_id == student.id]
        student_evaluator_drafts = [item for item in evaluator_drafts if item.student_id == student.id]
        student_form_responses = [item for item in student_responses if item.student_id == student.id]
        latest_checkin = student_checkins[0].confirmed_at if student_checkins else None
        latest_evaluation = student_evaluations[0].created_at if student_evaluations else None
        latest_student_response = student_form_responses[0].submitted_at if student_form_responses else None
        last_activity = max(
            [item for item in [latest_checkin, latest_evaluation, latest_student_response] if item],
            default=None,
        )
        has_expected_evaluations = len(student_evaluations) >= required_evaluator_station_count
        has_expected_student_responses = len(student_form_responses) >= required_student_form_station_count
        # Respuestas en estaciones de corrección diferida aún sin puntaje
        # definitivo: el estudiante no está "completo" hasta que se corrijan.
        pending_deferred_gradings = sum(
            1
            for item in student_form_responses
            if item.station_id in deferred_grading_station_ids
            and item.max_score is not None
            and item.score_obtained is None
        )
        pending_evaluator_drafts = len(student_evaluator_drafts)
        # OPT-20 F4 (D4): respuestas autoenviadas por el barrido sin contenido —
        # suman 0/max al consolidado como cualquiera, pero se marcan para que
        # coordinación distinga una omisión de una entrega real.
        blank_auto_submissions = sum(
            1
            for item in student_form_responses
            if item.submission_kind == "auto" and not item.answers
        )
        if (
            not student_checkins
            and not student_evaluations
            and not student_form_responses
            and not student_evaluator_drafts
        ):
            completion_status = "sin actividad"
        elif (
            has_expected_evaluations
            and has_expected_student_responses
            and pending_deferred_gradings == 0
            and pending_evaluator_drafts == 0
        ):
            completion_status = "completo"
        else:
            completion_status = "parcial"

        result_item = results_by_student.get(student.id, {})
        student_traceability.append({
            "id": student.id, "student_id": student.id,
            "ecoe_number": student.ecoe_number,
            "student_name": f"{student.name} {student.last_name}",
            "checkins_confirmed": len(student_checkins),
            "evaluator_submissions": len(student_evaluations),
            "student_submissions": len(student_form_responses),
            "missing_evaluations": max(0, required_evaluator_station_count - len(student_evaluations)),
            "missing_student_submissions": max(0, required_student_form_station_count - len(student_form_responses)),
            "pending_deferred_gradings": pending_deferred_gradings,
            "pending_evaluator_drafts": pending_evaluator_drafts,
            "blank_auto_submissions": blank_auto_submissions,
            "completion_status": completion_status,
            "last_checkin_at": latest_checkin.isoformat() if latest_checkin else None,
            "last_evaluation_at": latest_evaluation.isoformat() if latest_evaluation else None,
            "last_student_submission_at": latest_student_response.isoformat() if latest_student_response else None,
            "last_activity_at": last_activity.isoformat() if last_activity else None,
            "total_score": result_item.get("total_score", 0),
            "percentage": result_item.get("percentage", 0),
            "equivalent_grade": result_item.get("equivalent_grade", 0),
        })

    station_traceability: list[dict] = []
    for station in stations:
        station_checkins = [item for item in checkins if item.station_id == station.id]
        station_evaluations = [item for item in evaluator_records if item.station_id == station.id]
        station_evaluator_drafts = [item for item in evaluator_drafts if item.station_id == station.id]
        station_form_responses = [item for item in student_responses if item.station_id == station.id]
        station_blank_auto_submissions = sum(
            1
            for item in station_form_responses
            if item.submission_kind == "auto" and not item.answers
        )
        latest_station_activity = max(
            [item for item in [
                station_checkins[0].confirmed_at if station_checkins else None,
                station_evaluations[0].created_at if station_evaluations else None,
                station_form_responses[0].submitted_at if station_form_responses else None,
            ] if item],
            default=None,
        )
        if not station_checkins and not station_evaluations and not station_form_responses:
            station_status = "sin registros"
        elif station_evaluations or station_form_responses:
            station_status = "con evidencia"
        else:
            station_status = "con check-in"

        station_traceability.append({
            "id": station.id, "station_id": station.id,
            "station_number": station.station_number,
            "station_name": station.name,
            "circuit_name": station.circuit_name,
            "status": station_status,
            "assigned_evaluator": station_primary_evaluator.get(station.id, "Sin asignar"),
            "checkins_count": len(station_checkins),
            "evaluations_count": len(station_evaluations),
            "pending_evaluator_drafts": len(station_evaluator_drafts),
            "student_submissions_count": len(station_form_responses),
            "blank_auto_submissions": station_blank_auto_submissions,
            "last_activity_at": latest_station_activity.isoformat() if latest_station_activity else None,
        })

    activity_log: list[dict] = []
    for pilot_run in pilot_runs:
        activity_log.append({
            "timestamp": pilot_run.created_at.isoformat(),
            "type": "pilotaje", "label": pilot_run.name,
            "detail": f"Pilotaje {pilot_run.scope.replace('_', ' ')} registrado.",
            "actor": "Coordinación ECOE", "mode": "pilotaje",
        })
    for checkin in checkins:
        student = students_by_id.get(checkin.student_id)
        station = stations_by_id.get(checkin.station_id)
        if not student or not station:
            continue
        activity_log.append({
            "timestamp": checkin.confirmed_at.isoformat(), "type": "checkin",
            "label": "Ingreso confirmado",
            "detail": f"{student.ecoe_number} - {student.name} {student.last_name} en estación {station.station_number}: {station.name}.",
            "actor": checkin.evaluator_name, "mode": checkin.mode,
        })
    for record in evaluator_records:
        student = students_by_id.get(record.student_id)
        station = stations_by_id.get(record.station_id)
        if not student or not station:
            continue
        activity_log.append({
            "timestamp": record.created_at.isoformat(), "type": "evaluacion",
            "label": "Evaluación enviada",
            "detail": f"{student.ecoe_number} - {student.name} {student.last_name} evaluado en estación {station.station_number}: {station.name}.",
            "actor": record.evaluator_name, "mode": record.mode,
        })
    for draft in evaluator_drafts:
        student = students_by_id.get(draft.student_id)
        station = stations_by_id.get(draft.station_id)
        if not student or not station:
            continue
        activity_log.append({
            "timestamp": draft.updated_at.isoformat() if draft.updated_at else draft.created_at.isoformat(),
            "type": "evaluacion_borrador",
            "label": "Evaluación en borrador (sin finalizar)",
            "detail": (
                f"{student.ecoe_number} - {student.name} {student.last_name}: registro del evaluador "
                f"en estación {station.station_number}: {station.name} quedó como borrador; "
                "debe finalizarse por contingencia."
            ),
            "actor": draft.evaluator_name, "mode": draft.mode,
        })
    for response in student_responses:
        student = students_by_id.get(response.student_id)
        station = stations_by_id.get(response.station_id)
        if not student or not station:
            continue
        # OPT-20 F4 (D4): etiquetar el origen de la respuesta y si llegó vacía.
        kind = response.submission_kind or "manual"
        is_blank = not response.answers
        if kind == "auto" and is_blank:
            label = "Respuesta del estudiante (automática, sin respuesta)"
            verb = "no alcanzó a responder (autoenvío en blanco) en"
        elif kind == "auto":
            label = "Respuesta del estudiante (automática)"
            verb = "quedó autoenviada en"
        elif kind == "contingency":
            label = "Respuesta del estudiante (por contingencia)"
            verb = "fue registrada por contingencia en"
        else:
            label = "Respuesta del estudiante"
            verb = "respondió en"
        activity_log.append({
            "timestamp": response.submitted_at.isoformat(), "type": "respuesta_estudiante",
            "label": label,
            "detail": f"{student.ecoe_number} - {student.name} {student.last_name} {verb} estación {station.station_number}: {station.name}.",
            "actor": f"{student.name} {student.last_name}", "mode": response.mode,
            "submission_kind": kind,
            "answered": not is_blank,
        })
    activity_log.sort(key=lambda item: item["timestamp"], reverse=True)

    return {
        "summary": {
            "active_students": len(students),
            "stations": len(stations),
            "expected_evaluations": expected_evaluations_total,
            "expected_student_submissions": expected_student_submissions_total,
            "confirmed_checkins": len(checkins),
            "evaluator_submissions": len(evaluator_records),
            "pending_evaluator_drafts": len(evaluator_drafts),
            "student_submissions": len(student_responses),
            "blank_auto_submissions": sum(
                1
                for item in student_responses
                if item.submission_kind == "auto" and not item.answers
            ),
            "pilot_runs": len(pilot_runs),
        },
        "student_traceability": student_traceability,
        "station_traceability": station_traceability,
        "activity_log": activity_log[:25],
    }


_SUBMISSION_KIND_LABELS = {
    "manual": "Manual",
    "auto": "Automático",
    "contingency": "Contingencia",
    "draft_finalized": "Borrador finalizado",
}


def _submission_trace_rows(db: Session, ecoe_event_id: int) -> list[dict]:
    """Un indicador por respuesta de la ejecución real (OPT-20 F4, D4).

    Marca origen (`manual`/`auto`/`contingencia`) y si la respuesta llegó en
    blanco. Es metadato de trazabilidad, no de nota: se calcula en vivo aun
    con el consolidado congelado. El rediseño completo del export es OPT-19;
    aquí solo se agrega este indicador mínimo en una hoja aparte.
    """
    students = {
        s.id: s
        for s in db.scalars(select(Student).where(Student.ecoe_event_id == ecoe_event_id)).all()
    }
    stations = {
        s.id: s
        for s in db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()
    }
    responses = db.scalars(
        select(StudentResponse)
        .where(
            StudentResponse.ecoe_event_id == ecoe_event_id,
            StudentResponse.mode == SessionMode.ejecucion.value,
        )
        .order_by(StudentResponse.station_id.asc(), StudentResponse.id.asc())
    ).all()
    rows: list[dict] = []
    for response in responses:
        student = students.get(response.student_id)
        station = stations.get(response.station_id)
        kind = response.submission_kind or "manual"
        answered = bool(response.answers)
        rows.append({
            "ecoe_number": student.ecoe_number if student else None,
            "student_name": f"{student.name} {student.last_name}" if student else "",
            "station_number": station.station_number if station else None,
            "station_name": station.name if station else "",
            "origen": _SUBMISSION_KIND_LABELS.get(kind, kind),
            "en_blanco": "Sí" if (kind == "auto" and not answered) else "No",
            "score_obtained": response.score_obtained,
            "max_score": response.max_score,
            "by_contingency": response.by_contingency,
        })
    return rows


def _station_score_rows(db: Session, ecoe_event_id: int) -> list[dict]:
    """Hoja `resultados_por_estacion` (OPT-16), formato largo.

    Una fila por (estudiante, estación) con puntaje obtenido, máximo y %.
    Sigue el mismo patrón `frozen` que el consolidado: sirve el snapshot
    `StationResult` con el evento cerrado, recalcula en vivo si no. El rediseño
    completo del export (item-analysis, metadatos) es OPT-19, que absorbe esta
    hoja.
    """
    station_rows, _ = read_station_results(db, ecoe_event_id)
    students = {
        s.id: s
        for s in db.scalars(
            select(Student).where(Student.ecoe_event_id == ecoe_event_id)
        ).all()
    }
    stations = db.scalars(
        select(Station).where(Station.ecoe_event_id == ecoe_event_id)
        .order_by(Station.station_number.asc(), Station.id.asc())
    ).all()
    block = build_station_score_block(station_rows, list(stations), students)
    return [
        {
            "n_ecoe": row["ecoe_number"],
            "estudiante": row["student_name"],
            "estacion_numero": row["station_number"],
            "estacion": row["station_name"],
            "puntaje": row["obtained_score"],
            "maximo": row["max_score"],
            "porcentaje": row["percent_score"],
        }
        for row in block["students"]
    ]


def export_results_excel(db: Session, ecoe_event_id: int, *, persist: bool = False) -> bytes:
    if persist:
        data = persist_results(db, ecoe_event_id)
    else:
        data, _, _ = read_results(db, ecoe_event_id)
    df = pd.DataFrame(data)
    trace_df = pd.DataFrame(_submission_trace_rows(db, ecoe_event_id))
    station_df = pd.DataFrame(_station_score_rows(db, ecoe_event_id))
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="consolidado")
        station_df.to_excel(writer, index=False, sheet_name="resultados_por_estacion")
        trace_df.to_excel(writer, index=False, sheet_name="trazabilidad_envios")
    return buffer.getvalue()


def export_contingency_pdf(db: Session, ecoe_event_id: int, station_id: int | None = None) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle("Contingencia ECOE")
    text = pdf.beginText(40, 800)
    text.setFont("Helvetica-Bold", 14)
    text.textLine("Proyecto Tecnologico ECOE - Respaldo imprimible")
    text.setFont("Helvetica", 11)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    text.textLine(f"ECOE: {ecoe_event.name}")
    if station_id:
        station = db.get(Station, station_id)
        text.textLine(f"Estación: {station.station_number} - {station.name}")
        text.textLine(f"Instrucción estudiante: {station.pre_entry_instruction}")
        text.textLine(f"Instrucción evaluador: {station.evaluator_instruction}")
        text.textLine(f"Materiales: {station.materials}")
    else:
        stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()
        text.textLine("Resumen general de estaciones")
        for station in stations:
            text.textLine(f"{station.station_number}. {station.name} [{station.status}] {station.circuit_name}")
    pdf.drawText(text)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def store_contingency_export(db: Session, ecoe_event_id: int, export_type: str, content: bytes) -> str:
    settings = get_settings()
    output_dir = Path(settings.storage_path) / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{export_type}-{ecoe_event_id}.bin"
    path.write_bytes(content)
    db.add(ContingencyExport(
        ecoe_event_id=ecoe_event_id,
        export_type=export_type,
        file_path=str(path),
    ))
    db.commit()
    return str(path)
