"""F0.3 / F0.4 / F0.7 (auditoría SaaS: resto de H04, H08, parte de H13)."""

import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

import app.api.routes.operational as operational
from app.models.entities import AuditLog, ECOEResult, ECOEResultVersion, User
from conftest import ADMIN, COORDINATOR, STUDENT, TestingSessionLocal, login
from test_proc04_closure import _build, _payload, _score


def _close_complete_event(auth_client) -> dict:
    ctx = _build()
    for station_id in ctx["stations"]["Circuito A"]:
        _score(ctx, ctx["students"][0], station_id, 10)
    assert auth_client.put(
        f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "cerrado")
    ).status_code == 200
    return ctx


def _reopen(auth_client, ctx: dict, reason: str):
    return auth_client.put(
        f"/api/ecoe/{ctx['event_id']}",
        json=_payload(ctx["event_id"], "en_ejecucion", transition_reason=reason),
    )


# ── F0.3: acta versionada ─────────────────────────────────────────────


def test_reopening_archives_the_acta_it_replaces(auth_client):
    ctx = _close_complete_event(auth_client)
    assert _reopen(auth_client, ctx, "Faltó transcribir una pauta en papel").status_code == 200

    body = auth_client.get(f"/api/results/{ctx['event_id']}/versions").json()
    assert len(body["versions"]) == 1
    version = body["versions"][0]
    assert version["version"] == 1
    assert version["reason"] == "Faltó transcribir una pauta en papel"
    assert version["superseded_by_email"] == ADMIN[0]
    assert version["results"][0]["percentage"] == 100.0
    assert version["results"][0]["ecoe_number"] == "E001"
    assert len(version["station_results"]) == 2
    with TestingSessionLocal() as db:  # el acta vigente sí quedó invalidada
        assert db.scalars(select(ECOEResult).where(
            ECOEResult.ecoe_event_id == ctx["event_id"])).all() == []


def test_each_reopening_adds_a_version_and_keeps_the_previous_ones(auth_client):
    ctx = _close_complete_event(auth_client)
    _reopen(auth_client, ctx, "Primera reapertura por papel faltante")
    auth_client.put(f"/api/ecoe/{ctx['event_id']}", json=_payload(ctx["event_id"], "cerrado"))
    _reopen(auth_client, ctx, "Segunda reapertura por rectificación")

    versions = auth_client.get(f"/api/results/{ctx['event_id']}/versions").json()["versions"]
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[1]["reason"].startswith("Primera")


def test_rejected_reopening_archives_nothing(auth_client):
    ctx = _close_complete_event(auth_client)
    assert _reopen(auth_client, ctx, "corto").status_code == 400
    with TestingSessionLocal() as db:
        assert db.scalars(select(ECOEResultVersion).where(
            ECOEResultVersion.ecoe_event_id == ctx["event_id"])).all() == []


def test_versions_are_not_visible_to_students(client, auth_client):
    ctx = _close_complete_event(auth_client)
    login(client, STUDENT)
    assert client.get(f"/api/results/{ctx['event_id']}/versions").status_code == 403
    login(client, ADMIN)


# ── F0.4: sockets y revocación ────────────────────────────────────────


@pytest.fixture
def fast_ws_revalidation(monkeypatch):
    monkeypatch.setattr(operational, "WS_REVALIDATE_SECONDS", 0.2)


def _set_active(email: str, active: bool) -> None:
    with TestingSessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        user.is_active = active
        user.account_status = "active" if active else "suspended"
        user.token_version = (user.token_version or 0) + 1
        db.commit()


def test_open_socket_is_closed_once_the_account_is_suspended(client, fast_ws_revalidation):
    login(client, COORDINATOR)
    try:
        with client.websocket_connect("/api/ws/live/1") as ws:
            ws.send_text("ping")  # con la cuenta vigente el canal sigue abierto
            _set_active(COORDINATOR[0], False)
            with pytest.raises(WebSocketDisconnect):
                for _ in range(20):
                    ws.receive_text()
    finally:
        _set_active(COORDINATOR[0], True)


def test_socket_of_a_valid_session_survives_revalidation(auth_client, fast_ws_revalidation):
    import time

    with auth_client.websocket_connect("/api/ws/live/1") as ws:
        time.sleep(0.7)  # varias revalidaciones
        ws.send_text("ping")
        auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
        assert ws.receive_json()["type"] == "timer_update"


# ── F0.7: auditoría sin datos personales de más ───────────────────────


def test_deleting_a_student_does_not_copy_rut_or_name_into_the_audit_log(auth_client):
    from app.models.entities import Student
    from test_opt20_f2_deadline_and_sweep import _build_event

    ctx = _build_event(status="en_configuracion")
    with TestingSessionLocal() as db:
        student = db.get(Student, ctx["student_id"])
        rut, name = student.rut, student.name
    assert auth_client.delete(f"/api/students/{ctx['student_id']}").status_code == 200
    with TestingSessionLocal() as db:
        log = db.scalar(select(AuditLog).where(
            AuditLog.action == "delete_student", AuditLog.target_id == str(ctx["student_id"])))
        assert log is not None
        assert rut not in str(log.payload) and name not in str(log.payload)
        assert log.payload["ecoe_number"] == "001"


# ── F0.6: uploads ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("demo_event_in_setup")
def test_oversized_upload_is_rejected_without_reading_it_whole(auth_client, monkeypatch):
    import app.api.routes.operational as routes

    monkeypatch.setattr(routes, "MAX_MEDIA_SIZE_BYTES", 1024)
    seen: list[int] = []
    from starlette.datastructures import UploadFile as StarletteUploadFile

    original = StarletteUploadFile.read

    async def spy(self, size: int = -1):
        seen.append(size)
        return await original(self, size)

    monkeypatch.setattr(StarletteUploadFile, "read", spy)
    response = auth_client.post(
        "/api/media/upload?ecoe_event_id=1&station_id=1",
        files={"file": ("grande.png", b"\x89PNG\r\n\x1a\n" + b"0" * 5000, "image/png")},
    )
    assert response.status_code == 400
    # Nunca se pidió el archivo completo: a lo más el límite + 1 byte.
    assert seen and all(0 < size <= 1025 for size in seen)


@pytest.mark.usefixtures("demo_event_in_setup")
def test_media_is_served_with_nosniff(auth_client):
    uploaded = auth_client.post(
        "/api/media/upload?ecoe_event_id=1&station_id=1&target_viewer=evaluador",
        files={"file": ("foto.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    served = auth_client.get(f"/api/media/file/{uploaded.json()['id']}")
    assert served.status_code == 200
    assert served.headers["x-content-type-options"] == "nosniff"
