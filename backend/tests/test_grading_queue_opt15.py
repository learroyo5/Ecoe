"""OPT-15 — cola del corrector: forma extendida de `GET /api/grading/{event}`
(`assessment_tool` por fila, `scope`, `pending_by_station`) y `next` /
`pending_remaining` en `grade_response`.

Incluye negativos de scoping: aunque el hallazgo es UX, se toca la forma de la
respuesta de un endpoint con scoping por corrector.
"""

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEEvent,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, RoleCode
from conftest import ADMIN, TestingSessionLocal, login
from test_deferred_grading import _account, _assign_corrector


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


MANUAL_FORM = {"questions": [{"type": "short_text", "label": "Interpreta", "points": 6}]}


def _make_multi_station_event(*, tool_on_first: bool = False, students_per_station: int = 1):
    """Evento en ejecución con dos estaciones de corrección diferida.

    Devuelve ``(event_id, [station_id, ...], [(station_id, student_id, checkin_id), ...])``.
    """
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Cola corrector",
            date=date(2026, 12, 10),
            course_name="Curso",
            school_name="Escuela",
            responsible_teacher="Docente",
            contact_email="docente@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=2,
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=students_per_station * 2,
            total_groups=1,
            passing_reference_percent=60,
            status=ECOEStatus.en_ejecucion.value,
        )
        db.add(event)
        db.flush()

        tool_id = None
        if tool_on_first:
            tool = AssessmentTool(
                name="Pauta informe", tool_type="checklist", max_score=6, free_observation=True
            )
            db.add(tool)
            db.flush()
            db.add_all([
                AssessmentItem(tool_id=tool.id, label="Identifica el ritmo", score_per_item=3, order_index=0),
                AssessmentItem(tool_id=tool.id, label="Propone manejo", score_per_item=3, order_index=1),
            ])
            db.flush()
            tool_id = tool.id

        station_ids: list[int] = []
        checkins: list[tuple[int, int, int]] = []
        for number in (1, 2):
            station = Station(
                ecoe_event_id=event.id,
                station_number=number,
                name=f"Informe {number}",
                station_type="formulario_estudiante",
                circuit_name="Circuito A",
                station_time_minutes=8,
                transition_time_minutes=2,
                expected_outcomes="Resultado",
                student_activity="Actividad",
                pre_entry_instruction="Ingreso",
                student_station_instruction="Dentro",
                evaluator_instruction="",
                requires_evaluator=False,
                requires_student_form=True,
                requires_deferred_grading=True,
                max_score=6,
                student_form_definition=MANUAL_FORM,
                assessment_tool_id=tool_id if number == 1 else None,
            )
            db.add(station)
            db.flush()
            station_ids.append(station.id)
            for index in range(students_per_station):
                student = Student(
                    ecoe_event_id=event.id,
                    name=f"Alumna{number}{index}",
                    last_name="Cola",
                    rut=f"5{event.id}{number}{index}0-1",
                    email=f"cola{event.id}-{number}-{index}@example.edu",
                    ecoe_number=f"{number}{index}1",
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
                    evaluator_name="Coordinación",
                    status="confirmado",
                    confirmed_at=_utcnow_naive(),
                )
                db.add(checkin)
                db.flush()
                checkins.append((station.id, student.id, checkin.id))
        db.commit()
        return event.id, station_ids, checkins


def _submit(auth_client, event_id, station_id, student_id, checkin_id, answer="Ritmo sinusal"):
    response = auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        "answers": {"question_1": answer},
    })
    assert response.status_code == 200, response.text
    return response.json()["response_id"]


def _spread_submitted_at(event_id: int) -> None:
    """Da `submitted_at` estrictamente creciente por id para un orden FIFO estable."""
    with TestingSessionLocal() as db:
        rows = db.scalars(
            select(StudentResponse)
            .where(StudentResponse.ecoe_event_id == event_id)
            .order_by(StudentResponse.id.asc())
        ).all()
        base = _utcnow_naive()
        for offset, row in enumerate(rows):
            row.submitted_at = base + timedelta(minutes=offset)
            db.add(row)
        db.commit()


