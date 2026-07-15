"""Event-scoped member onboarding and invitation lifecycle tests."""

import secrets
from datetime import timedelta

from sqlalchemy import func, select

from app.models.entities import Role, User, UserInvitation
from app.models.enums import RoleCode
from app.services.invitations import hash_invitation_token
from app.utils.clock import utcnow_naive
from conftest import ADMIN, login


def event_payload(name: str) -> dict:
    return {
        "name": name,
        "date": "2026-11-01",
        "course_name": "Curso invitaciones",
        "school_name": "Escuela",
        "responsible_teacher": "Responsable",
        "contact_email": "responsable@example.edu",
        "circuit_mode": "paralelo_espejo",
        "total_stations": 1,
        "station_time_minutes": 8,
        "transition_time_minutes": 2,
        "total_students": 1,
        "total_groups": 1,
        "passing_reference_percent": 60,
    }


def station_payload(event_id: int) -> dict:
    return {
        "ecoe_event_id": event_id,
        "station_number": 1,
        "name": "Estacion de invitacion",
        "station_type": "procedimental",
        "circuit_name": "Circuito A",
        "expected_outcomes": "Resultado",
        "student_activity": "Actividad",
        "pre_entry_instruction": "Ingreso",
        "evaluator_instruction": "Evaluar",
        "requires_evaluator": True,
        "max_score": 10,
    }


def create_event_and_station(client, name: str) -> tuple[int, int]:
    login(client, ADMIN)
    event_response = client.post("/api/ecoe", json=event_payload(name))
    assert event_response.status_code == 200, event_response.text
    event_id = event_response.json()["id"]
    station_response = client.post("/api/stations", json=station_payload(event_id))
    assert station_response.status_code == 200, station_response.text
    return event_id, station_response.json()["id"]


def create_delegated_admin(client, event_id: int, label: str) -> tuple[str, str]:
    login(client, ADMIN)
    email = f"{label}-{secrets.token_hex(6)}@example.edu"
    password = secrets.token_urlsafe(24)
    created = client.post("/api/users", json={
        "email": email,
        "full_name": f"Admin {label}",
        "password": password,
        "role_code": RoleCode.miembro.value,
    })
    assert created.status_code == 200, created.text
    grant = client.post(f"/api/ecoe/{event_id}/admins/{created.json()['id']}")
    assert grant.status_code == 200, grant.text
    return email, password


def invite_payload(event_id: int, station_id: int, email: str, role: str = "evaluador") -> dict:
    return {
        "ecoe_event_id": event_id,
        "name": "Persona",
        "last_name": "Invitada",
        "email": email,
        "role_code": role,
        "station_ids": [station_id] if role == "evaluador" else [],
    }


