"""OPT-16 · Resultado por estación (`StationResult`) + desglose `by_station`.

Cubre:
- `persist_results` puebla `StationResult` (delete-then-insert idempotente).
- `compute_station_results` reusa los mismos filtros que `compute_results`:
  excluye borradores de evaluador, `mode=pilotaje` y pendientes de corrección
  diferida (`score_obtained IS NULL`).
- Invariante: `sum(by_station del estudiante) == ECOEResult del estudiante`.
- `read_station_results` congela el snapshot tras el cierre y cae a vivo si el
  evento está cerrado sin filas.
- `GET /results` expone `by_station.stations` + `by_station.students`.
- `compute_station_results` es función de módulo reutilizable con parámetro
  `mode` aditivo (lo necesitan OPT-17/18).
"""

import inspect
import statistics
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.models.entities import (
    ECOEEvent,
    ECOEResult,
    EvaluatorRecord,
    Station,
    StationCheckIn,
    StationResult,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.results import (
    build_station_score_block,
    compute_station_results,
    persist_results,
    read_station_results,
)
from app.services.validation import update_ecoe_status
from conftest import ADMIN, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _auto_form(points: int, correct: str = "A") -> dict:
    return {
        "questions": [
            {
                "type": "single_choice",
                "label": "Conducta",
                "options": ["A", "B"],
                "points": points,
                "correct_option": correct,
            },
        ]
    }


MANUAL_FORM = {"questions": [{"type": "short_text", "label": "Justifica", "points": 4}]}


def _build_event(*, status: str = ECOEStatus.en_ejecucion.value, n_students: int = 3):
    """Evento en ejecución con 2 estaciones de formulario y `n_students` alumnos.

    Estación 1: autocorrección (single_choice, máx 10).
    Estación 2: autocorrección (single_choice, máx 6).
    Cada alumno tiene check-in confirmado en ambas estaciones.
    """
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Estaciones OPT-16",
            date=date(2026, 12, 10),
            course_name="Curso",
            school_name="Escuela",
            responsible_teacher="Docente",
            contact_email="docente@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=2,
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=n_students,
            total_groups=1,
            passing_reference_percent=60,
            status=status,
        )
        db.add(event)
        db.flush()
        stations = []
        for number, points in ((1, 10), (2, 6)):
            station = Station(
                ecoe_event_id=event.id,
                station_number=number,
                name=f"Estación {number}",
                station_type="formulario_estudiante",
                circuit_name="Circuito A",
                station_time_minutes=8,
                transition_time_minutes=2,
                expected_outcomes="Resultado",
                student_activity="Actividad",
                pre_entry_instruction="Ingreso",
                evaluator_instruction="",
                requires_evaluator=False,
                requires_student_form=True,
                max_score=points,
                student_form_definition=_auto_form(points),
            )
            db.add(station)
            db.flush()
            stations.append(station.id)
        students = []
        for idx in range(n_students):
            student = Student(
                ecoe_event_id=event.id,
                name=f"Alumno{idx}",
                last_name="Estación",
                rut=f"7{event.id}{idx}00-1",
                email=f"st{event.id}_{idx}@example.edu",
                ecoe_number=f"{idx + 1:03d}",
                group_name="G1",
                circuit_name="Circuito A",
                is_active=True,
            )
            db.add(student)
            db.flush()
            checkins = {}
            for station_id in stations:
                checkin = StationCheckIn(
                    ecoe_event_id=event.id,
                    station_id=station_id,
                    student_id=student.id,
                    evaluator_email="eval1@ecoe.cl",
                    evaluator_name="Evaluadora",
                    status="confirmado",
                    confirmed_at=_utcnow_naive(),
                )
                db.add(checkin)
                db.flush()
                checkins[station_id] = checkin.id
            students.append((student.id, checkins))
        db.commit()
        return event.id, stations, students


def _submit(client, event_id, station_id, student_id, checkin_id, answer):
    response = client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        "answers": {"question_1": answer},
    })
    assert response.status_code == 200, response.text
    return response.json()["response_id"]


