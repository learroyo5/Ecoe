"""Negative authorization tests for cross-event and mixed-role bypasses."""

import secrets

import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.core.security import get_password_hash
from app.models.entities import ECOEEvent, Role, StaffAssignment, StationCheckIn, Student, User
from app.models.enums import ECOEStatus, RoleCode
from conftest import ADMIN, COEDITOR, COORDINATOR, login


def set_event_status(db, event_id: int, status: str) -> None:
    """Force the lifecycle state directly: tests exercise authorization,
    not the transition graph (covered in test_state_machine_and_modes)."""
    event = db.get(ECOEEvent, event_id)
    event.status = status
    db.add(event)


def event_payload(name: str) -> dict:
    return {
        "name": name,
        "date": "2026-10-01",
        "course_name": "Curso",
        "school_name": "Escuela",
        "responsible_teacher": "Docente",
        "contact_email": "docente@example.edu",
        "circuit_mode": "paralelo_espejo",
        "total_stations": 2,
        "station_time_minutes": 8,
        "transition_time_minutes": 2,
        "total_students": 2,
        "total_groups": 1,
        "passing_reference_percent": 60,
    }


def station_payload(event_id: int, name: str) -> dict:
    return {
        "ecoe_event_id": event_id,
        "station_number": 1,
        "name": name,
        "station_type": "procedimental",
        "circuit_name": "Circuito A",
        "expected_outcomes": "Resultado",
        "student_activity": "Actividad",
        "pre_entry_instruction": "Ingreso",
        "evaluator_instruction": "Evaluar",
        "requires_evaluator": True,
        "max_score": 10,
    }