def test_event_admin_invites_activates_and_reuses_one_identity(client, db_factory):
    event_id, station_id = create_event_and_station(client, "Invitacion principal")
    admin_credentials = create_delegated_admin(client, event_id, "principal")
    invited_email = f"invitee-{secrets.token_hex(6)}@example.edu"

    login(client, admin_credentials)
    lookup = client.get(
        "/api/event-members/lookup",
        params={"ecoe_event_id": event_id, "email": invited_email},
    )
    assert lookup.status_code == 200
    assert lookup.json() == {"exists": False, "assigned_to_event": False}

    invitation = client.post(
        "/api/event-members/invite",
        json=invite_payload(event_id, station_id, invited_email),
    )
    assert invitation.status_code == 200, invitation.text
    assert invitation.headers["cache-control"] == "no-store"
    body = invitation.json()
    assert body["status"] == "invited"
    token = body["activation_token"]

    with db_factory() as db:
        account = db.scalar(select(User).where(func.lower(User.email) == invited_email))
        stored = db.scalar(
            select(UserInvitation).where(UserInvitation.user_id == account.id)
        )
        assert account.account_status == "pending"
        assert account.is_active is False
        assert stored.token_hash == hash_invitation_token(token)
        assert stored.token_hash != token

    assert client.post(
        "/api/auth/login",
        json={"email": invited_email, "password": secrets.token_urlsafe(24)},
    ).status_code == 401
    assert client.post(
        "/api/auth/activate-invitation",
        json={"token": token, "password": "short"},
    ).status_code == 422

    password = secrets.token_urlsafe(24)
    activated = client.post(
        "/api/auth/activate-invitation",
        json={"token": token, "password": password},
    )
    assert activated.status_code == 200, activated.text
    assert activated.headers["cache-control"] == "no-store"
    assert client.post(
        "/api/auth/activate-invitation",
        json={"token": token, "password": secrets.token_urlsafe(24)},
    ).status_code == 400

    login(client, (invited_email, password))
    assert client.get(f"/api/ecoe/{event_id}").status_code == 200
    roles = client.get(f"/api/ecoe/{event_id}/roles/me").json()["roles"]
    assert roles == [RoleCode.evaluador.value]
    assert client.get("/api/auth/me").json()["role"] == RoleCode.miembro.value

    second_event_id, _ = create_event_and_station(client, "Reutilizacion de identidad")
    second_admin = create_delegated_admin(client, second_event_id, "secundario")
    login(client, second_admin)
    assigned = client.post(
        "/api/event-members/invite",
        json=invite_payload(
            second_event_id,
            station_id,
            invited_email,
            role=RoleCode.coeditor_docente.value,
        ) | {"station_ids": []},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "assigned"
    assert "activation_token" not in assigned.json()

    login(client, (invited_email, password))
    second_roles = client.get(f"/api/ecoe/{second_event_id}/roles/me").json()["roles"]
    assert second_roles == [RoleCode.coeditor_docente.value]
    # A coeditor cannot use the administrator-only invitation endpoint.
    forbidden = client.post(
        "/api/event-members/invite",
        json=invite_payload(second_event_id, station_id, f"forbidden-{secrets.token_hex(4)}@example.edu"),
    )
    assert forbidden.status_code == 403


def test_event_admin_cannot_invite_into_another_event(client):
    own_event_id, own_station_id = create_event_and_station(client, "Alcance propio")
    foreign_event_id, _ = create_event_and_station(client, "Alcance ajeno")
    credentials = create_delegated_admin(client, own_event_id, "scoped")
    login(client, credentials)
    response = client.post(
        "/api/event-members/invite",
        json=invite_payload(
            foreign_event_id,
            own_station_id,
            f"cross-{secrets.token_hex(5)}@example.edu",
        ),
    )
    assert response.status_code == 403


def test_suspended_account_cannot_be_reactivated_by_event_admin(client):
    event_id, station_id = create_event_and_station(client, "Cuenta suspendida")
    credentials = create_delegated_admin(client, event_id, "suspension")
    suspended_email = f"suspended-{secrets.token_hex(5)}@example.edu"

    login(client, ADMIN)
    created = client.post("/api/users", json={
        "email": suspended_email,
        "full_name": "Cuenta suspendida",
        "password": secrets.token_urlsafe(24),
        "role_code": RoleCode.miembro.value,
    })
    assert created.status_code == 200
    assert client.patch(f"/api/users/{created.json()['id']}", json={"is_active": False}).status_code == 200

    login(client, credentials)
    response = client.post(
        "/api/event-members/invite",
        json=invite_payload(event_id, station_id, suspended_email),
    )
    assert response.status_code == 400
    assert "suspendida" in response.json()["detail"]


def test_expired_invitation_is_rejected(client, db_factory):
    event_id, station_id = create_event_and_station(client, "Invitacion expirada")
    credentials = create_delegated_admin(client, event_id, "expired")
    invited_email = f"expired-{secrets.token_hex(5)}@example.edu"
    login(client, credentials)
    response = client.post(
        "/api/event-members/invite",
        json=invite_payload(event_id, station_id, invited_email),
    )
    token = response.json()["activation_token"]
    with db_factory() as db:
        invitation = db.scalar(
            select(UserInvitation).where(
                UserInvitation.token_hash == hash_invitation_token(token)
            )
        )
        invitation.expires_at = utcnow_naive() - timedelta(seconds=1)
        db.add(invitation)
        db.commit()

    activation = client.post(
        "/api/auth/activate-invitation",
        json={"token": token, "password": secrets.token_urlsafe(24)},
    )
    assert activation.status_code == 400
