"""OPT-15b — bulk "puntuar 0 los blancos de esta estación".

`POST /api/grading/{event}/stations/{station_id}/zero-blank` puntúa 0 los
autoenvíos realmente en blanco de una estación de una sola pasada. Incluye
negativos: no toca otra estación, ni respuestas fuera del scope del corrector,
ni respuestas ya puntuadas, ni autoenvíos con contenido, ni respuestas manuales;
rechaza el evento cerrado (409) y deja un `AuditLog` por respuesta.
"""

import secrets
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models.entities import (
    AuditLog,
    ECOEEvent,
    Station,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.grading import apply_auto_grading
from conftest import ADMIN, TestingSessionLocal, login
from test_deferred_grading import _account, _assign_corrector


MANUAL_FORM = {"questions": [{"type": "short_text", "label": "Interpreta", "points": 6}]}


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_event(*, stations: int = 2, status: str = ECOEStatus.en_ejecucion.value):
    """Evento con N estaciones de corrección diferida y un estudiante por estación.

    Devuelve ``(event_id, [station_id, ...], [student_id, ...])``.
    """
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Bulk cero",
            date=date(2026, 12, 10),
            course_name="Curso",
            school_name="Escuela",
            responsible_teacher="Docente",
            contact_email="docente@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=stations,
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=stations,
            total_groups=1,
            passing_reference_percent=60,
            status=status,
        )
        db.add(event)
        db.flush()
        station_ids: list[int] = []
        student_ids: list[int] = []
        for number in range(1, stations + 1):
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
            )
            db.add(station)
            db.flush()
            station_ids.append(station.id)
            student = Student(
                ecoe_event_id=event.id,
                name=f"Alumna{number}",
                last_name="Bulk",
                rut=f"6{event.id}{number}0-1",
                email=f"bulk{event.id}-{number}@example.edu",
                ecoe_number=f"{number}01",
                group_name="G1",
                circuit_name="Circuito A",
                is_active=True,
            )
            db.add(student)
            db.flush()
            student_ids.append(student.id)
        db.commit()
        return event.id, station_ids, student_ids


def _add_response(
    event_id: int,
    station_id: int,
    student_id: int,
    *,
    answers: dict,
    submission_kind: str,
) -> int:
    """Inserta una `StudentResponse` de ejecución con autocorrección aplicada."""
    with TestingSessionLocal() as db:
        station = db.get(Station, station_id)
        response = StudentResponse(
            ecoe_event_id=event_id,
            station_id=station_id,
            student_id=student_id,
            mode=SessionMode.ejecucion.value,
            answers=answers,
            submitted_at=_utcnow_naive(),
            by_contingency=False,
            submission_kind=submission_kind,
        )
        apply_auto_grading(response, station.student_form_definition)
        db.add(response)
        db.commit()
        db.refresh(response)
        return response.id


def _response(response_id: int) -> StudentResponse:
    with TestingSessionLocal() as db:
        return db.get(StudentResponse, response_id)


def _corrector(event_id: int, email: str, station_ids: list[int]) -> tuple[str, str]:
    password = secrets.token_urlsafe(24)
    _account(email, password)
    _assign_corrector(event_id, email, station_ids)
    return email, password


# ── Negativos ─────────────────────────────────────────────────────────

def test_zero_blank_only_touches_target_station(auth_client, client):
    login(auth_client, ADMIN)
    event_id, (station_a, station_b), (student_a, student_b) = _make_event()
    blank_a = _add_response(event_id, station_a, student_a, answers={}, submission_kind="auto")
    blank_b = _add_response(event_id, station_b, student_b, answers={}, submission_kind="auto")

    email, password = _corrector(event_id, "corr-bulk-a@example.edu", [station_a, station_b])
    login(client, (email, password))

    body = client.post(f"/api/grading/{event_id}/stations/{station_a}/zero-blank")
    assert body.status_code == 200, body.text
    assert body.json()["zeroed"] == 1
    assert body.json()["response_ids"] == [blank_a]

    assert _response(blank_a).score_obtained == 0
    assert _response(blank_b).score_obtained is None  # B intacta


def test_zero_blank_station_outside_corrector_scope_returns_403(auth_client, client):
    login(auth_client, ADMIN)
    event_id, (station_a, station_b), (student_a, student_b) = _make_event()
    blank_b = _add_response(event_id, station_b, student_b, answers={}, submission_kind="auto")

    email, password = _corrector(event_id, "corr-bulk-scope@example.edu", [station_a])
    login(client, (email, password))

    blocked = client.post(f"/api/grading/{event_id}/stations/{station_b}/zero-blank")
    assert blocked.status_code == 403
    assert _response(blank_b).score_obtained is None


def test_zero_blank_after_close_returns_409(auth_client):
    login(auth_client, ADMIN)
    event_id, (station_a, _), (student_a, _) = _make_event()
    blank_a = _add_response(event_id, station_a, student_a, answers={}, submission_kind="auto")
    with TestingSessionLocal() as db:
        db.get(ECOEEvent, event_id).status = ECOEStatus.cerrado.value
        db.commit()

    blocked = auth_client.post(f"/api/grading/{event_id}/stations/{station_a}/zero-blank")
    assert blocked.status_code == 409
    assert _response(blank_a).score_obtained is None


