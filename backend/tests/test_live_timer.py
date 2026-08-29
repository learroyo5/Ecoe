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

    def test_timing_update_resyncs_existing_live_session(self, auth_client):
        """Regression: editing ECOE timing must not leave the running-session
        template (seconds) stuck at whatever it was when the session was
        first created."""
        auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
        original = auth_client.get("/api/live/1").json()
        try:
            updated = auth_client.patch("/api/ecoe/1/timing", json={
                "station_time_minutes": 3,
                "transition_time_minutes": 1,
                "sync_existing_stations": True,
            })
            assert updated.status_code == 200, updated.text

            session = auth_client.get("/api/live/1").json()
            assert session["station_time_seconds"] == 180
            assert session["transition_time_seconds"] == 60
            # Not running: the resync also refreshes the currently-displayed
            # remaining time, not just the template for the next start/reset.
            assert session["remaining_seconds"] == 180

            stations = auth_client.get("/api/stations/1").json()
            assert all(s["station_time_minutes"] == 3 for s in stations)
            assert all(s["transition_time_minutes"] == 1 for s in stations)
        finally:
            auth_client.patch("/api/ecoe/1/timing", json={
                "station_time_minutes": original["station_time_seconds"] / 60,
                "transition_time_minutes": original["transition_time_seconds"] / 60,
                "sync_existing_stations": True,
            })
            auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})

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


class TestLiveTimerHardening:
    """OPT-9 / H-vivo-8: /live/control must fail cleanly on a bad event and
    must not let next_transition run the circuit past its last station."""

    def test_control_on_missing_event_returns_404(self, auth_client):
        response = auth_client.post("/api/live/control", json={
            "ecoe_event_id": 999999,
            "action": "start",
        })
        assert response.status_code == 404, response.text

    def test_next_transition_stops_at_last_station(self, auth_client):
        stations = auth_client.get("/api/stations/1").json()
        slots = len({s["station_number"] for s in stations})
        assert slots >= 2

        auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
        try:
            # reset leaves the index at 1; slots-1 transitions move it to the
            # last slot, and the next one must be rejected.
            for _ in range(slots - 1):
                ok = auth_client.post("/api/live/control", json={
                    "ecoe_event_id": 1,
                    "action": "next_transition",
                })
                assert ok.status_code == 200, ok.text
            assert auth_client.get("/api/live/1").json()["current_station_index"] == slots

            blocked = auth_client.post("/api/live/control", json={
                "ecoe_event_id": 1,
                "action": "next_transition",
            })
            assert blocked.status_code == 409, blocked.text
            assert auth_client.get("/api/live/1").json()["current_station_index"] == slots
        finally:
            auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
