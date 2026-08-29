"""OPT-19 · Export Excel enriquecido (multi-hoja) + limpieza del `persist` muerto.

Cubre:
- **Negativo P0**: `export_results_excel` es un GET y **no muta** — no consolida
  `ECOEResult` / `StationResult` ni deja `AuditLog(consolidate_results)`
  (blinda la eliminación del parámetro `persist`).
- Las 5 hojas esperadas existen y en orden: `metadatos`, `consolidado`,
  `por_estacion`, `item_analysis`, `trazabilidad_envios`.
- `metadatos`: curso, escuela, fecha, umbral, nº estudiantes, `frozen`,
  `consolidado_at`.
- `trazabilidad_envios`: una fila por registro con identidad de
  evaluador/corrector, timestamps, `mode`, `submission_kind`, `by_contingency`,
  `borrador`.
- `item_analysis`: una fila por criterio de pauta (`mode=ejecucion`).
- Evento cerrado → `consolidado` y `por_estacion` salen del snapshot, no del
  recálculo.
- Rol sin acceso al evento → 403.
- Evento vacío → xlsx válido con encabezados, sin excepción.
"""

from datetime import date, datetime, timezone
from io import BytesIO

import pandas as pd
import pytest
from sqlalchemy import func, select

from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    AuditLog,
    ECOEEvent,
    ECOEResult,
    EvaluatorRecord,
    Station,
    StationResult,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, InstrumentType, SessionMode
from app.services.results import export_results_excel
from app.services.validation import update_ecoe_status
from conftest import CORRECTOR, STUDENT, TestingSessionLocal, login

EXPECTED_SHEETS = ["metadatos", "consolidado", "por_estacion", "item_analysis", "trazabilidad_envios"]


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Fixtures de datos ────────────────────────────────────────────────


def _event(*, status: str = ECOEStatus.en_ejecucion.value, passing: float = 60.0) -> int:
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Export OPT-19",
            date=date(2026, 12, 15),
            course_name="Semiología II",
            school_name="Facultad de Medicina UChile",
            responsible_teacher="Dra. Ruiz",
            contact_email="ruiz@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=2,
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=3,
            total_groups=1,
            passing_reference_percent=passing,
            status=status,
        )
        db.add(event)
        db.flush()
        event_id = event.id
        db.commit()
        return event_id


def _tool(n_items: int, score_per_item: float = 2.0) -> tuple[int, list[int]]:
    with TestingSessionLocal() as db:
        tool = AssessmentTool(
            name="Pauta estructurada",
            tool_type=InstrumentType.checklist.value,
            max_score=n_items * score_per_item,
            free_observation=True,
        )
        db.add(tool)
        db.flush()
        item_ids: list[int] = []
        for idx in range(n_items):
            item = AssessmentItem(
                tool_id=tool.id,
                label=f"Criterio {idx + 1}",
                score_per_item=score_per_item,
                order_index=idx,
            )
            db.add(item)
            db.flush()
            item_ids.append(item.id)
        tool_id = tool.id
        db.commit()
        return tool_id, item_ids


def _station(
    event_id: int,
    number: int,
    max_score: float,
    *,
    tool_id: int | None = None,
    form: bool = False,
) -> int:
    with TestingSessionLocal() as db:
        station = Station(
            ecoe_event_id=event_id,
            station_number=number,
            name=f"Estación {number}",
            station_type="formulario_estudiante" if form else "evaluador",
            circuit_name="Circuito A",
            station_time_minutes=8,
            transition_time_minutes=2,
            expected_outcomes="R",
            student_activity="A",
            pre_entry_instruction="I",
            evaluator_instruction="E",
            requires_evaluator=not form,
            requires_student_form=form,
            max_score=max_score,
            assessment_tool_id=tool_id,
        )
        db.add(station)
        db.flush()
        station_id = station.id
        db.commit()
        return station_id