# ── Negativos de scoping ──────────────────────────────────────────────

def test_corrector_response_rows_stay_within_scope(auth_client, client):
    login(auth_client, ADMIN)
    event_id, station_ids, checkins = _make_multi_station_event(tool_on_first=True)
    station_a, station_b = station_ids
    for station_id, student_id, checkin_id in checkins:
        _submit(auth_client, event_id, station_id, student_id, checkin_id)

    password = secrets.token_urlsafe(24)
    _account("corr-scope-a@example.edu", password)
    _assign_corrector(event_id, "corr-scope-a@example.edu", [station_a])

    login(client, ("corr-scope-a@example.edu", password))
    body = client.get(f"/api/grading/{event_id}").json()

    assert {row["station_id"] for row in body["responses"]} == {station_a}
    # `assessment_tool` solo de la estación A (la única en scope y la única con pauta).
    assert body["responses"][0]["assessment_tool"] is not None
    assert len(body["responses"][0]["assessment_tool"]["items"]) == 2
    assert str(station_b) not in body["pending_by_station"]


def test_pending_by_station_respects_corrector_scope(auth_client, client):
    login(auth_client, ADMIN)
    event_id, station_ids, checkins = _make_multi_station_event()
    station_a, station_b = station_ids
    for station_id, student_id, checkin_id in checkins:
        _submit(auth_client, event_id, station_id, student_id, checkin_id)

    password = secrets.token_urlsafe(24)
    _account("corr-pbs@example.edu", password)
    _assign_corrector(event_id, "corr-pbs@example.edu", [station_a])

    login(client, ("corr-pbs@example.edu", password))
    body = client.get(f"/api/grading/{event_id}").json()

    assert list(body["pending_by_station"].keys()) == [str(station_a)]
    assert body["pending_by_station"][str(station_a)]["pending"] == 1
    assert body["pending_count"] == 1  # solo A, no B


def test_grade_response_next_stays_within_scope(auth_client, client):
    login(auth_client, ADMIN)
    event_id, station_ids, checkins = _make_multi_station_event(students_per_station=2)
    station_a, station_b = station_ids
    for station_id, student_id, checkin_id in checkins:
        _submit(auth_client, event_id, station_id, student_id, checkin_id)
    _spread_submitted_at(event_id)

    resp = _responses_by_student(event_id)
    a_responses = [resp[stu] for (s, stu, _) in checkins if s == station_a]

    password = secrets.token_urlsafe(24)
    _account("corr-next@example.edu", password)
    _assign_corrector(event_id, "corr-next@example.edu", [station_a])
    login(client, ("corr-next@example.edu", password))

    graded = client.post(
        f"/api/grading/responses/{a_responses[0]}", json={"scores": {"question_1": 4}}
    ).json()
    # El `next` apunta a la otra respuesta de A, nunca a una de B.
    assert graded["next"]["response_id"] == a_responses[1]
    assert graded["pending_remaining"] == 1

    graded_last = client.post(
        f"/api/grading/responses/{a_responses[1]}", json={"scores": {"question_1": 4}}
    ).json()
    assert graded_last["next"] is None
    assert graded_last["pending_remaining"] == 0


def test_grading_scope_object_for_corrector_without_assignment(auth_client, client):
    login(auth_client, ADMIN)
    event_id, station_ids, checkins = _make_multi_station_event()

    password = secrets.token_urlsafe(24)
    _account("corr-noassign@example.edu", password)
    # Asignación de corrector SIN estaciones (lo que deja el import CSV de staff,
    # `staff.py` fuerza `station_ids=[]`): tiene acceso al evento por el rol, pero
    # scope vacío → caso H-corr-6.
    _assign_corrector(event_id, "corr-noassign@example.edu", [])

    login(client, ("corr-noassign@example.edu", password))
    body = client.get(f"/api/grading/{event_id}").json()

    assert body["responses"] == []
    assert body["scope"] == {
        "is_corrector": True,
        "has_assignment": False,
        "assigned_station_ids": [],
    }
    assert body["pending_by_station"] == {}


