"""Access-reset flow for event members already active (Reiniciar acceso)."""

import secrets

from conftest import ADMIN, login
from test_event_member_invitations import (
    create_delegated_admin,
    create_event_and_station,
    invite_payload,
)


def invite_and_activate(client, event_id: int, station_id: int, role: str, label: str) -> tuple[str, str]:
    login(client, ADMIN)
    email = f"{label}-{secrets.token_hex(6)}@example.edu"
    response = client.post(
        "/api/event-members/invite",
        json=invite_payload(event_id, station_id, email, role=role),
    )
    assert response.status_code == 200, response.text
    token = response.json()["activation_token"]
    password = secrets.token_urlsafe(24)
    activated = client.post(
        "/api/auth/activate-invitation",
        json={"token": token, "password": password},
    )
    assert activated.status_code == 200, activated.text
    return email, password


def test_admin_resets_access_for_active_evaluator(client):
    event_id, station_id = create_event_and_station(client, "Reinicio de acceso")
    admin_credentials = create_delegated_admin(client, event_id, "reset-admin")
    evaluator_email, old_password = invite_and_activate(
        client, event_id, station_id, "evaluador", "evaluator"
    )

    login(client, admin_credentials)
    response = client.post(
        "/api/event-members/reset-access",
        json={"ecoe_event_id": event_id, "email": evaluator_email},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["status"] == "reset"
    assert body["email"] == evaluator_email
    new_token = body["activation_token"]

    # The old password still works until the new link is actually used.
    assert client.post(
        "/api/auth/login", json={"email": evaluator_email, "password": old_password}
    ).status_code == 200

    new_password = secrets.token_urlsafe(24)
    activated = client.post(
        "/api/auth/activate-invitation",
        json={"token": new_token, "password": new_password},
    )
    assert activated.status_code == 200, activated.text

    assert client.post(
        "/api/auth/login", json={"email": evaluator_email, "password": old_password}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": evaluator_email, "password": new_password}
    ).status_code == 200


def test_coeditor_can_reset_access_but_not_invite_new_accounts(client):
    event_id, station_id = create_event_and_station(client, "Reinicio via coeditor")
    evaluator_email, _ = invite_and_activate(client, event_id, station_id, "evaluador", "evaluator")
    coeditor_email, coeditor_password = invite_and_activate(
        client, event_id, station_id, "coeditor_docente", "coeditor"
    )

    login(client, (coeditor_email, coeditor_password))
    reset_response = client.post(
        "/api/event-members/reset-access",
        json={"ecoe_event_id": event_id, "email": evaluator_email},
    )
    assert reset_response.status_code == 200, reset_response.text

    forbidden = client.post(
        "/api/event-members/invite",
        json=invite_payload(event_id, station_id, f"new-{secrets.token_hex(4)}@example.edu"),
    )
    assert forbidden.status_code == 403


def test_reset_access_rejects_member_not_in_event(client):
    event_id, station_id = create_event_and_station(client, "Fuera del equipo")
    admin_credentials = create_delegated_admin(client, event_id, "outsider-admin")
    outsider_email = f"outsider-{secrets.token_hex(5)}@example.edu"

    login(client, ADMIN)
    created = client.post("/api/users", json={
        "email": outsider_email,
        "full_name": "Fuera del equipo",
        "password": secrets.token_urlsafe(24),
        "role_code": "miembro",
    })
    assert created.status_code == 200

    login(client, admin_credentials)
    response = client.post(
        "/api/event-members/reset-access",
        json={"ecoe_event_id": event_id, "email": outsider_email},
    )
    assert response.status_code == 404


def test_reset_access_rejects_pending_account(client):
    event_id, station_id = create_event_and_station(client, "Cuenta pendiente")
    admin_credentials = create_delegated_admin(client, event_id, "pending-admin")

    login(client, admin_credentials)
    pending_email = f"pending-{secrets.token_hex(5)}@example.edu"
    invited = client.post(
        "/api/event-members/invite",
        json=invite_payload(event_id, station_id, pending_email),
    )
    assert invited.status_code == 200, invited.text

    response = client.post(
        "/api/event-members/reset-access",
        json={"ecoe_event_id": event_id, "email": pending_email},
    )
    assert response.status_code == 400


def test_admin_cannot_reset_access_into_another_event(client):
    event_id, station_id = create_event_and_station(client, "Alcance propio reset")
    foreign_event_id, foreign_station_id = create_event_and_station(client, "Alcance ajeno reset")
    admin_credentials = create_delegated_admin(client, event_id, "cross-reset-admin")
    foreign_evaluator_email, _ = invite_and_activate(
        client, foreign_event_id, foreign_station_id, "evaluador", "foreign-evaluator"
    )

    login(client, admin_credentials)
    response = client.post(
        "/api/event-members/reset-access",
        json={"ecoe_event_id": foreign_event_id, "email": foreign_evaluator_email},
    )
    assert response.status_code == 403