def _students(event_id: int, n: int) -> list[int]:
    ids: list[int] = []
    with TestingSessionLocal() as db:
        for idx in range(n):
            student = Student(
                ecoe_event_id=event_id,
                name=f"Alumno{idx}",
                last_name="Export",
                rut=f"5{event_id}{idx}00-1",
                email=f"ex{event_id}_{idx}@example.edu",
                ecoe_number=f"{idx + 1:03d}",
                group_name="G1",
                circuit_name="Circuito A",
                is_active=True,
            )
            db.add(student)
            db.flush()
            ids.append(student.id)
        db.commit()
    return ids


def _response(
    event_id: int,
    station_id: int,
    student_id: int,
    obtained: float | None,
    maximo: float,
    *,
    mode: str = SessionMode.ejecucion.value,
    kind: str = "manual",
    answers: dict | None = None,
    graded_by: str | None = None,
    by_contingency: bool = False,
    grading: dict | None = None,
) -> int:
    with TestingSessionLocal() as db:
        response = StudentResponse(
            ecoe_event_id=event_id,
            station_id=station_id,
            student_id=student_id,
            mode=mode,
            answers={"question_1": "A"} if answers is None else answers,
            score_obtained=obtained,
            max_score=maximo,
            submission_kind=kind,
            by_contingency=by_contingency,
            graded_by_email=graded_by,
            graded_at=_utcnow_naive() if graded_by else None,
            grading=grading if grading is not None else {
                "question_1": {"kind": "auto", "earned": obtained, "max": maximo, "answered": True}
            },
        )
        db.add(response)
        db.flush()
        response_id = response.id
        db.commit()
        return response_id


def _eval_record(
    event_id: int,
    station_id: int,
    student_id: int,
    item_scores: dict[int, float],
    max_total: float,
    *,
    is_draft: bool = False,
    by_contingency: bool = False,
    name: str = "Dr. Pérez",
) -> None:
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=event_id,
            station_id=station_id,
            student_id=student_id,
            evaluator_name=name,
            mode=SessionMode.ejecucion.value,
            score_obtained=sum(item_scores.values()),
            max_score=max_total,
            is_draft=is_draft,
            by_contingency=by_contingency,
            answers={"item_scores": {str(k): v for k, v in item_scores.items()}},
        ))
        db.commit()


def _close(event_id: int) -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        update_ecoe_status(db, event, ECOEStatus.cerrado.value, actor_email="admin@ecoe.cl")


def _sheets(event_id: int) -> dict[str, pd.DataFrame]:
    with TestingSessionLocal() as db:
        content = export_results_excel(db, event_id)
    return pd.read_excel(BytesIO(content), sheet_name=None)


# ── Negativo P0: el GET no muta ──────────────────────────────────────


def test_export_excel_does_not_mutate():
    """Llamar el export 2 veces sobre un evento NO cerrado: no crea snapshot
    `ECOEResult` / `StationResult` ni deja `AuditLog(consolidate_results)`.
    Blinda que se eliminó el parámetro `persist` (una escritura en un GET)."""
    event_id = _event()
    tool_id, item_ids = _tool(3)
    s1 = _station(event_id, 1, 6.0, tool_id=tool_id)
    s2 = _station(event_id, 2, 5.0, form=True)
    students = _students(event_id, 3)
    for sid in students:
        _eval_record(event_id, s1, sid, {item_ids[0]: 2, item_ids[1]: 2, item_ids[2]: 0}, 6.0)
        _response(event_id, s2, sid, 3.0, 5.0)

    with TestingSessionLocal() as db:
        export_results_excel(db, event_id)
        export_results_excel(db, event_id)

    with TestingSessionLocal() as db:
        assert db.scalar(
            select(func.count(ECOEResult.id)).where(ECOEResult.ecoe_event_id == event_id)
        ) == 0
        assert db.scalar(
            select(func.count(StationResult.id)).where(StationResult.ecoe_event_id == event_id)
        ) == 0
        assert db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "consolidate_results",
                AuditLog.target_id == str(event_id),
            )
        ) == 0
        # El evento sigue en ejecución, no fue cerrado por el export.
        assert str(db.get(ECOEEvent, event_id).status) == ECOEStatus.en_ejecucion.value


def test_export_excel_signature_has_no_persist_param():
    import inspect

    assert "persist" not in inspect.signature(export_results_excel).parameters


# ── Hojas y encabezados ─────────────────────────────────────────────