def test_corrector_event_a_cannot_read_grading_event_b(auth_client, client):
    login(auth_client, ADMIN)
    event_a, stations_a, _ = _make_multi_station_event()
    event_b, _, _ = _make_multi_station_event()

    password = secrets.token_urlsafe(24)
    _account("corr-crossevent@example.edu", password)
    _assign_corrector(event_a, "corr-crossevent@example.edu", [stations_a[0]])

    login(client, ("corr-crossevent@example.edu", password))
    assert client.get(f"/api/grading/{event_b}").status_code == 403


# ── Positivos ─────────────────────────────────────────────────────────

def test_grading_row_includes_serialized_assessment_tool(auth_client):
    login(auth_client, ADMIN)
    event_id, station_ids, checkins = _make_multi_station_event(tool_on_first=True)
    for station_id, student_id, checkin_id in checkins:
        _submit(auth_client, event_id, station_id, student_id, checkin_id)

    body = auth_client.get(f"/api/grading/{event_id}").json()
    by_station = {row["station_id"]: row for row in body["responses"]}

    with_tool = by_station[station_ids[0]]["assessment_tool"]
    assert with_tool is not None
    assert with_tool["name"] == "Pauta informe"
    assert [item["label"] for item in with_tool["items"]] == [
        "Identifica el ritmo",
        "Propone manejo",
    ]
    assert by_station[station_ids[1]]["assessment_tool"] is None


def test_grade_response_returns_next_and_pending_remaining(auth_client):
    login(auth_client, ADMIN)
    event_id, station_ids, checkins = _make_multi_station_event(students_per_station=3)
    station_a = station_ids[0]
    # Solo la estación A tiene respuestas → 3 pendientes en total.
    a_checkins = [c for c in checkins if c[0] == station_a]
    for station_id, student_id, checkin_id in a_checkins:
        _submit(auth_client, event_id, station_id, student_id, checkin_id)
    _spread_submitted_at(event_id)

    resp = _responses_by_student(event_id)
    a_responses = [resp[stu] for (s, stu, _) in a_checkins]
    assert len(a_responses) == 3

    first = auth_client.post(
        f"/api/grading/responses/{a_responses[0]}", json={"scores": {"question_1": 3}}
    ).json()
    assert first["next"]["response_id"] == a_responses[1]
    assert first["pending_remaining"] == 2

    second = auth_client.post(
        f"/api/grading/responses/{a_responses[1]}", json={"scores": {"question_1": 3}}
    ).json()
    assert second["next"]["response_id"] == a_responses[2]

    third = auth_client.post(
        f"/api/grading/responses/{a_responses[2]}", json={"scores": {"question_1": 3}}
    ).json()
    assert third["next"] is None
    assert third["pending_remaining"] == 0


def test_admin_sees_full_scope_object(auth_client):
    login(auth_client, ADMIN)
    event_id, station_ids, checkins = _make_multi_station_event()
    for station_id, student_id, checkin_id in checkins:
        _submit(auth_client, event_id, station_id, student_id, checkin_id)

    body = auth_client.get(f"/api/grading/{event_id}").json()
    assert body["scope"] == {
        "is_corrector": False,
        "has_assignment": True,
        "assigned_station_ids": [],
    }
    assert {int(k) for k in body["pending_by_station"]} == set(station_ids)


def _responses_by_student(event_id: int) -> dict[int, int]:
    """{student_id: response_id} para el evento."""
    with TestingSessionLocal() as db:
        return {
            row.student_id: row.id
            for row in db.scalars(
                select(StudentResponse).where(StudentResponse.ecoe_event_id == event_id)
            ).all()
        }