def test_zero_blank_skips_non_blank_and_non_auto(auth_client):
    login(auth_client, ADMIN)
    event_id, [station_a], [student_a] = _make_event(stations=1)
    # Tres respuestas en la MISMA estación: manual con contenido, auto con
    # contenido, y auto totalmente en blanco. Solo la tercera se puntúa 0.
    _make_extra_students(event_id, station_a, count=2)
    students = _students(event_id)
    manual_row = _add_response(
        event_id, station_a, students[0], answers={"question_1": "algo"}, submission_kind="manual"
    )
    auto_answered = _add_response(
        event_id, station_a, students[1], answers={"question_1": "algo"}, submission_kind="auto"
    )
    blank_auto = _add_response(
        event_id, station_a, students[2], answers={}, submission_kind="auto"
    )

    body = auth_client.post(f"/api/grading/{event_id}/stations/{station_a}/zero-blank")
    assert body.status_code == 200, body.text
    assert body.json()["zeroed"] == 1
    assert body.json()["response_ids"] == [blank_auto]

    assert _response(manual_row).score_obtained is None
    assert _response(auto_answered).score_obtained is None
    assert _response(blank_auto).score_obtained == 0


def test_zero_blank_does_not_regrade_resolved(auth_client):
    login(auth_client, ADMIN)
    event_id, [station_a], [student_a] = _make_event(stations=1)
    _make_extra_students(event_id, station_a, count=1)
    students = _students(event_id)
    already = _add_response(event_id, station_a, students[0], answers={}, submission_kind="auto")
    fresh_blank = _add_response(event_id, station_a, students[1], answers={}, submission_kind="auto")

    graded = auth_client.post(
        f"/api/grading/responses/{already}", json={"scores": {"question_1": 4}}
    )
    assert graded.status_code == 200, graded.text

    body = auth_client.post(f"/api/grading/{event_id}/stations/{station_a}/zero-blank")
    assert body.status_code == 200, body.text
    # La ya corregida no se toca (su nota sigue en 4); solo la nueva pasa a 0.
    assert body.json()["zeroed"] == 1
    assert body.json()["response_ids"] == [fresh_blank]
    assert _response(already).score_obtained == 4
    assert _response(fresh_blank).score_obtained == 0


# ── Positivos ─────────────────────────────────────────────────────────

def test_zero_blank_scores_and_feeds_results(auth_client):
    from app.services.results import compute_results

    login(auth_client, ADMIN)
    event_id, [station_a], [student_a] = _make_event(stations=1)
    _add_response(event_id, station_a, student_a, answers={}, submission_kind="auto")

    auth_client.post(f"/api/grading/{event_id}/stations/{station_a}/zero-blank")

    with TestingSessionLocal() as db:
        row = next(r for r in compute_results(db, event_id) if r["student_id"] == student_a)
    assert row["total_score"] == 0
    assert row["max_score"] == 6


def test_zero_blank_writes_one_auditlog_per_response(auth_client):
    login(auth_client, ADMIN)
    event_id, [station_a], [student_a] = _make_event(stations=1)
    _make_extra_students(event_id, station_a, count=1)
    students = _students(event_id)
    ids = [
        _add_response(event_id, station_a, s, answers={}, submission_kind="auto")
        for s in students
    ]

    auth_client.post(f"/api/grading/{event_id}/stations/{station_a}/zero-blank")

    with TestingSessionLocal() as db:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.action == "grade_student_response",
                AuditLog.target_type == "StudentResponse",
            )
        ).all()
    bulk_logs = {
        log.target_id: log
        for log in logs
        if log.payload.get("bulk") == "zero_blank"
        and log.payload.get("ecoe_event_id") == event_id
    }
    assert set(bulk_logs) == {str(i) for i in ids}
    for log in bulk_logs.values():
        assert log.payload["station_id"] == station_a
        assert log.payload["score_obtained"] == 0


def test_zero_blank_returns_pending_remaining(auth_client):
    login(auth_client, ADMIN)
    event_id, [station_a], [student_a] = _make_event(stations=1)
    _make_extra_students(event_id, station_a, count=1)
    students = _students(event_id)
    _add_response(event_id, station_a, students[0], answers={}, submission_kind="auto")
    # Una manual con contenido que sigue pendiente tras el bulk.
    _add_response(
        event_id, station_a, students[1], answers={"question_1": "algo"}, submission_kind="manual"
    )

    body = auth_client.post(f"/api/grading/{event_id}/stations/{station_a}/zero-blank").json()
    assert body["zeroed"] == 1
    assert body["pending_remaining"] == 1


def test_zero_blank_no_candidates_is_noop(auth_client):
    login(auth_client, ADMIN)
    event_id, [station_a], [student_a] = _make_event(stations=1)
    _add_response(
        event_id, station_a, student_a, answers={"question_1": "algo"}, submission_kind="manual"
    )
    body = auth_client.post(f"/api/grading/{event_id}/stations/{station_a}/zero-blank").json()
    assert body == {"zeroed": 0, "response_ids": [], "pending_remaining": 1}


# ── helpers de fixtures ───────────────────────────────────────────────

def _make_extra_students(event_id: int, station_id: int, *, count: int) -> None:
    with TestingSessionLocal() as db:
        base = db.scalar(select(Student).where(Student.ecoe_event_id == event_id))
        existing = len(
            db.scalars(select(Student).where(Student.ecoe_event_id == event_id)).all()
        )
        for index in range(count):
            n = existing + index
            db.add(Student(
                ecoe_event_id=event_id,
                name=f"Extra{n}",
                last_name="Bulk",
                rut=f"7{event_id}{n}0-1",
                email=f"extra{event_id}-{n}@example.edu",
                ecoe_number=f"9{n}1",
                group_name="G1",
                circuit_name=base.circuit_name,
                is_active=True,
            ))
        db.commit()


def _students(event_id: int) -> list[int]:
    with TestingSessionLocal() as db:
        return [
            s.id
            for s in db.scalars(
                select(Student)
                .where(Student.ecoe_event_id == event_id)
                .order_by(Student.id.asc())
            ).all()
        ]