def test_export_has_all_sheets_in_order():
    event_id = _event()
    _station(event_id, 1, 5.0, form=True)
    students = _students(event_id, 2)
    for sid in students:
        _response(event_id, _station_id_for(event_id), sid, 3.0, 5.0)
    sheets = _sheets(event_id)
    assert list(sheets.keys()) == EXPECTED_SHEETS


def _station_id_for(event_id: int) -> int:
    with TestingSessionLocal() as db:
        return db.scalar(
            select(Station.id).where(Station.ecoe_event_id == event_id).order_by(Station.id)
        )


def test_export_metadatos_sheet():
    event_id = _event(passing=55.0)
    _station(event_id, 1, 5.0, form=True)
    sid = _students(event_id, 3)[0]
    _response(event_id, _station_id_for(event_id), sid, 4.0, 5.0)

    meta = _sheets(event_id)["metadatos"]
    assert list(meta.columns) == ["campo", "valor"]
    kv = dict(zip(meta["campo"], meta["valor"]))
    assert kv["Curso"] == "Semiología II"
    assert kv["Escuela / institución"] == "Facultad de Medicina UChile"
    assert str(kv["Fecha"]).startswith("2026-12-15")
    assert float(kv["Porcentaje de referencia de aprobación (nota 4,0)"]) == pytest.approx(55.0)
    assert int(kv["Estudiantes activos"]) == 3
    assert int(kv["Estaciones"]) == 1
    assert kv["Resultados congelados (snapshot del acta)"] == "No"


def test_export_metadatos_frozen_flag_after_close():
    event_id = _event()
    s1 = _station(event_id, 1, 5.0, form=True)
    sid = _students(event_id, 1)[0]
    _response(event_id, s1, sid, 4.0, 5.0)
    _close(event_id)

    meta = _sheets(event_id)["metadatos"]
    kv = dict(zip(meta["campo"], meta["valor"]))
    assert kv["Resultados congelados (snapshot del acta)"] == "Sí"
    assert str(kv["Consolidado el"]) != "nan" and kv["Consolidado el"]
    assert kv["Estado"] == ECOEStatus.cerrado.value


def test_export_trazabilidad_has_identity_and_metadata_columns():
    event_id = _event()
    tool_id, item_ids = _tool(2)
    s_eval = _station(event_id, 1, 4.0, tool_id=tool_id)
    s_form = _station(event_id, 2, 5.0, form=True)
    st_a, st_b = _students(event_id, 2)

    _eval_record(event_id, s_eval, st_a, {item_ids[0]: 2, item_ids[1]: 1}, 4.0, name="Dra. Soto")
    _eval_record(
        event_id, s_eval, st_b, {item_ids[0]: 1, item_ids[1]: 0}, 4.0,
        is_draft=True, name="Dra. Soto",
    )
    _response(event_id, s_form, st_a, 3.0, 5.0, graded_by="corrector@ecoe.cl")
    _response(
        event_id, s_form, st_b, 5.0, 5.0, kind="contingency",
        by_contingency=True, graded_by="auto",
    )

    trace = _sheets(event_id)["trazabilidad_envios"]
    for column in (
        "tipo_registro", "mode", "submission_kind", "by_contingency", "borrador",
        "evaluador", "corrector", "enviado_at", "corregido_at", "actualizado_at",
        "score_obtained", "max_score", "porcentaje",
    ):
        assert column in trace.columns, column

    assert set(trace["tipo_registro"]) == {"evaluador", "formulario"}

    evaluador_rows = trace[trace["tipo_registro"] == "evaluador"]
    assert set(evaluador_rows["evaluador"]) == {"Dra. Soto"}
    assert set(evaluador_rows["borrador"]) == {"Sí", "No"}

    formulario_rows = trace[trace["tipo_registro"] == "formulario"]
    assert "corrector@ecoe.cl" in set(formulario_rows["corrector"])
    assert "auto" in set(formulario_rows["corrector"])
    contingency_row = formulario_rows[formulario_rows["submission_kind"] == "contingency"].iloc[0]
    assert bool(contingency_row["by_contingency"]) is True