def _close(event_id: int, actor_email: str = "admin@ecoe.cl") -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        update_ecoe_status(db, event, ECOEStatus.cerrado.value, actor_email=actor_email)


def _set_status(event_id: int, status: str) -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        event.status = status
        db.add(event)
        db.commit()


# ── Positivos ─────────────────────────────────────────────────────────


def test_persist_results_populates_station_results(auth_client):
    event_id, stations, students = _build_event(n_students=2)
    s1, s2 = stations
    (st_a, ck_a), (st_b, ck_b) = students
    _submit(auth_client, event_id, s1, st_a, ck_a[s1], "A")   # 10/10
    _submit(auth_client, event_id, s2, st_a, ck_a[s2], "B")   # 0/6
    _submit(auth_client, event_id, s1, st_b, ck_b[s1], "B")   # 0/10
    _submit(auth_client, event_id, s2, st_b, ck_b[s2], "A")   # 6/6

    _close(event_id)

    with TestingSessionLocal() as db:
        rows = db.scalars(
            select(StationResult).where(StationResult.ecoe_event_id == event_id)
        ).all()
        by_key = {(r.student_id, r.station_id): r for r in rows}
    assert len(rows) == 4
    assert by_key[(st_a, s1)].obtained_score == 10
    assert by_key[(st_a, s1)].max_score == 10
    assert by_key[(st_a, s1)].percent_score == 100
    assert by_key[(st_a, s2)].percent_score == 0
    assert by_key[(st_b, s2)].percent_score == 100


def test_station_results_sum_matches_consolidated(auth_client):
    event_id, stations, students = _build_event(n_students=3)
    s1, s2 = stations
    answers = {0: ("A", "A"), 1: ("A", "B"), 2: ("B", "B")}
    for idx, (student_id, checkins) in enumerate(students):
        a1, a2 = answers[idx]
        _submit(auth_client, event_id, s1, student_id, checkins[s1], a1)
        _submit(auth_client, event_id, s2, student_id, checkins[s2], a2)

    _close(event_id)

    with TestingSessionLocal() as db:
        station_rows = db.scalars(
            select(StationResult).where(StationResult.ecoe_event_id == event_id)
        ).all()
        ecoe_rows = {
            r.student_id: r
            for r in db.scalars(
                select(ECOEResult).where(ECOEResult.ecoe_event_id == event_id)
            ).all()
        }
    per_student: dict[int, list[float]] = {}
    for row in station_rows:
        acc = per_student.setdefault(row.student_id, [0.0, 0.0])
        acc[0] += row.obtained_score
        acc[1] += row.max_score
    for student_id, (obtained, max_score) in per_student.items():
        assert obtained == pytest.approx(ecoe_rows[student_id].total_score)
        assert max_score == pytest.approx(ecoe_rows[student_id].max_score)


def test_by_station_block_in_results_payload(auth_client):
    event_id, stations, students = _build_event(n_students=3)
    s1, s2 = stations
    # Estación 1: A, A, B → 100%, 100%, 0%
    plan = {0: "A", 1: "A", 2: "B"}
    for idx, (student_id, checkins) in enumerate(students):
        _submit(auth_client, event_id, s1, student_id, checkins[s1], plan[idx])

    body = auth_client.get(f"/api/results/{event_id}").json()
    assert "by_station" in body
    stations_block = {row["station_id"]: row for row in body["by_station"]["stations"]}
    st1 = stations_block[s1]
    assert st1["n"] == 3
    assert st1["mean_percent"] == pytest.approx(
        statistics.fmean([100.0, 100.0, 0.0]), abs=0.01
    )
    assert st1["sd_percent"] == pytest.approx(
        statistics.stdev([100.0, 100.0, 0.0]), abs=0.05
    )
    assert st1["min_percent"] == 0
    assert st1["max_percent"] == 100
    # Estación 2 sin respuestas → n=0, agregados None
    st2 = stations_block[s2]
    assert st2["n"] == 0
    assert st2["mean_percent"] is None
    assert st2["sd_percent"] is None
    # Formato largo: 3 filas (una por alumno en la estación 1)
    long_rows = [r for r in body["by_station"]["students"] if r["station_id"] == s1]
    assert len(long_rows) == 3
    assert {r["percent_score"] for r in long_rows} == {0.0, 100.0}


