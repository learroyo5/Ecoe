"""Server-authoritative live timer (A2)."""

import time


class TestLiveTimerWebSocket:
    def test_authenticated_user_with_event_access_can_connect_and_receives_broadcast(
        self, auth_client,
    ):
        """Regression test for a false alarm during the 2026-07-08 deploy:
        an unauthenticated handshake correctly gets HTTP 403 (uvicorn turns
        a pre-accept websocket.close() into a 403), which was misread as a
        broken WebSocket. This proves the real, authenticated path works:
        the connection is accepted and timer_update broadcasts arrive.
        """
        with auth_client.websocket_connect("/api/ws/live/1") as ws:
            auth_client.post("/api/live/control", json={
                "ecoe_event_id": 1,
                "action": "start",
            })
            message = ws.receive_json()
            assert message["type"] == "timer_update"
            assert message["ecoe_event_id"] == 1
            assert message["status"] == "running"


class TestLiveTimer:
    def test_start_sets_server_side_phase(self, auth_client):
        response = auth_client.post("/api/live/control", json={
            "ecoe_event_id": 1,
            "action": "start",
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "running"
        assert data["remaining_seconds"] == data["station_time_seconds"]
        assert data["phase_started_at"] is not None
        assert data["server_now"] is not None

    def test_remaining_decreases_with_server_clock(self, auth_client):
        start = auth_client.post("/api/live/control", json={
            "ecoe_event_id": 1,
            "action": "start",
        }).json()
        time.sleep(1.2)
        current = auth_client.get("/api/live/1").json()
        assert current["remaining_seconds"] < start["remaining_seconds"]

    def test_pause_freezes_remaining(self, auth_client):
        auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
        time.sleep(1.2)
        paused = auth_client.post("/api/live/control", json={
            "ecoe_event_id": 1,
            "action": "pause",
        }).json()
        assert paused["status"] == "paused"
        assert paused["phase_started_at"] is None
        assert paused["remaining_seconds"] < paused["station_time_seconds"]

        time.sleep(1.1)
        still_paused = auth_client.get("/api/live/1").json()
        assert still_paused["remaining_seconds"] == paused["remaining_seconds"]

    def test_reset_restores_full_time(self, auth_client):
        auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
        reset = auth_client.post("/api/live/control", json={
            "ecoe_event_id": 1,
            "action": "reset",
        }).json()
        assert reset["status"] == "ready"
        assert reset["remaining_seconds"] == reset["station_time_seconds"]
        assert reset["phase_started_at"] is None
        assert reset["current_station_index"] == 1

    def test_transition_uses_transition_time(self, auth_client):
        auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
        transition = auth_client.post("/api/live/control", json={
            "ecoe_event_id": 1,
            "action": "next_transition",
        }).json()
        assert transition["status"] == "transition"
        assert transition["remaining_seconds"] == transition["transition_time_seconds"]
        assert transition["current_station_index"] == 2

        # Leave the session in a clean state for other tests.
        auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