def test_export_trazabilidad_excludes_pilotaje():
    event_id = _event()
    s1 = _station(event_id, 1, 5.0, form=True)
    sid = _students(event_id, 1)[0]
    _response(event_id, s1, sid, 4.0, 5.0, mode=SessionMode.pilotaje.value)

    trace = _sheets(event_id)["trazabilidad_envios"]
    assert trace.empty or "ejecucion" in set(trace["mode"])
    assert "pilotaje" not in set(trace.get("mode", []))


def test_export_item_analysis_sheet():
    event_id = _event()
    tool_id, item_ids = _tool(3, score_per_item=2.0)
    s1 = _station(event_id, 1, 6.0, tool_id=tool_id)
    students = _students(event_id, 4)
    plans = [
        {item_ids[0]: 2, item_ids[1]: 2, item_ids[2]: 2},
        {item_ids[0]: 2, item_ids[1]: 2, item_ids[2]: 0},
        {item_ids[0]: 2, item_ids[1]: 0, item_ids[2]: 0},
        {item_ids[0]: 0, item_ids[1]: 0, item_ids[2]: 0},
    ]
    for sid, plan in zip(students, plans):
        _eval_record(event_id, s1, sid, plan, 6.0)

    item_df = _sheets(event_id)["item_analysis"]
    for column in ("estacion_numero", "estacion", "criterio", "n", "dificultad", "punto_biserial", "maximo", "fuera_de_umbral"):
        assert column in item_df.columns, column
    assert len(item_df) == 3
    assert set(item_df["n"]) == {4}
    # Criterio 1: media 1.5/2 = 0.75 de dificultad.
    crit1 = item_df[item_df["criterio"] == "Criterio 1"].iloc[0]
    assert float(crit1["dificultad"]) == pytest.approx(0.75, abs=1e-3)


def test_export_item_analysis_empty_without_structured_grading():
    event_id = _event()
    s1 = _station(event_id, 1, 5.0, form=True)  # sin assessment_tool ni grading puntuable
    sid = _students(event_id, 1)[0]
    _response(event_id, s1, sid, 4.0, 5.0, answers={"question_1": "A"}, grading={})

    item_df = _sheets(event_id)["item_analysis"]
    assert list(item_df.columns) == [
        "estacion_numero", "estacion", "criterio", "n", "dificultad", "punto_biserial", "maximo", "fuera_de_umbral",
    ]
    assert item_df.empty


# ── Frozen: consolidado y por_estacion desde el snapshot ─────────────


def test_export_frozen_event_uses_snapshot():
    event_id = _event()
    s1 = _station(event_id, 1, 5.0, form=True)
    sid = _students(event_id, 1)[0]
    response_id = _response(event_id, s1, sid, 5.0, 5.0)
    _close(event_id)

    # Mutación a mano del puntaje real tras consolidar.
    with TestingSessionLocal() as db:
        response = db.get(StudentResponse, response_id)
        response.score_obtained = 0
        db.add(response)
        db.commit()

    sheets = _sheets(event_id)
    consolidado = sheets["consolidado"]
    assert consolidado[consolidado["student_id"] == sid]["total_score"].iloc[0] == 5
    por_estacion = sheets["por_estacion"]
    assert por_estacion["puntaje"].iloc[0] == 5


# ── Permisos ────────────────────────────────────────────────────────


def test_export_excel_requires_event_access(client):
    event_id = _event()
    _station(event_id, 1, 5.0, form=True)
    for creds in (STUDENT, CORRECTOR):
        login(client, creds)
        denied = client.get(f"/api/results/{event_id}/export/excel")
        assert denied.status_code == 403, f"{creds[0]}: {denied.status_code}"


# ── Robustez ────────────────────────────────────────────────────────


def test_export_empty_event_no_crash(auth_client):
    event_id = _event()
    export = auth_client.get(f"/api/results/{event_id}/export/excel")
    assert export.status_code == 200
    sheets = pd.read_excel(BytesIO(export.content), sheet_name=None)
    assert list(sheets.keys()) == EXPECTED_SHEETS
    assert list(sheets["trazabilidad_envios"].columns)[:3] == ["n_ecoe", "estudiante", "estacion_numero"]
    assert list(sheets["metadatos"].columns) == ["campo", "valor"]
