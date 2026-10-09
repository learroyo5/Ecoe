"""Datos de la instancia de demostración (demo.ecoe.cl).

Uso, dentro del contenedor backend de la instancia demo:

    python -m app.db.seed_demo

Deja dos ECOE para mostrar el proceso completo:

- **«ECOE Medicina Interna 2026»** (el del seed base), EN EJECUCIÓN: circuitos
  espejo A/B, equipo asignado, primera rotación ya registrada. Sirve para
  mostrar el panel en vivo, el tablero de estaciones, el kiosco y la
  contingencia.
- **«ECOE Cirugía 2026»**, CERRADO: 12 estudiantes × 5 estaciones evaluadas,
  acta consolidada por el flujo real de cierre. Sirve para mostrar resultados,
  desglose por estación, análisis psicométrico y exportación.

Es idempotente (no duplica si ya existen) y sólo usa datos ficticios. Nunca
se ejecuta solo: la instancia demo corre con ``AUTO_SEED_DEMO=false``.
"""

import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.seed import seed_data
from app.db.session import SessionLocal
from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEEvent,
    ECOEPermission,
    EvaluatorRecord,
    LiveSession,
    PilotRun,
    Role,
    StaffAssignment,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
    User,
)
from app.models.enums import ECOEStatus, InstrumentType, RoleCode, SessionMode, StationStatus
from app.services.grading import apply_auto_grading
from app.services.validation import update_ecoe_status
from app.utils.clock import utcnow_naive

LIVE_EVENT_NAME = "ECOE Medicina Interna 2026"
CLOSED_EVENT_NAME = "ECOE Cirugía 2026"

CHOICE_FORM = {
    "questions": [
        {
            "type": "single_choice",
            "label": "Diagnóstico más probable",
            "options": ["Síndrome coronario agudo", "Tromboembolismo pulmonar", "Reflujo gastroesofágico"],
            "points": 10,
            "correct_option": "Síndrome coronario agudo",
        },
        {
            "type": "single_choice",
            "label": "Primer examen a solicitar",
            "options": ["Electrocardiograma", "Radiografía de tórax", "Endoscopía digestiva"],
            "points": 10,
            "correct_option": "Electrocardiograma",
        },
    ]
}


def _ensure_user(db: Session, email: str, full_name: str, role_code: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        role = db.scalar(select(Role).where(Role.code == role_code))
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role_id=role.id,
        )
        db.add(user)
        db.flush()
    return user


def _ensure_evaluator(db: Session, event_id: int, station: Station, email: str, name: str, last_name: str) -> None:
    assignment = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == event_id,
            StaffAssignment.email == email,
            StaffAssignment.role_code == RoleCode.evaluador.value,
        )
    )
    if assignment is None:
        db.add(StaffAssignment(
            ecoe_event_id=event_id, name=name, last_name=last_name, email=email,
            role_code=RoleCode.evaluador.value, station_ids=[station.id],
        ))
    else:
        assignment.station_ids = [station.id]
        db.add(assignment)


def _item_scores(tool_items: list[AssessmentItem], rng: random.Random, skill: float) -> dict[str, float]:
    """Puntaje por criterio: cada uno se logra completo, a medias o no, según
    la habilidad del estudiante (0–1)."""
    scores: dict[str, float] = {}
    for item in tool_items:
        roll = rng.random()
        if roll < skill:
            value = float(item.score_per_item)
        elif roll < skill + 0.2:
            value = float(item.score_per_item) / 2
        else:
            value = 0.0
        scores[str(item.id)] = value
    return scores


def _record_station(
    db: Session, event: ECOEEvent, station: Station, student: Student,
    tool_items: list[AssessmentItem], rng: random.Random, skill: float, *, minutes_ago: float,
) -> None:
    """Deja a `student` como ya atendido en `station`: ingreso cerrado,
    evaluación y/o respuesta según lo que la estación requiera."""
    db.add(StationCheckIn(
        ecoe_event_id=event.id, station_id=station.id, student_id=student.id,
        evaluator_email="demo@ecoe.cl", evaluator_name="Equipo demo", status="cerrado",
        mode=SessionMode.ejecucion.value,
        confirmed_at=utcnow_naive() - timedelta(minutes=minutes_ago),
    ))
    if station.requires_evaluator and tool_items:
        scores = _item_scores(tool_items, rng, skill)
        db.add(EvaluatorRecord(
            ecoe_event_id=event.id, station_id=station.id, student_id=student.id,
            evaluator_name="Equipo demo", mode=SessionMode.ejecucion.value,
            score_obtained=sum(scores.values()),
            max_score=sum(float(item.score_per_item) for item in tool_items),
            observation="", answers={"item_scores": scores}, is_draft=False,
            submission_kind="manual",
        ))
    if station.requires_student_form:
        questions = (station.student_form_definition or {}).get("questions", [])
        answers = {}
        for index, question in enumerate(questions, start=1):
            options = question.get("options") or []
            if not options:
                continue
            correct = question.get("correct_option")
            answers[f"question_{index}"] = (
                correct if rng.random() < skill else rng.choice([o for o in options if o != correct])
            )
        response = StudentResponse(
            ecoe_event_id=event.id, station_id=station.id, student_id=student.id,
            mode=SessionMode.ejecucion.value, answers=answers, locked=True,
            by_contingency=False, submission_kind="manual",
        )
        apply_auto_grading(response, station.student_form_definition)
        db.add(response)


