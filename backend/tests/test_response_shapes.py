"""Regression tests for response_model additions (quality item 5).

A response_model that omits a field the frontend relies on fails silently
(Pydantic just drops it, no error) unless something asserts the field is
still present in the JSON payload.
"""

from conftest import ADMIN, login


class TestStationResponseShape:
    def test_station_response_includes_server_computed_timing(self, auth_client):
        """station_time_minutes/transition_time_minutes are set server-side
        from the ECOEEvent, not part of StationCreate — a schema without
        them would silently drop these fields from every response."""
        response = auth_client.post("/api/stations", json={
            "ecoe_event_id": 1,
            "station_number": 1,
            "name": "Estacion Shape Test",
            "station_type": "procedimental",
            "circuit_name": "Circuito A",
            "expected_outcomes": "Resultado esperado",
            "student_activity": "",
            "student_station_instruction": "",
            "pre_entry_instruction": "",
            "evaluator_instruction": "",
            "max_score": 20,
            "materials": "",
            "multimedia_notes": "",
            "requires_evaluator": True,
            "requires_student_form": False,
            "uses_multimedia": False,
            "uses_simulated_patient": False,
            "uses_physical_resources": False,
            "contingency_ready": False,
            "student_form_definition": {"questions": []},
            "status": "en_diseno",
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert "station_time_minutes" in data
        assert "transition_time_minutes" in data
        assert data["station_time_minutes"] > 0

        list_response = auth_client.get("/api/stations/1")
        assert list_response.status_code == 200
        assert all("station_time_minutes" in s for s in list_response.json())


class TestInstrumentResponseShape:
    def test_instrument_response_includes_nested_item_ids(self, auth_client):
        """AssessmentToolRead.items must validate from ORM AssessmentItem
        objects (id, tool_id extras) — a plain AssessmentItemInput without
        from_attributes raises a 500 ResponseValidationError instead."""
        response = auth_client.post("/api/instruments", json={
            "name": "Instrumento Shape Test",
            "tool_type": "lista_cotejo",
            "max_score": 10,
            "free_observation": True,
            "items": [
                {"label": "Item 1", "score_per_item": 5, "order_index": 1},
                {"label": "Item 2", "score_per_item": 5, "order_index": 2},
            ],
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data["items"]) == 2
        assert all("id" in item for item in data["items"])

        list_response = auth_client.get("/api/instruments")
        assert list_response.status_code == 200
        assert any(tool["items"] for tool in list_response.json())


class TestMediaResponseShape:
    def test_media_upload_response_excludes_file_path(self, auth_client):
        """file_path (server disk path) must not leak in API responses."""
        response = auth_client.post(
            "/api/media/upload?ecoe_event_id=1&station_id=1&target_viewer=estudiante",
            files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "file_path" not in data
        assert data["original_name"] == "photo.png"

        list_response = auth_client.get("/api/media/1")
        assert list_response.status_code == 200
        assert all("file_path" not in asset for asset in list_response.json())
