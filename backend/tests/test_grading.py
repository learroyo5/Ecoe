"""Scoring of student forms: auto-grading, manual grading, and results."""

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models.entities import ECOEEvent, Station, StationCheckIn, Student, StudentResponse
from app.models.enums import ECOEStatus
from app.services.results import compute_results
from conftest import ADMIN, COORDINATOR, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


SCORED_FORM = {
    "questions": [
        {
            "type": "single_choice",
            "label": "Diagnostico mas probable",
            "options": ["SCA", "TEP", "RGE"],
            "points": 4,
            "correct_option": "SCA",
        },
        {
            "type": "multiple_choice",
            "label": "Examenes iniciales",
            "options": ["ECG", "Troponinas", "Radiografia"],
            "points": 3,
            "correct_options": ["ECG", "Troponinas"],
        },
        {
            "type": "short_text",
            "label": "Justifica tu plan",
            "points": 3,
        },
    ]
}

AUTO_ONLY_FORM = {
    "questions": [
        {
            "type": "single_choice",
            "label": "Conducta inmediata",
            "options": ["A", "B"],
            "points": 5,
            "correct_option": "A",
        },
    ]
}


def _build_event(form_definition: dict) -> tuple[int, int, int, int]:
    """Fresh event in ejecucion with one form station, one student, one checkin."""
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="Grading",
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
            name="Formulario puntuado",
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
            max_score=0,
            student_form_definition=form_definition,
        )
        db.add(station)
        db.flush()
        student = Student(
            ecoe_event_id=event.id,
            name="Alumno",
            last_name="Puntaje",
            rut=f"40{event.id}00-1",
            email=f"grading{event.id}@example.edu",
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
            evaluator_email="eval1@ecoe.cl",
            evaluator_name="Evaluadora",
            status="confirmado",
            confirmed_at=_utcnow_naive(),
        )
        db.add(checkin)
        db.commit()
        return event.id, station.id, student.id, checkin.id


def test_choice_questions_autograde_on_submit(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(SCORED_FORM)
    response = auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        # single correcto (4), multiple incompleto (0), texto pendiente.
        "answers": {
            "question_1": "SCA",
            "question_2": ["ECG"],
            "question_3": "Porque el dolor es tipico",
        },
    })
    assert response.status_code == 200, response.text
    with TestingSessionLocal() as db:
        saved = db.get(StudentResponse, response.json()["response_id"])
        assert saved.max_score == 10
        assert saved.score_obtained is None  # texto manual pendiente
        assert saved.grading["question_1"]["earned"] == 4
        assert saved.grading["question_2"]["earned"] == 0
        assert saved.grading["question_3"]["earned"] is None


def test_auto_only_form_scores_immediately_and_feeds_results(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(AUTO_ONLY_FORM)
    response = auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        "answers": {"question_1": "A"},
    })
    assert response.status_code == 200, response.text
    with TestingSessionLocal() as db:
        saved = db.get(StudentResponse, response.json()["response_id"])
        assert saved.score_obtained == 5
        assert saved.max_score == 5
        assert saved.graded_by_email == "auto"
        results = compute_results(db, event_id)
    row = next(item for item in results if item["student_id"] == student_id)
    assert row["total_score"] == 5
    assert row["max_score"] == 5
    assert row["percentage"] == 100


def test_manual_grading_completes_score_and_results(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(SCORED_FORM)
    submitted = auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        "answers": {
            "question_1": "SCA",
            "question_2": ["ECG", "Troponinas"],
            "question_3": "Plan completo y justificado",
        },
    })
    response_id = submitted.json()["response_id"]

    # Antes de corregir: el formulario no aparece en resultados.
    with TestingSessionLocal() as db:
        results_before = compute_results(db, event_id)
    assert next(r for r in results_before if r["student_id"] == student_id)["max_score"] == 0

    listing = auth_client.get(f"/api/grading/{event_id}")
    assert listing.status_code == 200
    assert listing.json()["pending_count"] == 1
    row = next(r for r in listing.json()["responses"] if r["response_id"] == response_id)
    assert row["pending_questions"] == ["question_3"]

    graded = auth_client.post(
        f"/api/grading/responses/{response_id}",
        json={"scores": {"question_3": 2.5}},
    )
    assert graded.status_code == 200, graded.text
    assert graded.json()["score_obtained"] == 4 + 3 + 2.5

    with TestingSessionLocal() as db:
        results_after = compute_results(db, event_id)
    row_after = next(r for r in results_after if r["student_id"] == student_id)
    assert row_after["total_score"] == 9.5
    assert row_after["max_score"] == 10


def test_manual_grading_validations(auth_client):
    event_id, station_id, student_id, checkin_id = _build_event(SCORED_FORM)
    submitted = auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        "answers": {"question_1": "TEP", "question_3": "texto"},
    })
    response_id = submitted.json()["response_id"]

    over_max = auth_client.post(
        f"/api/grading/responses/{response_id}",
        json={"scores": {"question_3": 99}},
    )
    assert over_max.status_code == 400

    wrong_key = auth_client.post(
        f"/api/grading/responses/{response_id}",
        json={"scores": {"question_1": 1}},
    )
    assert wrong_key.status_code == 400


def test_grading_requires_content_manager_role(client):
    event_id, station_id, student_id, checkin_id = _build_event(SCORED_FORM)
    login(client, COORDINATOR)
    response = client.get(f"/api/grading/{event_id}")
    assert response.status_code == 403


def test_unscored_forms_keep_previous_behavior(auth_client):
    """Formularios sin puntos definidos no participan del consolidado."""
    event_id, station_id, student_id, checkin_id = _build_event(
        {"questions": [{"type": "single_choice", "label": "Sin puntos", "options": ["A", "B"]}]}
    )
    response = auth_client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        "answers": {"question_1": "A"},
    })
    assert response.status_code == 200
    with TestingSessionLocal() as db:
        saved = db.get(StudentResponse, response.json()["response_id"])
        assert saved.score_obtained is None
        assert saved.max_score is None
        assert saved.grading == {}