def _polish_live_event(db: Session, password: str) -> None:
    """El evento del seed base queda presentable: formularios con puntaje,
    todas las estaciones con evaluador con cuenta, y una rotación registrada."""
    event = db.scalar(select(ECOEEvent).where(ECOEEvent.name == LIVE_EVENT_NAME))
    if event is None:
        return
    stations = db.scalars(
        select(Station).where(Station.ecoe_event_id == event.id).order_by(Station.station_number)
    ).all()
    already = db.scalar(
        select(StudentResponse).where(StudentResponse.ecoe_event_id == event.id).limit(1)
    )
    if already is not None:
        return
    event.date = date.today()
    extra_evaluators = [
        ("eval2@ecoe.cl", "Rene", "Torres"),
        ("eval3@ecoe.cl", "Marcela", "Díaz"),
        ("eval4@ecoe.cl", "Ignacio", "Vera"),
    ]
    for email, name, last_name in extra_evaluators:
        _ensure_user(db, email, f"{name} {last_name}", RoleCode.evaluador.value, password)
    needing = [s for s in stations if s.requires_evaluator]
    pool = [("eval1@ecoe.cl", "Camila", "Soto")] + extra_evaluators
    for station, (email, name, last_name) in zip(needing, pool):
        _ensure_evaluator(db, event.id, station, email, name, last_name)
    for station in stations:
        station.uses_multimedia = False
        station.multimedia_notes = ""
        if station.requires_student_form and not station.requires_deferred_grading:
            station.student_form_definition = CHOICE_FORM
        station.status = StationStatus.publicada.value
        db.add(station)
    db.flush()

    rng = random.Random(2026)
    students = db.scalars(
        select(Student).where(Student.ecoe_event_id == event.id).order_by(Student.id)
    ).all()
    by_circuit: dict[str, list[Station]] = {}
    for station in stations:
        by_circuit.setdefault(station.circuit_name, []).append(station)
    tools: dict[int, list[AssessmentItem]] = {}
    for station in stations:
        if station.assessment_tool_id and station.assessment_tool_id not in tools:
            tools[station.assessment_tool_id] = list(db.scalars(
                select(AssessmentItem).where(AssessmentItem.tool_id == station.assessment_tool_id)
                .order_by(AssessmentItem.order_index)
            ))
    existing_pairs = {
        (record.station_id, record.student_id)
        for record in db.scalars(
            select(EvaluatorRecord).where(EvaluatorRecord.ecoe_event_id == event.id)
        )
    }
    # Primera ronda completa: los tres primeros estudiantes de cada circuito ya
    # pasaron por todas sus estaciones (salvo la de corrección diferida, que
    # queda con respuestas pendientes de corregir para mostrar esa pantalla).
    for circuit, circuit_stations in by_circuit.items():
        circuit_students = [s for s in students if s.circuit_name == circuit][:3]
        for student in circuit_students:
            skill = rng.uniform(0.45, 0.95)
            for station in circuit_stations:
                if (station.id, student.id) in existing_pairs:
                    continue
                _record_station(
                    db, event, station, student,
                    tools.get(station.assessment_tool_id or 0, []), rng, skill, minutes_ago=40,
                )
    db.commit()