def create_event(client, name: str) -> int:
    login(client, ADMIN)
    response = client.post("/api/ecoe", json=event_payload(name))
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_station(client, event_id: int, name: str) -> int:
    login(client, ADMIN)
    response = client.post("/api/stations", json=station_payload(event_id, name))
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_account(db_factory, email: str, role_code: str, password: str) -> User:
    with db_factory() as db:
        role = db.scalar(select(Role).where(Role.code == role_code))
        user = User(
            email=email,
            full_name=email.split("@", 1)[0],
            hashed_password=get_password_hash(password),
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def test_only_global_admin_manages_users_and_delegates_event_admin(client):
    event_id = create_event(client, "Delegacion institucional")
    password = secrets.token_urlsafe(24)
    created = client.post("/api/users", json={
        "email": "delegated-admin@example.edu",
        "full_name": "Admin delegado",
        "password": password,
        "role_code": RoleCode.coeditor_docente.value,
    })
    assert created.status_code == 200, created.text
    user_id = created.json()["id"]
    grant = client.post(f"/api/ecoe/{event_id}/admins/{user_id}")
    assert grant.status_code == 200, grant.text

    login(client, ("delegated-admin@example.edu", password))
    assert client.get(f"/api/ecoe/{event_id}").status_code == 200
    assert client.get("/api/users").status_code == 403
    assert client.post("/api/ecoe", json=event_payload("No permitido")).status_code == 403


def test_station_update_cannot_move_resource_to_another_event(client):
    target_event_id = create_event(client, "Destino no autorizado")
    login(client, COEDITOR)
    source = client.get("/api/stations/1").json()[0]
    source["ecoe_event_id"] = target_event_id
    response = client.put(f"/api/stations/{source['id']}", json=source)
    assert response.status_code == 400


def test_pdf_export_rejects_station_from_another_event(client):
    target_event_id = create_event(client, "PDF aislado")
    foreign_station_id = create_station(client, target_event_id, "Contenido reservado")
    login(client, COEDITOR)
    response = client.get(f"/api/results/1/export/pdf?station_id={foreign_station_id}")
    assert response.status_code == 404


def test_effective_evaluator_role_enforces_station_assignment(client, db_factory):
    event_id = create_event(client, "Evaluador multirrol")
    assigned_station_id = create_station(client, event_id, "Asignada")
    foreign_station_id = create_station(client, event_id, "No asignada")
    password = secrets.token_urlsafe(24)
    create_account(
        db_factory,
        "mixed-evaluator@example.edu",
        RoleCode.coeditor_docente.value,
        password,
    )
    with db_factory() as db:
        db.add(StaffAssignment(
            ecoe_event_id=event_id,
            name="Evaluador",
            last_name="Mixto",
            email="mixed-evaluator@example.edu",
            role_code=RoleCode.evaluador.value,
            station_ids=[assigned_station_id],
        ))
        # El gate de etapa exige en_pilotaje/en_ejecucion para registrar
        # check-ins; este test valida la autorizacion por asignacion.
        set_event_status(db, event_id, ECOEStatus.en_ejecucion.value)
        db.commit()

    login(client, ("mixed-evaluator@example.edu", password))
    response = client.post("/api/station-checkins/confirm", json={
        "ecoe_event_id": event_id,
        "station_id": foreign_station_id,
        "ecoe_number": "001",
    })
    assert response.status_code == 403


def test_student_only_event_relationship_cannot_submit_for_another_student(client, db_factory):
    event_id = create_event(client, "Estudiante multirrol")
    station_id = create_station(client, event_id, "Formulario")
    password = secrets.token_urlsafe(24)
    account = create_account(
        db_factory,
        "mixed-student@example.edu",
        RoleCode.coordinador_operativo.value,
        password,
    )
    with db_factory() as db:
        own = Student(
            ecoe_event_id=event_id, name="Propio", last_name="Alumno",
            rut="20000000-1", email=account.email, ecoe_number="001",
            group_name="G1", circuit_name="A", is_active=True,
        )
        victim = Student(
            ecoe_event_id=event_id, name="Otro", last_name="Alumno",
            rut="20000000-2", email="victim@example.edu", ecoe_number="002",
            group_name="G1", circuit_name="A", is_active=True,
        )
        db.add_all([own, victim])
        db.flush()
        checkin = StationCheckIn(
            ecoe_event_id=event_id,
            station_id=station_id,
            student_id=victim.id,
            evaluator_email="evaluator@example.edu",
            evaluator_name="Evaluador",
            status="confirmado",
        )
        db.add(checkin)
        # El gate de etapa exige en_pilotaje/en_ejecucion para aceptar
        # envios; este test valida la autorizacion de identidad.
        set_event_status(db, event_id, ECOEStatus.en_ejecucion.value)
        db.commit()
        db.refresh(victim)
        db.refresh(checkin)
        victim_id = victim.id
        checkin_id = checkin.id

    login(client, (account.email, password))
    response = client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": victim_id,
        "answers": {"answer": "forged"},
    })
    assert response.status_code == 403


def test_coordinator_cannot_delegate_content_or_coordinator_roles(client):
    login(client, COORDINATOR)
    for role_code in (RoleCode.coeditor_docente.value, RoleCode.coordinador_operativo.value):
        response = client.post("/api/staff", json={
            "ecoe_event_id": 1,
            "name": "Escalacion",
            "last_name": "No permitida",
            "email": f"{role_code}@example.edu",
            "role_code": role_code,
            "station_ids": [],
        })
        assert response.status_code == 403


def test_content_library_and_incident_station_are_scoped_to_event(client):
    target_event_id = create_event(client, "Contenido aislado")
    foreign_station_id = create_station(client, target_event_id, "Estacion ajena")

    login(client, COEDITOR)
    assert client.get(f"/api/templates?ecoe_event_id={target_event_id}").status_code == 403

    login(client, COORDINATOR)
    response = client.post("/api/incidents", json={
        "ecoe_event_id": 1,
        "station_id": foreign_station_id,
        "title": "Cruce indebido",
    })
    assert response.status_code == 400


def test_websocket_rejects_untrusted_origin(client):
    login(client, ADMIN)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/ws/live/1",
            headers={"origin": "https://malicious.example"},
        ):
            pass
