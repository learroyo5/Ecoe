"""Evaluación diferida: rol `corrector`, asignación, corrección acotada y validación.

Ver docs/architecture/EVALUACION_DIFERIDA_FASE1.md.
"""

import secrets
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.entities import (
    ECOEEvent,
    Role,
    StaffAssignment,
    Station,
    StationCheckIn,
    Student,
    User,
)
from app.models.enums import ECOEStatus, RoleCode
from app.services.results import build_traceability_report, compute_results
from app.services.validation import compute_ecoe_validation
from conftest import ADMIN, COEDITOR, COORDINATOR, EVALUATOR, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


MANUAL_FORM = {
    "questions": [
        {"type": "short_text", "label": "Interpreta el ECG", "points": 6},
    ]
}


def _make_event(*, deferred: bool, form: dict | None = MANUAL_FORM, with_form: bool = True):
    """Evento en ejecución con una estación de formulario y un estudiante con check-in."""
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Diferida",
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
            name="Informe escrito",
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
            requires_student_form=with_form,
            requires_deferred_grading=deferred,
            max_score=6,
            student_form_definition=form if with_form else {},
        )
        db.add(station)
        db.flush()
        student = Student(
            ecoe_event_id=event.id,
            name="Alumna",
            last_name="Diferida",
            rut=f"41{event.id}00-1",
            email=f"deferred{event.id}@example.edu",
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
            evaluator_name="Coordinación",
            status="confirmado",
            confirmed_at=_utcnow_naive(),
        )
        db.add(checkin)
        db.commit()
        return event.id, station.id, student.id, checkin.id


def _account(email: str, password: str, role_code: str = RoleCode.miembro.value) -> None:
    with TestingSessionLocal() as db:
        role = db.scalar(select(Role).where(Role.code == role_code))
        db.add(User(
            email=email,
            full_name=email.split("@", 1)[0],
            hashed_password=get_password_hash(password),
            role_id=role.id,
            is_active=True,
        ))
        db.commit()


def _assign_corrector(event_id: int, email: str, station_ids: list[int]) -> None:
    with TestingSessionLocal() as db:
        db.add(StaffAssignment(
            ecoe_event_id=event_id,
            name="Correctora",
            last_name="Diferida",
            email=email,
            role_code=RoleCode.corrector.value,
            station_ids=station_ids,
        ))
        db.commit()


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


# ── Asignación y delegación del rol corrector ───────────────────────────

def test_coeditor_and_coordinator_can_delegate_corrector_multi_station(client, db_factory):
    login(client, ADMIN)
    event = client.post("/api/ecoe", json={
        "name": "Correctores", "date": "2026-12-01", "course_name": "C",
        "school_name": "E", "responsible_teacher": "D", "contact_email": "d@e.edu",
        "circuit_mode": "paralelo_espejo", "total_stations": 2,
        "station_time_minutes": 8, "transition_time_minutes": 2,
        "total_students": 1, "total_groups": 1, "passing_reference_percent": 60,
    }).json()
    event_id = event["id"]

    def _station(number: int) -> int:
        payload = {
            "ecoe_event_id": event_id, "station_number": number,
            "name": f"E{number}", "station_type": "formulario_estudiante",
            "circuit_name": "Circuito A", "expected_outcomes": "o",
            "student_activity": "a", "pre_entry_instruction": "p",
            "student_station_instruction": "s", "evaluator_instruction": "",
            "requires_evaluator": False, "requires_student_form": True,
            "requires_deferred_grading": True, "max_score": 3,
            "student_form_definition": {"questions": [
                {"type": "short_text", "label": "x", "points": 3},
            ]},
        }
        return client.post("/api/stations", json=payload).json()["id"]

    s1, s2 = _station(1), _station(2)
    password = secrets.token_urlsafe(24)
    _account("corr-multi@example.edu", password)

    # El coordinador necesita rol efectivo en este evento para delegar en él.
    assigned = client.post("/api/staff", json={
        "ecoe_event_id": event_id, "name": "Coord", "last_name": "Op",
        "email": COORDINATOR[0], "role_code": "coordinador_operativo", "station_ids": [],
    })
    assert assigned.status_code == 200, assigned.text

    login(client, COORDINATOR)
    created = client.post("/api/staff", json={
        "ecoe_event_id": event_id,
        "name": "Correctora", "last_name": "Multi",
        "email": "corr-multi@example.edu",
        "role_code": "corrector",
        "station_ids": [s1, s2],
    })
    assert created.status_code == 200, created.text
    assert sorted(created.json()["station_ids"]) == sorted([s1, s2])


def _extra_station(event_id: int, number: int) -> int:
    with TestingSessionLocal() as db:
        station = Station(
            ecoe_event_id=event_id,
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
        )
        db.add(station)
        db.commit()
        db.refresh(station)
        return station.id


def _corrector_staff_id(event_id: int, email: str) -> int:
    with TestingSessionLocal() as db:
        return db.scalar(
            select(StaffAssignment).where(
                StaffAssignment.ecoe_event_id == event_id,
                StaffAssignment.email == email,
            )
        ).id