def _create_closed_event(db: Session, admin: User, password: str) -> None:
    if db.scalar(select(ECOEEvent).where(ECOEEvent.name == CLOSED_EVENT_NAME)) is not None:
        return
    rng = random.Random(42)
    event = ECOEEvent(
        name=CLOSED_EVENT_NAME,
        date=date.today() - timedelta(days=21),
        course_name="Cirugía",
        school_name="Escuela de Medicina",
        responsible_teacher="Dr. Pablo Rojas",
        contact_email="ecoe@universidad.cl",
        circuit_mode="secuencial",
        station_time_minutes=7,
        transition_time_minutes=1,
        inter_round_pause_minutes=5,
        total_groups=1,
        passing_reference_percent=60,
        status=ECOEStatus.en_ejecucion.value,
    )
    db.add(event)
    db.flush()
    db.add(ECOEPermission(ecoe_event_id=event.id, user_id=admin.id, role_code=RoleCode.admin_ecoe.value))

    tool = AssessmentTool(
        name="Pauta de habilidades quirúrgicas básicas",
        tool_type=InstrumentType.checklist.value, max_score=20, free_observation=True,
        origin_event_id=event.id,
    )
    db.add(tool)
    db.flush()
    criteria = [
        ("Higiene de manos y técnica aséptica", 4),
        ("Comunicación con el paciente y consentimiento", 4),
        ("Ejecución ordenada del procedimiento", 6),
        ("Manejo seguro del instrumental", 3),
        ("Indicaciones y cierre", 3),
    ]
    items = [
        AssessmentItem(tool_id=tool.id, label=label, score_per_item=points, order_index=index)
        for index, (label, points) in enumerate(criteria, start=1)
    ]
    db.add_all(items)
    db.flush()

    station_defs = [
        ("Anamnesis de dolor abdominal", "paciente_simulado", True, False),
        ("Examen físico abdominal", "procedimental", True, False),
        ("Sutura simple", "procedimental", True, False),
        ("Interpretación de imágenes", "formulario_estudiante", False, True),
        ("Consentimiento informado", "hibrida", True, True),
    ]
    stations: list[Station] = []
    for number, (name, station_type, requires_eval, requires_form) in enumerate(station_defs, start=1):
        station = Station(
            ecoe_event_id=event.id, station_number=number, name=name, station_type=station_type,
            circuit_name="Circuito A", station_time_minutes=7, transition_time_minutes=1,
            assessment_tool_id=tool.id if requires_eval else None,
            expected_outcomes="Demostrar desempeño clínico seguro y estructurado.",
            student_activity="Resolver la tarea clínica según las instrucciones de la estación.",
            pre_entry_instruction="Lea el caso antes de ingresar.",
            student_station_instruction="Dispone de 7 minutos para completar la tarea.",
            evaluator_instruction="Observe sin intervenir y registre cada criterio de la pauta.",
            requires_evaluator=requires_eval, requires_student_form=requires_form,
            uses_physical_resources=True, max_score=20,
            materials="Guantes, campo estéril, instrumental básico",
            student_form_definition=CHOICE_FORM if requires_form else {},
            contingency_ready=True, status=StationStatus.publicada.value,
        )
        db.add(station)
        stations.append(station)
    db.flush()

    evaluators = [
        ("eval1@ecoe.cl", "Camila", "Soto"), ("eval2@ecoe.cl", "Rene", "Torres"),
        ("eval3@ecoe.cl", "Marcela", "Díaz"), ("eval4@ecoe.cl", "Ignacio", "Vera"),
    ]
    for email, name, last_name in evaluators:
        _ensure_user(db, email, f"{name} {last_name}", RoleCode.evaluador.value, password)
    for station, (email, name, last_name) in zip([s for s in stations if s.requires_evaluator], evaluators):
        db.add(StaffAssignment(
            ecoe_event_id=event.id, name=name, last_name=last_name, email=email,
            role_code=RoleCode.evaluador.value, station_ids=[station.id],
        ))
    db.add(StaffAssignment(
        ecoe_event_id=event.id, name="Paula", last_name="Moya", email="coord@ecoe.cl",
        role_code=RoleCode.coordinador_operativo.value, station_ids=[],
    ))
    db.add(PilotRun(ecoe_event_id=event.id, name="Pilotaje general", scope="circuito_completo"))
    db.add(LiveSession(
        ecoe_event_id=event.id, mode=SessionMode.ejecucion.value, status="circuit_complete",
        station_time_seconds=420, transition_time_seconds=60, current_station_index=5,
        remaining_seconds=0, inter_round_pause_seconds=300,
    ))

    names = [
        ("Antonia", "Reyes"), ("Benjamín", "Soto"), ("Catalina", "Muñoz"), ("Diego", "Pérez"),
        ("Emilia", "Rojas"), ("Felipe", "Castro"), ("Gabriela", "Torres"), ("Hernán", "Vega"),
        ("Isidora", "Lagos"), ("Joaquín", "Silva"), ("Karla", "Núñez"), ("Lucas", "Fuentes"),
    ]
    students: list[Student] = []
    for index, (name, last_name) in enumerate(names, start=1):
        student = Student(
            ecoe_event_id=event.id, name=name, last_name=last_name,
            rut=f"2000000{index:02d}-0", email=f"cirugia{index}@demo.ecoe.cl",
            ecoe_number=f"E{index:03d}", group_name="Grupo 1", circuit_name="Circuito A",
            is_active=True,
        )
        db.add(student)
        students.append(student)
    db.flush()

    for student in students:
        skill = rng.uniform(0.35, 0.97)
        for station in stations:
            _record_station(
                db, event, station, student, items if station.requires_evaluator else [],
                rng, skill, minutes_ago=60 * 24 * 21,
            )
    db.flush()
    # Cierre por el camino real: valida completitud y consolida el acta.
    update_ecoe_status(db, event, ECOEStatus.cerrado.value, actor_email=admin.email)


def seed_demo(db: Session) -> None:
    settings = get_settings()
    password = settings.admin_password
    if len(password or "") < 8:
        raise SystemExit("Define ADMIN_PASSWORD (≥ 8 caracteres) en el entorno de la instancia demo.")
    seed_data(db)  # roles, cuentas base, bancos y el evento en ejecución
    admin = db.scalar(select(User).where(User.email == "admin@ecoe.cl"))
    if admin is None:
        raise SystemExit("El seed base no creó la cuenta admin@ecoe.cl; revisa las contraseñas del entorno.")
    _polish_live_event(db, password)
    _create_closed_event(db, admin, password)
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        seed_demo(session)
    print("Demo listo: «%s» en ejecución y «%s» cerrado." % (LIVE_EVENT_NAME, CLOSED_EVENT_NAME))