def test_by_station_recalculates_before_close(auth_client):
    event_id, stations, students = _build_event(n_students=1)
    s1, _s2 = stations
    student_id, checkins = students[0]

    body = auth_client.get(f"/api/results/{event_id}").json()
    assert body["frozen"] is False
    assert all(row["n"] == 0 for row in body["by_station"]["stations"])

    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")
    body = auth_client.get(f"/api/results/{event_id}").json()
    st1 = next(r for r in body["by_station"]["stations"] if r["station_id"] == s1)
    assert st1["n"] == 1
    assert st1["mean_percent"] == 100


def test_by_station_single_row_has_no_sd(auth_client):
    event_id, stations, students = _build_event(n_students=1)
    s1, _s2 = stations
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")
    body = auth_client.get(f"/api/results/{event_id}").json()
    st1 = next(r for r in body["by_station"]["stations"] if r["station_id"] == s1)
    assert st1["n"] == 1
    assert st1["sd_percent"] is None
    assert st1["sd_score"] is None
    assert st1["mean_score"] == 10


# ── Negativos / integridad ───────────────────────────────────────────


def test_by_station_excludes_evaluator_drafts(auth_client):
    event_id, stations, students = _build_event(n_students=1)
    s1, _s2 = stations
    student_id, _checkins = students[0]
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=event_id,
            station_id=s1,
            student_id=student_id,
            evaluator_name="Eval",
            mode=SessionMode.ejecucion.value,
            score_obtained=8,
            max_score=10,
            is_draft=True,
        ))
        db.commit()

    rows = compute_station_results_for(event_id)
    assert rows == []

    body = auth_client.get(f"/api/results/{event_id}").json()
    assert all(row["n"] == 0 for row in body["by_station"]["stations"])


def test_by_station_includes_finalized_evaluator_record(auth_client):
    """Contraparte del test de borradores: `is_draft=False` sí entra."""
    event_id, stations, students = _build_event(n_students=1)
    s1, _s2 = stations
    student_id, _checkins = students[0]
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=event_id,
            station_id=s1,
            student_id=student_id,
            evaluator_name="Eval",
            mode=SessionMode.ejecucion.value,
            score_obtained=8,
            max_score=10,
            is_draft=False,
        ))
        db.commit()
    rows = compute_station_results_for(event_id)
    assert len(rows) == 1
    assert rows[0]["obtained_score"] == 8
    assert rows[0]["percent_score"] == 80


def test_by_station_excludes_pilotaje(auth_client):
    event_id, stations, students = _build_event(n_students=1)
    s1, _s2 = stations
    student_id, _checkins = students[0]
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=event_id,
            station_id=s1,
            student_id=student_id,
            evaluator_name="Eval",
            mode=SessionMode.pilotaje.value,
            score_obtained=9,
            max_score=10,
            is_draft=False,
        ))
        db.commit()

    # Default `mode="ejecucion"` → no ve el registro de pilotaje.
    assert compute_station_results_for(event_id) == []
    body = auth_client.get(f"/api/results/{event_id}").json()
    assert all(row["n"] == 0 for row in body["by_station"]["stations"])

    # OPT-18 usará `mode="pilotaje"` — el parámetro es aditivo y sí lo trae.
    with TestingSessionLocal() as db:
        pilot_rows = compute_station_results(db, event_id, mode=SessionMode.pilotaje.value)
    assert len(pilot_rows) == 1
    assert pilot_rows[0]["obtained_score"] == 9


