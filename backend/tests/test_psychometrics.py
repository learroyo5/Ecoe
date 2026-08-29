"""OPT-18 · Analítica psicométrica (ejecución + pilotaje + item analysis).

Cubre:
- Fórmulas con valores calculados a mano: media/DE por estación, α de Cronbach
  (listwise), discriminación estación-total corregida, dificultad y
  punto-biserial por criterio.
- Casos degenerados (n < 2, < 2 estaciones, varianza 0) → `None`, nunca 500.
- Endpoint `GET /api/analytics/{id}/psychometrics`: auth (mismos roles que
  `/results`), validación de `mode`, aislamiento pilotaje/ejecución.
- Item analysis omite estaciones sin pauta estructurada sin romper.
- F3: transición a `pilotaje_validado` con métricas malas → 200 + `AuditLog`.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    AuditLog,
    ECOEEvent,
    EvaluatorRecord,
    Station,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.psychometrics import (
    build_psychometrics_block,
    item_analysis,
    reliability,
    station_stats,
)
from app.services.validation import update_ecoe_status
from conftest import ADMIN, COORDINATOR, CORRECTOR, EVALUATOR, STUDENT, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Fixtures de datos ────────────────────────────────────────────────


def _make_event(*, status: str = ECOEStatus.en_ejecucion.value, passing: float = 60.0) -> int:
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Psicometría OPT-18",
            date=date(2026, 12, 12),
            course_name="Curso",
            school_name="Escuela",
            responsible_teacher="Docente",
            contact_email="docente@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=3,
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=5,
            total_groups=1,
            passing_reference_percent=passing,
            status=status,
        )
        db.add(event)
        db.flush()
        event_id = event.id
        db.commit()
        return event_id


def _add_station(event_id: int, number: int, max_score: float, *, tool_id: int | None = None) -> int:
    with TestingSessionLocal() as db:
        station = Station(
            ecoe_event_id=event_id,
            station_number=number,
            name=f"Estación {number}",
            station_type="evaluador",
            circuit_name="Circuito A",
            station_time_minutes=8,
            transition_time_minutes=2,
            expected_outcomes="R",
            student_activity="A",
            pre_entry_instruction="I",
            evaluator_instruction="E",
            requires_evaluator=True,
            max_score=max_score,
            assessment_tool_id=tool_id,
        )
        db.add(station)
        db.flush()
        station_id = station.id
        db.commit()
        return station_id


def _add_students(event_id: int, n: int) -> list[int]:
    ids: list[int] = []
    with TestingSessionLocal() as db:
        for idx in range(n):
            student = Student(
                ecoe_event_id=event_id,
                name=f"Alumno{idx}",
                last_name="Psico",
                rut=f"8{event_id}{idx}00-1",
                email=f"ps{event_id}_{idx}@example.edu",
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


def _add_eval_record(
    event_id: int,
    station_id: int,
    student_id: int,
    obtained: float,
    max_score: float,
    *,
    mode: str = SessionMode.ejecucion.value,
    is_draft: bool = False,
    answers: dict | None = None,
) -> None:
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=event_id,
            station_id=station_id,
            student_id=student_id,
            evaluator_name="Eval",
            mode=mode,
            score_obtained=obtained,
            max_score=max_score,
            is_draft=is_draft,
            answers=answers or {},
        ))
        db.commit()


def _fake_rows(matrix: list[list[float]], station_ids: list[int], student_ids: list[int]) -> list[dict]:
    """Convierte una matriz de % en las filas que consumen station_stats/reliability."""
    rows: list[dict] = []
    for si, student_id in enumerate(student_ids):
        for ji, station_id in enumerate(station_ids):
            pct = matrix[si][ji]
            if pct is None:
                continue
            rows.append({
                "student_id": student_id,
                "station_id": station_id,
                "obtained_score": pct,
                "max_score": 100.0,
                "percent_score": pct,
            })
    return rows


class _FakeStation:
    def __init__(self, id_: int, number: int):
        self.id = id_
        self.station_number = number
        self.name = f"E{number}"
        self.circuit_name = "Circuito A"


# ── Fórmulas: valores a mano ─────────────────────────────────────────


def test_station_stats_mean_sd_n():
    stations = [_FakeStation(1, 1)]
    rows = _fake_rows([[80.0], [50.0], [90.0]], [1], [10, 11, 12])
    stats = station_stats(rows, stations, 60.0)[0]
    assert stats["n"] == 3
    assert stats["mean_percent"] == pytest.approx(73.3333, abs=1e-3)
    assert stats["sd_percent"] == pytest.approx(20.8167, abs=1e-3)  # stdev muestral


def test_station_stats_sd_none_with_single_observation():
    stations = [_FakeStation(1, 1)]
    rows = _fake_rows([[80.0]], [1], [10])
    stats = station_stats(rows, stations, 60.0)[0]
    assert stats["n"] == 1
    assert stats["sd_percent"] is None
    assert stats["mean_percent"] == 80.0


def test_cronbach_alpha_known_value():
    """Matriz 5×3 fija → α = 0.898 (calculado a mano).

    var_items (poblacional) = 200 + 114 + 410 = 724
    var_total (de las sumas por fila) = 1804
    α = 3/2 · (1 − 724/1804) = 0.898004…
    """
    station_ids = [1, 2, 3]
    student_ids = [10, 11, 12, 13, 14]
    matrix = [
        [80.0, 70.0, 90.0],
        [50.0, 60.0, 40.0],
        [90.0, 85.0, 95.0],
        [60.0, 55.0, 65.0],
        [70.0, 75.0, 60.0],
    ]
    rows = _fake_rows(matrix, station_ids, student_ids)
    stations = [_FakeStation(1, 1), _FakeStation(2, 2), _FakeStation(3, 3)]
    block = reliability(rows, stations)
    assert block["n_complete"] == 5
    assert block["n_total"] == 5
    assert block["k_stations"] == 3
    assert block["cronbach_alpha"] == pytest.approx(0.898, abs=0.001)


def test_station_discrimination_corrected():
    """Estación 1 vs. total-menos-estación-1 sobre la misma matriz 5×3.

    r = 2000 / sqrt(1000 · 4020) = 0.99751…
    """
    station_ids = [1, 2, 3]
    student_ids = [10, 11, 12, 13, 14]
    matrix = [
        [80.0, 70.0, 90.0],
        [50.0, 60.0, 40.0],
        [90.0, 85.0, 95.0],
        [60.0, 55.0, 65.0],
        [70.0, 75.0, 60.0],
    ]
    rows = _fake_rows(matrix, station_ids, student_ids)
    stations = [_FakeStation(1, 1), _FakeStation(2, 2), _FakeStation(3, 3)]
    disc = {d["station_id"]: d["r"] for d in reliability(rows, stations)["station_discrimination"]}
    assert disc[1] == pytest.approx(0.9975, abs=0.001)
    assert disc[2] is not None and disc[3] is not None


def test_cronbach_listwise_drops_incomplete_students():
    """Un alumno sin % en todas las estaciones no entra al cálculo listwise."""
    station_ids = [1, 2, 3]
    student_ids = [10, 11, 12, 13, 14, 15]
    matrix = [
        [80.0, 70.0, 90.0],
        [50.0, 60.0, 40.0],
        [90.0, 85.0, 95.0],
        [60.0, 55.0, 65.0],
        [70.0, 75.0, 60.0],
        [65.0, None, 55.0],  # incompleto → fuera
    ]
    rows = _fake_rows(matrix, station_ids, student_ids)
    stations = [_FakeStation(1, 1), _FakeStation(2, 2), _FakeStation(3, 3)]
    block = reliability(rows, stations)
    assert block["n_total"] == 6
    assert block["n_complete"] == 5
    assert block["cronbach_alpha"] == pytest.approx(0.898, abs=0.001)


def test_cronbach_none_with_fewer_than_two_stations():
    rows = _fake_rows([[80.0], [50.0], [90.0]], [1], [10, 11, 12])
    block = reliability(rows, [_FakeStation(1, 1)])
    assert block["k_stations"] == 1
    assert block["cronbach_alpha"] is None
    assert block["station_discrimination"][0]["r"] is None


def test_reliability_none_on_insufficient_data():
    rows = _fake_rows([[80.0, 70.0]], [1, 2], [10])  # 1 alumno
    block = reliability(rows, [_FakeStation(1, 1), _FakeStation(2, 2)])
    assert block["n_complete"] == 1
    assert block["cronbach_alpha"] is None
    assert all(d["r"] is None for d in block["station_discrimination"])


# ── Item analysis (pauta con evaluador) ──────────────────────────────


def _tool_with_items(scores: list[float]) -> tuple[int, list[int]]:
    with TestingSessionLocal() as db:
        tool = AssessmentTool(
            name="Pauta", tool_type="lista_cotejo", max_score=sum(scores), free_observation=True
        )
        db.add(tool)
        db.flush()
        item_ids = []
        for idx, score in enumerate(scores):
            item = AssessmentItem(
                tool_id=tool.id, label=f"Criterio {idx + 1}", score_per_item=score, order_index=idx
            )
            db.add(item)
            db.flush()
            item_ids.append(item.id)
        db.commit()
        return tool.id, item_ids


def test_item_difficulty_and_point_biserial():
    """Pauta de 3 criterios (máx 2 c/u), 4 alumnos, item_scores a mano.

    A:{2,2,2}=6  B:{2,2,0}=4  C:{0,0,0}=0  D:{0,2,0}=2
    dificultad  i1 = mean(2,2,0,0)/2 = 0.5   i2 = 1.5/2 = 0.75   i3 = 0.5/2 = 0.25
    r_pb(i1)    = pearson([2,2,0,0],[4,2,0,2]) = 4/sqrt(4·8) = 0.7071
    """
    event_id = _make_event()
    tool_id, item_ids = _tool_with_items([2, 2, 2])
    station_id = _add_station(event_id, 1, 6, tool_id=tool_id)
    students = _add_students(event_id, 4)
    plans = [
        {item_ids[0]: 2, item_ids[1]: 2, item_ids[2]: 2},
        {item_ids[0]: 2, item_ids[1]: 2, item_ids[2]: 0},
        {item_ids[0]: 0, item_ids[1]: 0, item_ids[2]: 0},
        {item_ids[0]: 0, item_ids[1]: 2, item_ids[2]: 0},
    ]
    for student_id, plan in zip(students, plans):
        _add_eval_record(
            event_id, station_id, student_id, sum(plan.values()), 6,
            answers={"item_scores": {str(k): v for k, v in plan.items()}},
        )

    with TestingSessionLocal() as db:
        analysis = {a["criterion_key"]: a for a in item_analysis(db, event_id, SessionMode.ejecucion.value)}

    assert analysis[str(item_ids[0])]["difficulty"] == pytest.approx(0.5, abs=1e-4)
    assert analysis[str(item_ids[1])]["difficulty"] == pytest.approx(0.75, abs=1e-4)
    assert analysis[str(item_ids[2])]["difficulty"] == pytest.approx(0.25, abs=1e-4)
    assert analysis[str(item_ids[0])]["point_biserial"] == pytest.approx(0.7071, abs=1e-3)
    assert analysis[str(item_ids[0])]["n"] == 4


def test_point_biserial_none_on_zero_variance_item():
    """Criterio que todos logran al máximo → r_pb = None, sin división por cero."""
    event_id = _make_event()
    tool_id, item_ids = _tool_with_items([2, 2])
    station_id = _add_station(event_id, 1, 4, tool_id=tool_id)
    students = _add_students(event_id, 3)
    for student_id in students:
        _add_eval_record(
            event_id, station_id, student_id, 2, 4,
            answers={"item_scores": {str(item_ids[0]): 2, str(item_ids[1]): 0}},
        )
    with TestingSessionLocal() as db:
        analysis = {a["criterion_key"]: a for a in item_analysis(db, event_id, SessionMode.ejecucion.value)}
    assert analysis[str(item_ids[0])]["difficulty"] == pytest.approx(1.0)
    assert analysis[str(item_ids[0])]["point_biserial"] is None


def test_item_analysis_resolves_order_index_keys():
    """`item_scores` guardado por `order_index` en vez de `id` también se resuelve."""
    event_id = _make_event()
    tool_id, item_ids = _tool_with_items([3, 3])
    station_id = _add_station(event_id, 1, 6, tool_id=tool_id)
    students = _add_students(event_id, 3)
    for student_id, (a, b) in zip(students, [(3, 3), (3, 0), (0, 0)]):
        _add_eval_record(
            event_id, station_id, student_id, a + b, 6,
            answers={"item_scores": {"0": a, "1": b}},  # claves = order_index
        )
    with TestingSessionLocal() as db:
        analysis = {a["criterion_key"]: a for a in item_analysis(db, event_id, SessionMode.ejecucion.value)}
    assert analysis[str(item_ids[0])]["n"] == 3
    assert analysis[str(item_ids[0])]["difficulty"] == pytest.approx(2.0 / 3.0, abs=1e-3)


def test_item_analysis_student_form_station():
    """Estación con formulario puntuable → dificultad por `question_<n>`."""
    login_client = None  # marcador: usamos submit vía API abajo
    event_id = _make_event()
    with TestingSessionLocal() as db:
        station = Station(
            ecoe_event_id=event_id,
            station_number=1,
            name="Formulario",
            station_type="formulario_estudiante",
            circuit_name="Circuito A",
            station_time_minutes=8,
            transition_time_minutes=2,
            expected_outcomes="R",
            student_activity="A",
            pre_entry_instruction="I",
            evaluator_instruction="",
            requires_evaluator=False,
            requires_student_form=True,
            max_score=10,
            student_form_definition={
                "questions": [
                    {"type": "single_choice", "label": "Q1", "options": ["A", "B"],
                     "points": 10, "correct_option": "A"},
                ]
            },
        )
        db.add(station)
        db.flush()
        station_id = station.id
        students = []
        for idx in range(3):
            student = Student(
                ecoe_event_id=event_id, name=f"F{idx}", last_name="Form",
                rut=f"5{event_id}{idx}0-1", email=f"f{event_id}_{idx}@e.edu",
                ecoe_number=f"{idx + 1:03d}", group_name="G1", circuit_name="Circuito A",
                is_active=True,
            )
            db.add(student)
            db.flush()
            students.append(student.id)
        # Respuestas puntuadas directamente (auto-grading resuelto).
        for student_id, earned in zip(students, [10.0, 10.0, 0.0]):
            db.add(StudentResponse(
                ecoe_event_id=event_id, station_id=station_id, student_id=student_id,
                mode=SessionMode.ejecucion.value, answers={"question_1": "A"},
                score_obtained=earned, max_score=10.0,
                grading={"question_1": {"kind": "auto", "earned": earned, "max": 10.0, "answered": True}},
            ))
        db.commit()

    with TestingSessionLocal() as db:
        analysis = item_analysis(db, event_id, SessionMode.ejecucion.value)
    q1 = next(a for a in analysis if a["criterion_key"] == "question_1")
    assert q1["n"] == 3
    assert q1["difficulty"] == pytest.approx(2.0 / 3.0, abs=1e-3)


def test_item_analysis_skips_stations_without_structured_rubric():
    """Estación sin pauta ni formulario puntuable no rompe ni aparece."""
    event_id = _make_event()
    station_id = _add_station(event_id, 1, 10)  # requires_evaluator, sin tool
    students = _add_students(event_id, 3)
    for student_id, score in zip(students, [8, 5, 2]):
        _add_eval_record(event_id, station_id, student_id, score, 10)
    with TestingSessionLocal() as db:
        analysis = item_analysis(db, event_id, SessionMode.ejecucion.value)
    assert analysis == []
    # El bloque completo igual se construye sin excepción.
    with TestingSessionLocal() as db:
        block = build_psychometrics_block(db, event_id, SessionMode.ejecucion.value)
    assert block["item_analysis"] == []
    assert block["station_stats"][0]["n"] == 3


# ── Endpoint: auth, mode, aislamiento ────────────────────────────────


def test_analytics_requires_event_access(client):
    """Mismos roles que `/results`: admin/coordinador 200; evaluador/estudiante/
    corrector 403 (evento demo 1, donde esos roles SÍ están asignados)."""
    for creds, expected in ((ADMIN, 200), (COORDINATOR, 200), (EVALUATOR, 403),
                            (STUDENT, 403), (CORRECTOR, 403)):
        login(client, creds)
        resp = client.get("/api/analytics/1/psychometrics")
        assert resp.status_code == expected, f"{creds[0]}: {resp.status_code} {resp.text}"


def test_analytics_foreign_event_forbidden(client):
    """Un evento sobre el que el usuario no tiene ningún rol → 403."""
    event_id = _make_event()
    login(client, EVALUATOR)
    resp = client.get(f"/api/analytics/{event_id}/psychometrics")
    assert resp.status_code == 403


def test_analytics_mode_param_rejects_garbage(auth_client):
    resp = auth_client.get("/api/analytics/1/psychometrics?mode=foo")
    assert resp.status_code == 422


def test_analytics_missing_event_404(auth_client):
    resp = auth_client.get("/api/analytics/999999/psychometrics")
    assert resp.status_code == 404


def test_psychometrics_over_pilotaje_mode(auth_client):
    """`mode=pilotaje` ve solo registros de pilotaje; `mode=ejecucion` los de
    ejecución. No se mezclan."""
    event_id = _make_event()
    s1 = _add_station(event_id, 1, 10)
    s2 = _add_station(event_id, 2, 10)
    students = _add_students(event_id, 3)
    # Ejecución: todos 100 % en s1.
    for student_id in students:
        _add_eval_record(event_id, s1, student_id, 10, 10, mode=SessionMode.ejecucion.value)
    # Pilotaje: todos 20 % en s1.
    for student_id in students:
        _add_eval_record(event_id, s1, student_id, 2, 10, mode=SessionMode.pilotaje.value)

    exec_block = auth_client.get(f"/api/analytics/{event_id}/psychometrics?mode=ejecucion").json()
    pilot_block = auth_client.get(f"/api/analytics/{event_id}/psychometrics?mode=pilotaje").json()

    exec_s1 = next(s for s in exec_block["station_stats"] if s["station_id"] == s1)
    pilot_s1 = next(s for s in pilot_block["station_stats"] if s["station_id"] == s1)
    assert exec_s1["mean_percent"] == pytest.approx(100.0)
    assert pilot_s1["mean_percent"] == pytest.approx(20.0)
    assert exec_block["mode"] == "ejecucion"
    assert pilot_block["mode"] == "pilotaje"


def test_psychometrics_excludes_evaluator_drafts(auth_client):
    event_id = _make_event()
    s1 = _add_station(event_id, 1, 10)
    students = _add_students(event_id, 2)
    _add_eval_record(event_id, s1, students[0], 9, 10)
    _add_eval_record(event_id, s1, students[1], 1, 10, is_draft=True)  # no cuenta
    block = auth_client.get(f"/api/analytics/{event_id}/psychometrics").json()
    s1_stats = next(s for s in block["station_stats"] if s["station_id"] == s1)
    assert s1_stats["n"] == 1
    assert s1_stats["mean_percent"] == pytest.approx(90.0)


def test_psychometrics_insufficient_data_no_500(auth_client):
    """1 estudiante / 1 estación → α, DE, discriminación = None; HTTP 200."""
    event_id = _make_event()
    s1 = _add_station(event_id, 1, 10)
    students = _add_students(event_id, 1)
    _add_eval_record(event_id, s1, students[0], 7, 10)
    resp = auth_client.get(f"/api/analytics/{event_id}/psychometrics")
    assert resp.status_code == 200
    block = resp.json()
    assert block["reliability"]["cronbach_alpha"] is None
    assert block["station_stats"][0]["sd_percent"] is None
    assert all(d["r"] is None for d in block["reliability"]["station_discrimination"])


def test_psychometrics_empty_event_no_500(auth_client):
    event_id = _make_event()
    resp = auth_client.get(f"/api/analytics/{event_id}/psychometrics")
    assert resp.status_code == 200
    block = resp.json()
    assert block["station_stats"] == []
    assert block["reliability"]["cronbach_alpha"] is None
    assert block["item_analysis"] == []
    assert block["warnings"] == []


def test_psychometrics_frozen_event_uses_snapshot(auth_client):
    """Evento cerrado: mutar un puntaje a mano no mueve las métricas (snapshot)."""
    from app.services.results import persist_results

    event_id = _make_event(status=ECOEStatus.en_ejecucion.value)
    s1 = _add_station(event_id, 1, 10)
    s2 = _add_station(event_id, 2, 10)
    students = _add_students(event_id, 3)
    for student_id in students:
        _add_eval_record(event_id, s1, student_id, 10, 10)
        _add_eval_record(event_id, s2, student_id, 8, 10)

    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        update_ecoe_status(db, event, ECOEStatus.cerrado.value, actor_email="admin@ecoe.cl")

    # Mutación posterior al cierre.
    with TestingSessionLocal() as db:
        rec = db.scalars(
            select(EvaluatorRecord).where(
                EvaluatorRecord.ecoe_event_id == event_id,
                EvaluatorRecord.station_id == s1,
            )
        ).first()
        rec.score_obtained = 0
        db.add(rec)
        db.commit()

    block = auth_client.get(f"/api/analytics/{event_id}/psychometrics?mode=ejecucion").json()
    assert block["frozen"] is True
    s1_stats = next(s for s in block["station_stats"] if s["station_id"] == s1)
    assert s1_stats["mean_percent"] == pytest.approx(100.0)  # snapshot, no el 0


# ── F3 · pilotaje_validado: advierte, no bloquea ─────────────────────


def _pilot_ready_event() -> int:
    """Evento en_pilotaje que cumple `can_publish` salvo la psicometría."""
    login_client = None
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Pilotaje F3",
            date=date(2026, 12, 20),
            course_name="Curso",
            school_name="Escuela",
            responsible_teacher="Docente",
            contact_email="docente@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=2,
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=4,
            total_groups=1,
            passing_reference_percent=60,
            status=ECOEStatus.en_pilotaje.value,
        )
        db.add(event)
        db.flush()
        event_id = event.id
        for number in (1, 2):
            db.add(Station(
                ecoe_event_id=event_id, station_number=number, name=f"E{number}",
                station_type="evaluador", circuit_name="Circuito A",
                station_time_minutes=8, transition_time_minutes=2,
                expected_outcomes="R", student_activity="A", pre_entry_instruction="I",
                evaluator_instruction="E", requires_evaluator=False, max_score=10,
            ))
        students = []
        for idx in range(4):
            s = Student(
                ecoe_event_id=event_id, name=f"P{idx}", last_name="F3",
                rut=f"3{event_id}{idx}0-1", email=f"p3{event_id}_{idx}@e.edu",
                ecoe_number=f"{idx + 1:03d}", group_name="G1", circuit_name="Circuito A",
                is_active=True,
            )
            db.add(s)
            db.flush()
            students.append(s.id)
        db.commit()

    stations = _station_ids(event_id)
    # Pilotaje con estaciones anticorrelacionadas: α negativa (< 0.6) y
    # discriminación negativa, pero var_total ≠ 0 (α definida, no None).
    plans = {
        stations[0]: [10, 6, 2, 0],
        stations[1]: [1, 3, 3, 6],
    }
    for station_id, scores in plans.items():
        for student_id, score in zip(students, scores):
            _add_eval_record(event_id, station_id, student_id, score, 10,
                             mode=SessionMode.pilotaje.value)
    return event_id


def _station_ids(event_id: int) -> list[int]:
    with TestingSessionLocal() as db:
        return [
            s.id
            for s in db.scalars(
                select(Station).where(Station.ecoe_event_id == event_id)
                .order_by(Station.station_number)
            ).all()
        ]


def test_pilot_psychometrics_returns_warnings(auth_client):
    event_id = _pilot_ready_event()
    block = auth_client.get(f"/api/analytics/{event_id}/psychometrics?mode=pilotaje").json()
    codes = {w["code"] for w in block["warnings"]}
    # Estaciones anticorrelacionadas → α baja y discriminación negativa/baja.
    assert block["reliability"]["cronbach_alpha"] is not None
    assert codes & {"cronbach_alpha_low", "station_discrimination_negative",
                    "station_discrimination_low"}


def test_pilot_validation_does_not_block_transition_and_writes_audit(auth_client):
    """Transición a `pilotaje_validado` con métricas malas → 200 + AuditLog."""
    event_id = _pilot_ready_event()
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        update_ecoe_status(
            db, event, ECOEStatus.pilotaje_validado.value, actor_email="admin@ecoe.cl"
        )
        db.refresh(event)
        assert event.status == ECOEStatus.pilotaje_validado.value

    with TestingSessionLocal() as db:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.action == "validate_pilot",
                AuditLog.target_id == str(event_id),
            )
        ).all()
    assert len(logs) == 1
    assert logs[0].user_email == "admin@ecoe.cl"
    assert "cronbach_alpha" in logs[0].payload
    assert "warning_count" in logs[0].payload


def test_allowed_status_transitions_unchanged():
    """OPT-18 no toca el grafo de estados."""
    from app.services.validation import ALLOWED_STATUS_TRANSITIONS

    assert ALLOWED_STATUS_TRANSITIONS[ECOEStatus.en_pilotaje.value] == {
        ECOEStatus.listo_para_pilotaje.value,
        ECOEStatus.pilotaje_validado.value,
    }
