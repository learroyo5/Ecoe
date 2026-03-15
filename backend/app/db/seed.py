from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
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


def seed_data(db: Session) -> None:
    if db.scalar(select(User).limit(1)):
        return

    roles = [
        Role(code=RoleCode.creador_ecoe.value, name="Creador ECOE"),
        Role(code=RoleCode.coeditor_docente.value, name="Coeditor docente"),
        Role(code=RoleCode.evaluador.value, name="Evaluador"),
        Role(code=RoleCode.estudiante.value, name="Estudiante"),
        Role(code=RoleCode.coordinador_operativo.value, name="Coordinador operativo"),
        Role(code=RoleCode.cronometrador.value, name="Cronometrador"),
    ]
    db.add_all(roles)
    db.flush()
    role_map = {role.code: role.id for role in roles}

    users = [
        User(
            email="creator@ecoe.cl",
            full_name="Dra. Laura Martinez",
            hashed_password=get_password_hash("admin123"),
            role_id=role_map[RoleCode.creador_ecoe.value],
        ),
        User(
            email="coeditor@ecoe.cl",
            full_name="Dr. Pablo Rojas",
            hashed_password=get_password_hash("admin123"),
            role_id=role_map[RoleCode.coeditor_docente.value],
        ),
        User(
            email="eval1@ecoe.cl",
            full_name="Enf. Camila Soto",
            hashed_password=get_password_hash("admin123"),
            role_id=role_map[RoleCode.evaluador.value],
        ),
        User(
            email="student1@ecoe.cl",
            full_name="Estudiante 1 Demo",
            hashed_password=get_password_hash("admin123"),
            role_id=role_map[RoleCode.estudiante.value],
        ),
        User(
            email="coord@ecoe.cl",
            full_name="Coordinacion ECOE",
            hashed_password=get_password_hash("admin123"),
            role_id=role_map[RoleCode.coordinador_operativo.value],
        ),
        User(
            email="timer@ecoe.cl",
            full_name="Cronometro Central",
            hashed_password=get_password_hash("admin123"),
            role_id=role_map[RoleCode.cronometrador.value],
        ),
    ]
    db.add_all(users)
    db.flush()

    ecoe = ECOEEvent(
        name="ECOE Medicina Interna 2026",
        date=date(2026, 4, 15),
        course_name="Medicina Interna",
        school_name="Escuela de Medicina",
        responsible_teacher="Dra. Laura Martinez",
        contact_email="ecoe@universidad.cl",
        circuit_mode="paralelo_espejo",
        total_stations=5,
        station_time_minutes=8,
        transition_time_minutes=2,
        total_students=10,
        total_groups=2,
        passing_reference_percent=60,
        status=ECOEStatus.publicado.value,
    )
    db.add(ecoe)
    db.flush()

    templates = [
        StationTemplate(
            name="Procedimental",
            category="procedimental",
            description="Plantilla para tecnica o procedimiento clinico",
            default_configuration={"requires_evaluator": True, "requires_student_form": False},
        ),
        StationTemplate(
            name="Paciente simulado",
            category="paciente_simulado",
            description="Guion clinico con actor o paciente simulado",
            default_configuration={"uses_simulated_patient": True},
        ),
        StationTemplate(
            name="Formulario estudiante",
            category="formulario_estudiante",
            description="Estacion cognitiva con buzon digital",
            default_configuration={"requires_student_form": True},
        ),
        StationTemplate(
            name="Multimedia",
            category="multimedia",
            description="Estacion con video, audio, imagen o PDF",
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
            AssessmentItem(tool_id=tool.id, label="Presentacion al paciente", score_per_item=2, order_index=2),
            AssessmentItem(tool_id=tool.id, label="Tecnica correcta", score_per_item=8, order_index=3),
            AssessmentItem(tool_id=tool.id, label="Interpretacion final", score_per_item=8, order_index=4),
        ]
    )

    simulated_patient = SimulatedPatient(
        character_name="Juan Perez, 54 anos",
        summary_profile="Paciente con dolor toracico intermitente.",
        base_story="Consulta en urgencias por dolor opresivo al esfuerzo desde hace 2 dias.",
        key_answers="Dolor 7/10, irradia a brazo izquierdo, antecedente HTA.",
        emotional_tone="Ansioso y preocupado",
        special_instructions="Responder solo si el estudiante pregunta dirigidamente.",
    )
    db.add(simulated_patient)
    db.flush()

    station_defs = [
        ("Ingreso y anamnesis", "paciente_simulado", True, False, False),
        ("Interpretacion ECG", "multimedia", True, True, True),
        ("Examen cardiovascular", "procedimental", True, False, False),
        ("Plan diagnostico", "formulario_estudiante", False, True, False),
        ("Consejeria y cierre", "hibrida", True, True, False),
    ]
    for idx, (name, station_type, requires_eval, requires_form, multimedia) in enumerate(
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
                expected_outcomes="Demostrar desempeno clinico seguro y estructurado.",
                student_activity="Resolver la tarea clinica segun instrucciones de la estacion.",
                pre_entry_instruction="Lea el caso y prepare su abordaje clinico.",
                evaluator_instruction="Observe, puntue y registre observaciones relevantes.",
                requires_evaluator=requires_eval,
                requires_student_form=requires_form,
                uses_multimedia=multimedia,
                uses_simulated_patient=station_type == "paciente_simulado",
                uses_physical_resources=True,
                max_score=20,
                materials="Guantes, ficha, lapiz",
                clinical_equipment="Fonendoscopio y tensiometro",
                simulator="Paciente estandarizado",
                ambience="Box de urgencia",
                multimedia_notes="Mostrar ECG previo en PDF" if multimedia else "",
                student_form_definition={
                    "questions": [
                        {
                            "type": "single_choice",
                            "label": "Diagnostico mas probable",
                            "options": ["SCA", "TEP", "RGE"],
                        }
                    ]
                    if requires_form
                    else []
                },
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
            name="Camila",
            last_name="Soto",
            email="eval1@ecoe.cl",
            role_code=RoleCode.evaluador.value,
            station_ids=[1, 2],
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
            name="Paula",
            last_name="Moya",
            email="coord@ecoe.cl",
            role_code=RoleCode.coordinador_operativo.value,
            station_ids=[5],
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