def test_by_station_excludes_pending_deferred_grading(client):
    login(client, ADMIN)
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Diferida OPT-16",
            date=date(2026, 12, 10),
            course_name="Curso",
            school_name="Escuela",
            responsible_teacher="Docente",
            contact_email="docente@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=1,
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=1,
            total_groups=1,
            passing_reference_percent=60,
            status=ECOEStatus.en_ejecucion.value,
        )
        db.add(event)
        db.flush()
        station = Station(
            ecoe_event_id=event.id,
            station_number=1,
            name="Informe",
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
            requires_deferred_grading=True,
            max_score=4,
            student_form_definition=MANUAL_FORM,
        )
        db.add(station)
        db.flush()
        student = Student(
            ecoe_event_id=event.id,
            name="Alumna",
            last_name="Diferida",
            rut=f"9{event.id}00-1",
            email=f"def{event.id}@example.edu",
            ecoe_number="001",
            group_name="G1",
            circuit_name="Circuito A",
            is_active=True,
        )
        db.add(student)
        db.flush()
        checkin = StationCheckIn(
            ecoe_event_id=event.id,
            station_id=station.id,
            student_id=student.id,
            evaluator_email="coord@ecoe.cl",
            evaluator_name="Coord",
            status="confirmado",
            confirmed_at=_utcnow_naive(),
        )
        db.add(checkin)
        db.commit()
        event_id, station_id, student_id, checkin_id = (
            event.id, station.id, student.id, checkin.id
        )

    response_id = _submit(client, event_id, station_id, student_id, checkin_id, "texto")

    # Pendiente de corrección (score_obtained IS NULL) → no entra.
    assert compute_station_results_for(event_id) == []

    graded = client.post(
        f"/api/grading/responses/{response_id}", json={"scores": {"question_1": 3}}
    )
    assert graded.status_code == 200, graded.text

    rows = compute_station_results_for(event_id)
    assert len(rows) == 1
    assert rows[0]["obtained_score"] == 3
    assert rows[0]["max_score"] == 4
    assert rows[0]["percent_score"] == 75


def test_station_results_idempotent_on_reconsolidate(auth_client):
    event_id, stations, students = _build_event(n_students=2)
    s1, s2 = stations
    for student_id, checkins in students:
        _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")
        _submit(auth_client, event_id, s2, student_id, checkins[s2], "A")

    snapshots = []
    for _ in range(3):
        with TestingSessionLocal() as db:
            persist_results(db, event_id, actor_email="admin@ecoe.cl")
        with TestingSessionLocal() as db:
            rows = db.scalars(
                select(StationResult)
                .where(StationResult.ecoe_event_id == event_id)
                .order_by(StationResult.student_id, StationResult.station_id)
            ).all()
            snapshots.append([
                (r.student_id, r.station_id, r.obtained_score, r.max_score, r.percent_score)
                for r in rows
            ])
    assert len(snapshots[0]) == 4  # 2 alumnos x 2 estaciones
    assert snapshots[0] == snapshots[1] == snapshots[2]


def test_by_station_frozen_snapshot_does_not_change_after_close(auth_client):
    event_id, stations, students = _build_event(n_students=1)
    s1, _s2 = stations
    student_id, checkins = students[0]
    response_id = _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")

    _close(event_id)

    # Se manipula el puntaje real después de consolidar.
    with TestingSessionLocal() as db:
        response = db.get(StudentResponse, response_id)
        response.score_obtained = 0
        db.add(response)
        db.commit()

    body = auth_client.get(f"/api/results/{event_id}").json()
    assert body["frozen"] is True
    st1 = next(r for r in body["by_station"]["stations"] if r["station_id"] == s1)
    assert st1["mean_percent"] == 100  # snapshot, no el 0 recalculado
    long_row = next(r for r in body["by_station"]["students"] if r["station_id"] == s1)
    assert long_row["obtained_score"] == 10

    # El recálculo en vivo sí ve la mutación.
    with TestingSessionLocal() as db:
        live = compute_station_results(db, event_id)
    assert live[0]["obtained_score"] == 0


