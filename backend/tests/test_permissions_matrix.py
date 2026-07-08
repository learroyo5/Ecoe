"""Role × endpoint permission matrix over the seeded demo event."""

import pytest

from conftest import ADMIN, COEDITOR, COORDINATOR, EVALUATOR, STUDENT, TIMER, login

# (credentials, id, method, path, expected_status)
MATRIX = [
    # Users management is admin-only
    (ADMIN, "admin", "GET", "/api/users", 200),
    (COEDITOR, "coeditor", "GET", "/api/users", 403),
    (COORDINATOR, "coordinador", "GET", "/api/users", 403),
    (EVALUATOR, "evaluador", "GET", "/api/users", 403),
    (STUDENT, "estudiante", "GET", "/api/users", 403),
    (TIMER, "cronometrador", "GET", "/api/users", 403),
    # Student roster
    (ADMIN, "admin", "GET", "/api/students/1", 200),
    (COORDINATOR, "coordinador", "GET", "/api/students/1", 200),
    (EVALUATOR, "evaluador", "GET", "/api/students/1", 403),
    (STUDENT, "estudiante", "GET", "/api/students/1", 403),
    (TIMER, "cronometrador", "GET", "/api/students/1", 403),
    # Live panel: operational roles only
    (ADMIN, "admin", "GET", "/api/live/1", 200),
    (COORDINATOR, "coordinador", "GET", "/api/live/1", 200),
    (TIMER, "cronometrador", "GET", "/api/live/1", 200),
    (EVALUATOR, "evaluador", "GET", "/api/live/1", 403),
    (STUDENT, "estudiante", "GET", "/api/live/1", 403),
    # Event detail is visible to every role enrolled in the event
    (ADMIN, "admin", "GET", "/api/ecoe/1", 200),
    (COEDITOR, "coeditor", "GET", "/api/ecoe/1", 200),
    (EVALUATOR, "evaluador", "GET", "/api/ecoe/1", 200),
    (STUDENT, "estudiante", "GET", "/api/ecoe/1", 200),
    (TIMER, "cronometrador", "GET", "/api/ecoe/1", 200),
    # Evaluator workflow context
    (EVALUATOR, "evaluador", "GET", "/api/evaluator/context/1", 200),
    (STUDENT, "estudiante", "GET", "/api/evaluator/context/1", 403),
    # Results are for event managers
    (ADMIN, "admin", "GET", "/api/results/1", 200),
    (COORDINATOR, "coordinador", "GET", "/api/results/1", 200),
    (EVALUATOR, "evaluador", "GET", "/api/results/1", 403),
    (STUDENT, "estudiante", "GET", "/api/results/1", 403),
]


@pytest.mark.parametrize(
    "credentials,method,path,expected",
    [(c, m, p, e) for c, _rid, m, p, e in MATRIX],
    ids=[f"{rid}-{m}-{p}-{e}" for _c, rid, m, p, e in MATRIX],
)
def test_permission_matrix(client, credentials, method, path, expected):
    login(client, credentials)
    response = client.request(method, path)
    assert response.status_code == expected, response.text


def test_ecoe_creation_is_admin_only(client):
    payload = {
        "name": "ECOE Matrix",
        "date": "2026-09-01",
        "course_name": "Curso",
        "school_name": "Escuela",
        "responsible_teacher": "Docente",
        "contact_email": "m@ecoe.cl",
        "circuit_mode": "paralelo_espejo",
        "total_stations": 2,
        "station_time_minutes": 8,
        "transition_time_minutes": 2,
        "total_students": 5,
        "total_groups": 1,
        "passing_reference_percent": 60,
    }
    for credentials in (COEDITOR, COORDINATOR, EVALUATOR, STUDENT, TIMER):
        login(client, credentials)
        response = client.post("/api/ecoe", json=payload)
        assert response.status_code == 403, f"{credentials[0]} pudo crear un ECOE"

    login(client, ADMIN)
    response = client.post("/api/ecoe", json=payload)
    assert response.status_code == 200