def test_corrector_station_ids_updated_in_place(auth_client, client):
    """`PATCH /api/staff/{id}` mueve las estaciones de un corrector sin borrarlo;
    el scope de `GET /api/grading/{event}` cambia en consecuencia."""
    login(auth_client, ADMIN)
    event_id, station_a, student_id, checkin_id = _make_event(deferred=True)
    station_b = _extra_station(event_id, 2)
    _submit(auth_client, event_id, station_a, student_id, checkin_id)

    password = secrets.token_urlsafe(24)
    _account("corr-reassign@example.edu", password)
    _assign_corrector(event_id, "corr-reassign@example.edu", [station_a])
    staff_id = _corrector_staff_id(event_id, "corr-reassign@example.edu")

    login(client, ("corr-reassign@example.edu", password))
    assert client.get(f"/api/grading/{event_id}").json()["pending_count"] == 1

    # `auth_client` y `client` son el MISMO TestClient: re-autenticamos como
    # admin para el PATCH y volvemos al corrector para revisar el scope.
    login(auth_client, ADMIN)
    patched = auth_client.patch(
        f"/api/staff/{staff_id}",
        json={"role_code": "corrector", "station_ids": [station_b]},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["station_ids"] == [station_b]

    login(client, ("corr-reassign@example.edu", password))
    body = client.get(f"/api/grading/{event_id}").json()
    assert body["responses"] == []  # ya no ve la estación A
    assert body["scope"]["assigned_station_ids"] == [station_b]


def test_corrector_cannot_be_left_without_stations(auth_client):
    login(auth_client, ADMIN)
    event_id, station_a, _, _ = _make_event(deferred=True)
    _account("corr-empty@example.edu", "x")
    _assign_corrector(event_id, "corr-empty@example.edu", [station_a])
    staff_id = _corrector_staff_id(event_id, "corr-empty@example.edu")

    blocked = auth_client.patch(
        f"/api/staff/{staff_id}",
        json={"role_code": "corrector", "station_ids": []},
    )
    assert blocked.status_code == 400
    assert _corrector_staff_id(event_id, "corr-empty@example.edu")  # sigue existiendo


def test_reassign_corrector_station_must_belong_to_event(auth_client):
    login(auth_client, ADMIN)
    event_id, station_a, _, _ = _make_event(deferred=True)
    other_event, other_station, _, _ = _make_event(deferred=True)
    _account("corr-crossstation@example.edu", "x")
    _assign_corrector(event_id, "corr-crossstation@example.edu", [station_a])
    staff_id = _corrector_staff_id(event_id, "corr-crossstation@example.edu")

    blocked = auth_client.patch(
        f"/api/staff/{staff_id}",
        json={"role_code": "corrector", "station_ids": [other_station]},
    )
    assert blocked.status_code == 400


def test_corrector_requires_at_least_one_station(auth_client):
    login(auth_client, ADMIN)
    event_id, station_id, _, _ = _make_event(deferred=True)
    _account("corr-nostation@example.edu", "x")
    response = auth_client.post("/api/staff", json={
        "ecoe_event_id": event_id,
        "name": "Sin", "last_name": "Estación",
        "email": "corr-nostation@example.edu",
        "role_code": "corrector",
        "station_ids": [],
    })
    assert response.status_code == 400


def test_evaluator_cannot_delegate_corrector(client, db_factory):
    login(client, ADMIN)
    event_id, station_id, _, _ = _make_event(deferred=True)
    password = secrets.token_urlsafe(24)
    with db_factory() as db:
        role = db.scalar(select(Role).where(Role.code == RoleCode.miembro.value))
        db.add(User(email="lonely-eval@example.edu", full_name="Eval",
                    hashed_password=get_password_hash(password), role_id=role.id, is_active=True))
        db.add(StaffAssignment(
            ecoe_event_id=event_id, name="Eval", last_name="Solo",
            email="lonely-eval@example.edu", role_code=RoleCode.evaluador.value,
            station_ids=[station_id],
        ))
        db.commit()
    _account("target-corr@example.edu", "y")
    login(client, ("lonely-eval@example.edu", password))
    response = client.post("/api/staff", json={
        "ecoe_event_id": event_id, "name": "T", "last_name": "C",
        "email": "target-corr@example.edu", "role_code": "corrector",
        "station_ids": [station_id],
    })
    assert response.status_code == 403


# ── Corrección acotada a las estaciones asignadas ──────────────────────

def test_corrector_grades_only_assigned_station_and_feeds_results(auth_client, client):
    login(auth_client, ADMIN)
    event_id, station_id, student_id, checkin_id = _make_event(deferred=True)
    response_id = _submit(auth_client, event_id, station_id, student_id, checkin_id)

    password = secrets.token_urlsafe(24)
    _account("corr-ok@example.edu", password)
    _assign_corrector(event_id, "corr-ok@example.edu", [station_id])

    login(client, ("corr-ok@example.edu", password))
    listing = client.get(f"/api/grading/{event_id}")
    assert listing.status_code == 200
    assert listing.json()["pending_count"] == 1

    graded = client.post(f"/api/grading/responses/{response_id}", json={"scores": {"question_1": 5}})
    assert graded.status_code == 200, graded.text
    assert graded.json()["score_obtained"] == 5

    with TestingSessionLocal() as db:
        row = next(r for r in compute_results(db, event_id) if r["student_id"] == student_id)
    assert row["total_score"] == 5
    assert row["max_score"] == 6


def test_corrector_cannot_grade_unassigned_station(auth_client, client):
    login(auth_client, ADMIN)
    event_id, station_id, student_id, checkin_id = _make_event(deferred=True)
    response_id = _submit(auth_client, event_id, station_id, student_id, checkin_id)

    password = secrets.token_urlsafe(24)
    _account("corr-scope@example.edu", password)
    _assign_corrector(event_id, "corr-scope@example.edu", [999_999])

    login(client, ("corr-scope@example.edu", password))
    assert client.get(f"/api/grading/{event_id}").json()["responses"] == []
    blocked = client.post(f"/api/grading/responses/{response_id}", json={"scores": {"question_1": 3}})
    assert blocked.status_code == 403


def test_corrector_is_event_scoped(auth_client, client):
    login(auth_client, ADMIN)
    event_a, station_a, student_a, checkin_a = _make_event(deferred=True)
    event_b, _, _, _ = _make_event(deferred=True)

    password = secrets.token_urlsafe(24)
    _account("corr-a@example.edu", password)
    _assign_corrector(event_a, "corr-a@example.edu", [station_a])

    login(client, ("corr-a@example.edu", password))
    assert client.get(f"/api/grading/{event_b}").status_code == 403


def test_corrector_has_no_access_to_other_operational_screens(auth_client, client):
    login(auth_client, ADMIN)
    event_id, station_id, student_id, checkin_id = _make_event(deferred=True)
    password = secrets.token_urlsafe(24)
    _account("corr-narrow@example.edu", password)
    _assign_corrector(event_id, "corr-narrow@example.edu", [station_id])

    login(client, ("corr-narrow@example.edu", password))
    assert client.get(f"/api/results/{event_id}").status_code == 403
    assert client.get(f"/api/live/{event_id}").status_code == 403
    assert client.get(f"/api/students/{event_id}").status_code == 403
    assert client.get(f"/api/evaluator/context/{event_id}").status_code == 403
    assert client.get(f"/api/dashboard/{event_id}").status_code == 403
    # Pero sí puede leer el ECOE al que está asignado (contexto de la pantalla
    # Corrección) y sus roles efectivos.
    assert client.get(f"/api/ecoe/{event_id}").status_code == 200
    assert client.get(f"/api/ecoe/{event_id}/roles/me").status_code == 200


# ── Validación ────────────────────────────────────────────────────────

def _validation(event_id: int) -> dict:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        return compute_ecoe_validation(db, event)


def test_deferred_station_without_corrector_blocks_publication(auth_client):
    login(auth_client, ADMIN)
    event_id, station_id, _, _ = _make_event(deferred=True)
    report = _validation(event_id)
    blockers = " ".join(
        b for issue in report["station_issues"] for b in issue["blockers"]
    )
    assert "corrector asignado" in blockers
    assert report["deferred_grading_ready"] is False
    assert report["can_publish"] is False


def test_deferred_station_with_corrector_and_manual_question_is_ready(auth_client):
    login(auth_client, ADMIN)
    event_id, station_id, _, _ = _make_event(deferred=True)
    _account("corr-ready@example.edu", "z")
    _assign_corrector(event_id, "corr-ready@example.edu", [station_id])
    report = _validation(event_id)
    assert report["deferred_grading_ready"] is True
    station_issue = report["station_issues"][0]
    assert not any("corrector" in b for b in station_issue["blockers"])


def test_deferred_flag_without_manual_question_blocks(auth_client):
    login(auth_client, ADMIN)
    event_id, station_id, _, _ = _make_event(
        deferred=True,
        form={"questions": [
            {"type": "single_choice", "label": "x", "options": ["a", "b"],
             "points": 4, "correct_option": "a"},
        ]},
    )
    _account("corr-auto@example.edu", "z")
    _assign_corrector(event_id, "corr-auto@example.edu", [station_id])
    report = _validation(event_id)
    blockers = " ".join(
        b for issue in report["station_issues"] for b in issue["blockers"]
    )
    assert "corrección manual con puntaje" in blockers


def test_pending_deferred_grading_keeps_student_partial_and_is_reported(auth_client):
    login(auth_client, ADMIN)
    event_id, station_id, student_id, checkin_id = _make_event(deferred=True)
    _account("corr-pending@example.edu", "z")
    _assign_corrector(event_id, "corr-pending@example.edu", [station_id])
    _submit(auth_client, event_id, station_id, student_id, checkin_id)

    report = _validation(event_id)
    assert report["pending_deferred_grading_stations"] == [1]

    with TestingSessionLocal() as db:
        trace = build_traceability_report(db, event_id)
    row = next(r for r in trace["student_traceability"] if r["student_id"] == student_id)
    assert row["pending_deferred_gradings"] == 1
    assert row["completion_status"] == "parcial"