def test_by_station_falls_back_to_live_when_closed_without_snapshot(auth_client):
    event_id, stations, students = _build_event(n_students=1)
    s1, _s2 = stations
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")
    _set_status(event_id, ECOEStatus.cerrado.value)  # cierre "a mano", sin snapshot

    with TestingSessionLocal() as db:
        assert not db.scalars(
            select(StationResult).where(StationResult.ecoe_event_id == event_id)
        ).all()
        rows, frozen = read_station_results(db, event_id)
    assert frozen is False
    assert len(rows) == 1
    assert rows[0]["obtained_score"] == 10


def test_blank_auto_submission_counts_as_zero_in_station(auth_client):
    event_id, stations, students = _build_event(n_students=2)
    s1, _s2 = stations
    (st_a, ck_a), (st_b, ck_b) = students
    _submit(auth_client, event_id, s1, st_a, ck_a[s1], "A")  # 10/10
    # Autoenvío en blanco con score 0 resuelto (submission_kind=auto, answers={}).
    with TestingSessionLocal() as db:
        db.add(StudentResponse(
            ecoe_event_id=event_id,
            station_id=s1,
            student_id=st_b,
            mode=SessionMode.ejecucion.value,
            answers={},
            submission_kind="auto",
            score_obtained=0,
            max_score=10,
        ))
        db.commit()

    rows = {r["student_id"]: r for r in compute_station_results_for(event_id)}
    assert rows[st_b]["obtained_score"] == 0
    assert rows[st_b]["max_score"] == 10
    assert rows[st_b]["percent_score"] == 0

    body = auth_client.get(f"/api/results/{event_id}").json()
    st1 = next(r for r in body["by_station"]["stations"] if r["station_id"] == s1)
    assert st1["n"] == 2
    assert st1["mean_percent"] == pytest.approx(50.0, abs=0.01)


# ── Coordinación OPT-17 / OPT-18 ─────────────────────────────────────


def test_compute_station_results_is_reusable_module_function_with_mode():
    """OPT-17 reescribe `compute_results` sobre esta función; OPT-18 la llama
    con `mode="pilotaje"`. Debe ser función de módulo (no anidada) con `mode`
    keyword-only y default `"ejecucion"`."""
    assert inspect.isfunction(compute_station_results)
    assert compute_station_results.__module__ == "app.services.results"
    sig = inspect.signature(compute_station_results)
    assert list(sig.parameters) == ["db", "ecoe_event_id", "mode"]
    mode_param = sig.parameters["mode"]
    assert mode_param.kind is inspect.Parameter.KEYWORD_ONLY
    assert mode_param.default == SessionMode.ejecucion.value


def test_build_station_score_block_is_pure_python_no_db():
    stations = [
        _FakeStation(1, 1, "E1", "Circuito A"),
        _FakeStation(2, 2, "E2", "Circuito A"),
    ]
    students = {10: _FakeStudent("001", "Ana", "Pérez")}
    rows = [
        {"student_id": 10, "station_id": 1, "obtained_score": 8.0,
         "max_score": 10.0, "percent_score": 80.0},
    ]
    block = build_station_score_block(rows, stations, students)
    assert [s["n"] for s in block["stations"]] == [1, 0]
    assert block["stations"][0]["mean_percent"] == 80.0
    assert block["stations"][1]["mean_percent"] is None
    assert block["students"][0]["student_name"] == "Ana Pérez"
    assert block["students"][0]["ecoe_number"] == "001"


class _FakeStation:
    def __init__(self, id_, number, name, circuit):
        self.id = id_
        self.station_number = number
        self.name = name
        self.circuit_name = circuit


class _FakeStudent:
    def __init__(self, ecoe_number, name, last_name):
        self.ecoe_number = ecoe_number
        self.name = name
        self.last_name = last_name


def compute_station_results_for(event_id: int) -> list[dict]:
    with TestingSessionLocal() as db:
        return compute_station_results(db, event_id)
