from datetime import date
from pathlib import Path
import warnings

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEPermission,
    ECOEEvent,
    EvaluatorRecord,
    Incident,
    LiveSession,
    PilotRecord,
    PilotRun,
    Role,
    SimulatedPatient,
    StaffAssignment,
    Station,
    StationTemplate,
    Student,
    User,
)
from app.models.enums import ECOEStatus, InstrumentType, RoleCode, SessionMode, StationStatus

MIN_SEED_PASSWORD_LENGTH = 12


def _validated_seed_password(password: str, email: str) -> str | None:
    """Never create an account whose password is empty or trivially weak."""
    if len(password or "") < MIN_SEED_PASSWORD_LENGTH:
        warnings.warn(
            f"Seed omitido para {email}: la contraseña configurada está vacía o "
            f"tiene menos de {MIN_SEED_PASSWORD_LENGTH} caracteres. "
            "Define la variable correspondiente en .env.",
            stacklevel=3,
        )
        return None
    return password


def seed_data(db: Session) -> None:
    if db.scalar(select(User).limit(1)):
        return
    settings = get_settings()

    role_defs = [
        (RoleCode.admin_global.value, "Administrador global"),
        (RoleCode.miembro.value, "Miembro institucional"),
        (RoleCode.admin_ecoe.value, "Administrador ECOE"),
        (RoleCode.coeditor_docente.value, "Coeditor docente"),
        (RoleCode.evaluador.value, "Evaluador"),
        (RoleCode.corrector.value, "Corrector de evaluación diferida"),
        (RoleCode.estudiante.value, "Estudiante"),
        (RoleCode.coordinador_operativo.value, "Coordinador operativo"),
        (RoleCode.cronometrador.value, "Cronometrador"),
    ]
    existing_roles = {
        role.code: role for role in db.scalars(select(Role)).all()
    }
    roles = [
        existing_roles.get(code) or Role(code=code, name=name)
        for code, name in role_defs
    ]
    db.add_all([role for role in roles if role.id is None])
    db.flush()
    role_map = {role.code: role.id for role in roles}

    user_defs = [
        ("admin@ecoe.cl", "Admin global", settings.admin_password, RoleCode.admin_global.value),
        ("coeditor@ecoe.cl", "Dr. Pablo Rojas", settings.coeditor_password, RoleCode.coeditor_docente.value),
        ("eval1@ecoe.cl", "Enf. Camila Soto", settings.evaluator_password, RoleCode.evaluador.value),
        ("corrector@ecoe.cl", "Dra. Lucía Fuentes", settings.corrector_password, RoleCode.corrector.value),
        ("student1@ecoe.cl", "Estudiante 1 Demo", settings.student_password, RoleCode.estudiante.value),
        ("coord@ecoe.cl", "Coordinación ECOE", settings.coordinator_password, RoleCode.coordinador_operativo.value),
        ("timer@ecoe.cl", "Cronómetro Central", settings.timer_password, RoleCode.cronometrador.value),
    ]
    users = []
    for email, full_name, raw_password, role_code in user_defs:
        password = _validated_seed_password(raw_password, email)
        if password is None:
            continue
        users.append(
            User(
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash(password),
                role_id=role_map[role_code],
            )
        )
    if not users:
        warnings.warn(
            "Seed cancelado: ninguna cuenta demo tiene contraseña valida configurada.",
            stacklevel=2,
        )
        db.commit()
        return
    db.add_all(users)
    db.flush()
    users_by_email = {user.email: user for user in users}

    admin_user = users_by_email.get("admin@ecoe.cl")
    if admin_user is None:
        warnings.warn(
            "Seed parcial: sin cuenta admin valida no se crea el ECOE demo.",
            stacklevel=2,
        )
        db.commit()
        return

    ecoe = ECOEEvent(
        name="ECOE Medicina Interna 2026",
        date=date(2026, 4, 15),
        course_name="Medicina Interna",
        school_name="Escuela de Medicina",
        responsible_teacher="Admin ECOE",
        contact_email="ecoe@universidad.cl",
        circuit_mode="paralelo_espejo",
        station_time_minutes=8,
        transition_time_minutes=2,
        total_groups=2,
        passing_reference_percent=60,
        # en_ejecucion: el gate de envios solo acepta registros operativos en
        # pilotaje/ejecucion; el evento demo debe permitir probar el flujo
        # completo (check-in, evaluacion, respuesta) sin transiciones previas.
        status=ECOEStatus.en_ejecucion.value,
    )
    db.add(ecoe)
    db.flush()
    db.add(
        ECOEPermission(
            ecoe_event_id=ecoe.id,
            user_id=admin_user.id,
            role_code=RoleCode.admin_ecoe.value,
        )
    )

    templates = [
        StationTemplate(
            name="Procedimental",
            category="procedimental",
            description="Plantilla para técnica o procedimiento clínico",
            default_configuration={"requires_evaluator": True, "requires_student_form": False},
        ),
        StationTemplate(
            name="Paciente simulado",
            category="paciente_simulado",
            description="Guion clínico con actor o paciente simulado",
            default_configuration={"uses_simulated_patient": True},
        ),
        StationTemplate(
            name="Formulario estudiante",
            category="formulario_estudiante",
            description="Estación cognitiva con buzón digital",
            default_configuration={"requires_student_form": True},
        ),
        StationTemplate(
            name="Multimedia",
            category="multimedia",
            description="Estación con video, audio, imagen o PDF",
            default_configuration={"uses_multimedia": True},
        ),
        StationTemplate(
            name="Hibrida",
            category="hibrida",
            description="Combina evaluador, formulario y multimedia",
            default_configuration={"requires_evaluator": True, "requires_student_form": True},
        ),
    ]
    db.add_all(templates)
    db.flush()

    tool = AssessmentTool(
        name="Lista de cotejo examen fisico",
        tool_type=InstrumentType.checklist.value,
        max_score=20,
        free_observation=True,
    )
    db.add(tool)
    db.flush()
    db.add_all(
        [
            AssessmentItem(tool_id=tool.id, label="Lavado de manos", score_per_item=2, order_index=1),
            AssessmentItem(tool_id=tool.id, label="Presentación al paciente", score_per_item=2, order_index=2),
            AssessmentItem(tool_id=tool.id, label="Tecnica correcta", score_per_item=8, order_index=3),
            AssessmentItem(tool_id=tool.id, label="Interpretación final", score_per_item=8, order_index=4),
        ]
    )

    simulated_patient = SimulatedPatient(
        character_name="Juan Perez, 54 anos",
        summary_profile="Paciente con dolor toracico intermitente.",
        base_story="Consulta en urgencias por dolor opresivo al esfuerzo desde hace 2 días.",
        key_answers="Dolor 7/10, irradia a brazo izquierdo, antecedente HTA.",
        emotional_tone="Ansioso y preocupado",
        special_instructions="Responder solo si el estudiante pregunta dirigidamente.",
    )
    db.add(simulated_patient)
    db.flush()

    # (nombre, tipo, requires_evaluator, requires_student_form, multimedia, requires_deferred_grading)
    station_defs = [
        ("Ingreso y anamnesis", "paciente_simulado", True, False, False, False),
        ("Interpretación ECG", "multimedia", True, True, True, False),
        ("Examen cardiovascular", "procedimental", True, False, False, False),
        ("Plan diagnóstico", "formulario_estudiante", False, True, False, False),
        ("Consejería y cierre", "hibrida", True, True, False, False),
        ("Informe de laboratorio", "formulario_estudiante", False, True, False, True),
    ]
    deferred_form = {
        "questions": [
            {
                "type": "short_text",
                "label": "Interpreta los resultados de laboratorio y justifica tu conducta",
                "points": 20,
            }
        ]
    }
    for idx, (name, station_type, requires_eval, requires_form, multimedia, requires_deferred) in enumerate(
        station_defs, start=1
    ):
        db.add(
            Station(
                ecoe_event_id=ecoe.id,
                template_id=templates[min(idx - 1, len(templates) - 1)].id,
                assessment_tool_id=tool.id if requires_eval else None,
                simulated_patient_id=simulated_patient.id if station_type == "paciente_simulado" else None,
                station_number=idx,
                name=name,
                station_type=station_type,
                circuit_name="Circuito A" if idx <= 3 else "Circuito B",
                station_time_minutes=8,
                transition_time_minutes=2,
                expected_outcomes="Demostrar desempeño clínico seguro y estructurado.",
                student_activity="Resolver la tarea clínica según instrucciones de la estación.",
                pre_entry_instruction="Lea el caso y prepare su abordaje clínico.",
                evaluator_instruction="Observe, puntue y registre observaciones relevantes.",
                requires_evaluator=requires_eval,
                requires_student_form=requires_form,
                requires_deferred_grading=requires_deferred,
                uses_multimedia=multimedia,
                uses_simulated_patient=station_type == "paciente_simulado",
                uses_physical_resources=True,
                max_score=20,
                materials="Guantes, ficha, lapiz",
                clinical_equipment="Fonendoscopio y tensiometro",
                simulator="Paciente estandarizado",
                ambience="Box de urgencia",
                multimedia_notes="Mostrar ECG previo en PDF" if multimedia else "",
                student_form_definition=(
                    deferred_form
                    if requires_deferred
                    else {
                        "questions": [
                            {
                                "type": "single_choice",
                                "label": "Diagnóstico más probable",
                                "options": ["SCA", "TEP", "RGE"],
                            }
                        ]
                    }
                    if requires_form
                    else {}
                ),
                contingency_ready=True,
                status=StationStatus.validada.value,
            )
        )

    students = [
        Student(
            ecoe_event_id=ecoe.id,
            name=f"Estudiante{i}",
            last_name="Demo",
            rut=f"1111111{i}-K",
            email=f"student{i}@ecoe.cl",
            ecoe_number=f"E{i:03}",
            group_name="Grupo 1" if i <= 5 else "Grupo 2",
            circuit_name="Circuito A" if i <= 5 else "Circuito B",
        )
        for i in range(1, 11)
    ]
    db.add_all(students)

    staff = [
        StaffAssignment(
            ecoe_event_id=ecoe.id,
            name="Pablo",
            last_name="Rojas",
            email="coeditor@ecoe.cl",
            role_code=RoleCode.coeditor_docente.value,
            station_ids=[],
        ),
        StaffAssignment(
            ecoe_event_id=ecoe.id,
            name="Camila",
            last_name="Soto",
            email="eval1@ecoe.cl",
            role_code=RoleCode.evaluador.value,
            station_ids=[1],
        ),
        StaffAssignment(
            ecoe_event_id=ecoe.id,
            name="Rene",
            last_name="Torres",
            email="eval2@ecoe.cl",
            role_code=RoleCode.evaluador.value,
            station_ids=[3, 4],
        ),
        StaffAssignment(
            ecoe_event_id=ecoe.id,
            name="Lucía",
            last_name="Fuentes",
            email="corrector@ecoe.cl",
            role_code=RoleCode.corrector.value,
            # Estación 6 "Informe de laboratorio": corrección diferida.
            station_ids=[6],
        ),
        StaffAssignment(
            ecoe_event_id=ecoe.id,
            name="Paula",
            last_name="Moya",
            email="coord@ecoe.cl",
            role_code=RoleCode.coordinador_operativo.value,
            station_ids=[],
        ),
        StaffAssignment(
            ecoe_event_id=ecoe.id,
            name="Cronómetro",
            last_name="Central",
            email="timer@ecoe.cl",
            role_code=RoleCode.cronometrador.value,
            station_ids=[],
        ),
    ]
    db.add_all(staff)
    db.flush()

    pilot = PilotRun(ecoe_event_id=ecoe.id, name="Pilotaje inicial", scope="circuito_completo")
    db.add(pilot)
    db.flush()
    db.add(PilotRecord(pilot_run_id=pilot.id, station_id=1, payload={"note": "tiempo correcto"}))

    live_session = LiveSession(
        ecoe_event_id=ecoe.id,
        mode=SessionMode.ejecucion.value,
        status="ready",
        station_time_seconds=480,
        transition_time_seconds=120,
        current_station_index=1,
        remaining_seconds=480,
    )
    db.add(live_session)
    db.flush()

    db.add(
        EvaluatorRecord(
            ecoe_event_id=ecoe.id,
            live_session_id=live_session.id,
            station_id=1,
            student_id=1,
            evaluator_name="Camila Soto",
            mode=SessionMode.ejecucion.value,
            score_obtained=17,
            max_score=20,
            observation="Buen rapport y orden.",
            answers={"item_1": 2, "item_2": 2, "item_3": 7, "item_4": 6},
        )
    )
    db.add(
        Incident(
            ecoe_event_id=ecoe.id,
            station_id=2,
            title="Audio bajo",
            detail="Se recomienda aumentar volumen del recurso multimedia.",
            severity="media",
        )
    )

    storage = Path(get_settings().storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    db.commit()
