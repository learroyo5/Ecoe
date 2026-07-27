"""Pilot runs capture operational findings (notes)."""

from conftest import ADMIN, login


def test_pilotage_notes_lifecycle(auth_client):
    runs = auth_client.get("/api/pilotage/1")
    assert runs.status_code == 200, runs.text
    run_id = runs.json()[0]["id"]

    updated = auth_client.patch(
        f"/api/pilotage/{run_id}/notes",
        json={"notes": "  La estación 2 tomó 9 minutos reales; ajustar guion.  "},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["notes"] == "La estación 2 tomó 9 minutos reales; ajustar guion."

    listed = auth_client.get("/api/pilotage/1")
    row = next(item for item in listed.json() if item["id"] == run_id)
    assert "ajustar guion" in row["notes"]


def test_pilotage_notes_forbidden_for_evaluator(client):
    login(client, ADMIN)
    run_id = client.get("/api/pilotage/1").json()[0]["id"]
    login(client, ("eval1@ecoe.cl", "test-evaluator-password"))
    response = client.patch(f"/api/pilotage/{run_id}/notes", json={"notes": "x"})
    assert response.status_code == 403
