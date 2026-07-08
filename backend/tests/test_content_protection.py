"""Exam content must not be readable by students/evaluators/timers (C2).

Instruments contain the evaluation checklists and simulated patients contain
the key answers: leaking them compromises the exam.
"""

import pytest

from conftest import ADMIN, COEDITOR, COORDINATOR, EVALUATOR, STUDENT, TIMER, login

CONTENT_ENDPOINTS = [
    "/api/templates",
    "/api/instruments",
    "/api/simulated-patients",
    "/api/station-bank",
]


class TestContentProtection:
    @pytest.mark.parametrize("endpoint", CONTENT_ENDPOINTS)
    @pytest.mark.parametrize("credentials", [STUDENT, EVALUATOR, TIMER],
                             ids=["estudiante", "evaluador", "cronometrador"])
    def test_operational_roles_cannot_read_exam_content(self, client, credentials, endpoint):
        login(client, credentials)
        response = client.get(endpoint)
        assert response.status_code == 403

    @pytest.mark.parametrize("endpoint", CONTENT_ENDPOINTS)
    @pytest.mark.parametrize("credentials", [ADMIN, COEDITOR, COORDINATOR],
                             ids=["admin", "coeditor", "coordinador"])
    def test_content_managers_can_read_exam_content(self, client, credentials, endpoint):
        login(client, credentials)
        response = client.get(endpoint)
        assert response.status_code == 200
