"""El evaluador debe poder tipear `7` / `007` / `E007` indistintamente al hacer
check-in, y el número que asigna el sistema lleva el prefijo `E` (decisión del
usuario 2026-08-29). El seed usa `E001`..`E010` para el evento 1."""

from conftest import TestingSessionLocal
from app.models.entities import ECOEEvent, Student
from app.models.enums import ECOEStatus
from app.utils.helpers import (
    format_ecoe_number,
    find_student_by_ecoe_number,
    normalize_ecoe_lookup,
)


def test_normalize_ecoe_lookup_collapses_prefix_and_padding():
    for value in ("7", "007", "E007", "e007", "E7", " E007 "):
        assert normalize_ecoe_lookup(value) == "7", value
    assert normalize_ecoe_lookup("E042") == "42"
    assert normalize_ecoe_lookup("") == ""
    assert normalize_ecoe_lookup("MED-2026-007") == "med-2026-007"


def test_format_ecoe_number_uses_e_prefix():
    assert format_ecoe_number(7) == "E007"
    assert format_ecoe_number(7, 4) == "E0007"
    assert format_ecoe_number(123) == "E123"


def test_find_seeded_student_by_bare_digits():
    with TestingSessionLocal() as db:
        for typed in ("E003", "e003", "003", "3", "E3"):
            found = find_student_by_ecoe_number(db, 1, typed)
            assert found is not None and found.ecoe_number == "E003", typed
        assert find_student_by_ecoe_number(db, 1, "999") is None


def test_exact_match_wins_and_ambiguous_canonical_returns_none():
    with TestingSessionLocal() as db:
        a = Student(ecoe_event_id=1, name="Q", last_name="A", rut="49000000-1",
                    email="q5@test.cl", ecoe_number="Q5", group_name="G",
                    circuit_name="Circuito A")
        b = Student(ecoe_event_id=1, name="Q", last_name="B", rut="49000000-2",
                    email="q005@test.cl", ecoe_number="Q005", group_name="G",
                    circuit_name="Circuito A")
        db.add_all([a, b])
        db.commit()
        try:
            assert find_student_by_ecoe_number(db, 1, "Q5").ecoe_number == "Q5"
            assert find_student_by_ecoe_number(db, 1, "Q005").ecoe_number == "Q005"
            # canónico "5" == E005 == Q5 == Q005 -> ambiguo, sin match exacto -> None
            assert find_student_by_ecoe_number(db, 1, "5") is None
        finally:
            db.delete(db.get(Student, a.id))
            db.delete(db.get(Student, b.id))
            db.commit()


def test_checkin_by_bare_number_confirms_seeded_prefixed_student(auth_client):
    """Regresión: tipear `4` en el check-in encuentra al estudiante `E004`."""
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, 1)
        original_status = event.status
        event.status = ECOEStatus.en_pilotaje.value
        target_id = db.query(Student).filter_by(ecoe_event_id=1, ecoe_number="E004").one().id
        db.commit()
    try:
        for typed in ("E004", "004", "4"):
            resp = auth_client.post("/api/station-checkins/confirm", json={
                "ecoe_event_id": 1, "station_id": 1, "ecoe_number": typed,
            })
            assert resp.status_code == 200, f"{typed}: {resp.text}"
            assert resp.json()["student_id"] == target_id
    finally:
        with TestingSessionLocal() as db:
            db.get(ECOEEvent, 1).status = original_status
            db.commit()
