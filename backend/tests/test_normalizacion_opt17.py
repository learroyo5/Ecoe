"""OPT-17 · Normalización por estación (promedio de %-de-logro, no razón de sumas).

`compute_results` deja de calcular `percentage = sum(obtenido)/sum(máx)*100` y
pasa a promediar los `percent_score` por estación del estudiante
(`compute_station_results`, OPT-16). Cada estación se normaliza a su propio
máximo → todas pesan igual. El estándar sigue siendo compensatorio: un solo
umbral global (`passing_reference_percent`) sobre ese promedio.

Ver `docs/optimizacion/PLANES/OPT-17__normalizacion-por-estacion.md`.

Cubre (positivos + negativos):
- promedio de %-por-estación con máximos heterogéneos (≠ razón de sumas);
- máximos homogéneos → nota idéntica a la fórmula vieja;
- evento de una estación → sin cambio;
- estudiante con actividad en una sola de varias estaciones → no se penaliza;
- `stations_counted` excluye estaciones sin actividad y con máximo 0;
- estación con `max == 0` excluida de la media pero no de las sumas crudas;
- estudiante sin ninguna estación puntuable → 0 % / nota mínima;
- `equivalent_grade` se alimenta del promedio nuevo (función sin tocar);
- evento cerrado con snapshot → sirve el número viejo congelado;
- evento cerrado sin snapshot → cae a la fórmula nueva.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.models.entities import (
    ECOEEvent,
    ECOEResult,
    EvaluatorRecord,
    Station,
    StationCheckIn,
    Student,
)
from app.models.enums import ECOEStatus, SessionMode
from app.services.results import (
    compute_equivalent_grade,
    compute_results,
    persist_results,
    read_results,
)
from app.services.validation import update_ecoe_status
from conftest import TestingSessionLocal


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _auto_form(points: int, correct: str = "A") -> dict:
    return {
        "questions": [
            {
                "type": "single_choice",
                "label": "Conducta",
                "options": ["A", "B"],
                "points": points,
                "correct_option": correct,
            },
        ]
    }


def _build_event(
    station_maxes: list[int],
    *,
    n_students: int = 1,
    status: str = ECOEStatus.en_ejecucion.value,
    passing: float = 60.0,
):
    """Evento en ejecución con una estación de autocorrección por cada máximo.

    Devuelve `(event_id, [station_id...], [(student_id, {station_id: checkin_id})...])`.
    """
    with TestingSessionLocal() as db:
        event = ECOEEvent(
            name="OPT-17 normalización",
            date=date(2026, 12, 10),
            course_name="Curso",
            school_name="Escuela",
            responsible_teacher="Docente",
            contact_email="docente@example.edu",
            circuit_mode="paralelo_espejo",
            total_stations=len(station_maxes),
            station_time_minutes=8,
            transition_time_minutes=2,
            total_students=n_students,
            total_groups=1,
            passing_reference_percent=passing,
            status=status,
        )
        db.add(event)
        db.flush()
        stations = []
        for number, points in enumerate(station_maxes, start=1):
            station = Station(
                ecoe_event_id=event.id,
                station_number=number,
                name=f"Estación {number}",
                station_type="formulario_estudiante",
                circuit_name="Circuito A",
                station_time_minutes=8,
                transition_time_minutes=2,
                expected_outcomes="Resultado",
                student_activity="Actividad",
                pre_entry_instruction="Ingreso",
                evaluator_instruction="",
                requires_evaluator=False,
                requires_student_form=True,
                max_score=points,
                student_form_definition=_auto_form(points or 1),
            )
            db.add(station)
            db.flush()
            stations.append(station.id)
        students = []
        for idx in range(n_students):
            student = Student(
                ecoe_event_id=event.id,
                name=f"Alumno{idx}",
                last_name="Norm",
                rut=f"6{event.id}{idx}00-1",
                email=f"norm{event.id}_{idx}@example.edu",
                ecoe_number=f"{idx + 1:03d}",
                group_name="G1",
                circuit_name="Circuito A",
                is_active=True,
            )
            db.add(student)
            db.flush()
            checkins = {}
            for station_id in stations:
                checkin = StationCheckIn(
                    ecoe_event_id=event.id,
                    station_id=station_id,
                    student_id=student.id,
                    evaluator_email="eval1@ecoe.cl",
                    evaluator_name="Evaluadora",
                    status="confirmado",
                    confirmed_at=_utcnow_naive(),
                )
                db.add(checkin)
                db.flush()
                checkins[station_id] = checkin.id
            students.append((student.id, checkins))
        db.commit()
        return event.id, stations, students


def _submit(client, event_id, station_id, student_id, checkin_id, answer):
    response = client.post("/api/student/submit", json={
        "checkin_id": checkin_id,
        "ecoe_event_id": event_id,
        "station_id": station_id,
        "student_id": student_id,
        "answers": {"question_1": answer},
    })
    assert response.status_code == 200, response.text
    return response.json()["response_id"]


def _close(event_id: int, actor_email: str = "admin@ecoe.cl") -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        update_ecoe_status(db, event, ECOEStatus.cerrado.value, actor_email=actor_email)


def _set_status(event_id: int, status: str) -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        event.status = status
        db.add(event)
        db.commit()


def _results_for(event_id: int) -> dict[int, dict]:
    with TestingSessionLocal() as db:
        return {row["student_id"]: row for row in compute_results(db, event_id)}


# ── Comportamiento nuevo ─────────────────────────────────────────────


def test_aggregate_is_mean_of_station_percentages(auth_client):
    """2 estaciones de máximo 20 y 5; estudiante 20/20 y 0/5.

    Fórmula vieja (razón de sumas): 20/25 = 80 %.
    Fórmula OPT-17 (promedio de %-por-estación): mean(100, 0) = 50 %.
    `total_score`/`max_score` crudos sin cambio: 20 y 25.
    """
    event_id, (s1, s2), students = _build_event([20, 5], n_students=1)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 20/20
    _submit(auth_client, event_id, s2, student_id, checkins[s2], "B")  # 0/5

    row = _results_for(event_id)[student_id]
    assert row["total_score"] == 20
    assert row["max_score"] == 25
    assert row["percentage"] == pytest.approx(50.0, abs=0.01)
    assert row["stations_counted"] == 2
    # La fórmula vieja habría dado 80.
    assert row["total_score"] / row["max_score"] * 100 == pytest.approx(80.0, abs=0.01)


def test_equal_max_stations_unchanged(auth_client):
    """3 estaciones del mismo máximo (10) → promedio(%) == razón de sumas
    exactamente → `percentage` y `equivalent_grade` idénticos a la fórmula vieja.
    """
    event_id, (s1, s2, s3), students = _build_event([10, 10, 10], n_students=1, passing=60.0)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 10/10
    _submit(auth_client, event_id, s2, student_id, checkins[s2], "B")  # 0/10
    _submit(auth_client, event_id, s3, student_id, checkins[s3], "A")  # 10/10

    row = _results_for(event_id)[student_id]
    old_percentage = row["total_score"] / row["max_score"] * 100  # 20/30
    assert row["percentage"] == pytest.approx(round(old_percentage, 2), abs=0.01)
    assert row["equivalent_grade"] == pytest.approx(
        round(compute_equivalent_grade(old_percentage, 60.0), 2), abs=0.01
    )
    assert row["stations_counted"] == 3


def test_single_station_event_unchanged(auth_client):
    """1 estación → `mean` de un solo % == razón de sumas. Cubre el escenario
    de `test_grading.py` (`percentage == 100`) y `test_deferred_grading.py`.
    """
    event_id, (s1,), students = _build_event([10], n_students=1)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 10/10

    row = _results_for(event_id)[student_id]
    assert row["percentage"] == 100
    assert row["total_score"] == 10
    assert row["max_score"] == 10
    assert row["stations_counted"] == 1
    assert row["equivalent_grade"] == pytest.approx(7.0)


def test_student_with_one_station_of_many_not_penalized(auth_client):
    """Estudiante con actividad en 1 de 2 estaciones → `percentage` es el % de
    esa estación, no la mitad. `stations_counted == 1` (la ausente no divide).
    """
    event_id, (s1, s2), students = _build_event([10, 10], n_students=1)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 10/10, s2 ausente

    row = _results_for(event_id)[student_id]
    assert row["percentage"] == 100
    assert row["stations_counted"] == 1
    assert row["total_score"] == 10
    assert row["max_score"] == 10


def test_stations_counted_excludes_inactive_station(auth_client):
    """`stations_counted` cuenta sólo estaciones con actividad: una estación sin
    ningún registro del estudiante no divide el promedio.
    """
    event_id, (s1, s2, s3), students = _build_event([10, 10, 6], n_students=1)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 10/10
    _submit(auth_client, event_id, s3, student_id, checkins[s3], "B")  # 0/6
    # s2 ausente

    row = _results_for(event_id)[student_id]
    assert row["stations_counted"] == 2              # s1 y s3, no s2
    assert row["percentage"] == pytest.approx(50.0, abs=0.01)  # mean(100, 0)
    assert row["total_score"] == 10
    assert row["max_score"] == 16


def test_station_with_zero_max_excluded_from_mean(auth_client):
    """Una fila con `max_score == 0` (p. ej. `EvaluatorRecord` con máximo 0) no
    fuerza un 0 % en la media ni cuenta en `stations_counted`; sí entra a la
    suma cruda de `max_score`.
    """
    event_id, (s1, s2), students = _build_event([10, 10], n_students=1)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 10/10
    with TestingSessionLocal() as db:
        db.add(EvaluatorRecord(
            ecoe_event_id=event_id,
            station_id=s2,
            student_id=student_id,
            evaluator_name="Eval",
            mode=SessionMode.ejecucion.value,
            score_obtained=0,
            max_score=0,
            is_draft=False,
        ))
        db.commit()

    row = _results_for(event_id)[student_id]
    assert row["stations_counted"] == 1              # sólo s1
    assert row["percentage"] == 100                  # media sobre {s1}, sin el 0 % espurio
    assert row["total_score"] == 10
    assert row["max_score"] == 10                    # s2 aporta 0 al máximo crudo


def test_student_with_no_scorable_station_is_zero_percent(auth_client):
    event_id, stations, students = _build_event([10, 6], n_students=1)
    student_id, _checkins = students[0]  # sin ninguna respuesta

    row = _results_for(event_id)[student_id]
    assert row["percentage"] == 0
    assert row["stations_counted"] == 0
    assert row["total_score"] == 0
    assert row["max_score"] == 0
    assert row["equivalent_grade"] == pytest.approx(1.0)


def test_equivalent_grade_fed_new_percentage(auth_client):
    """`equivalent_grade == compute_equivalent_grade(promedio, passing)` — la
    función de escala no se toca; sólo cambia el número que recibe.
    """
    event_id, (s1, s2), students = _build_event([20, 5], n_students=1, passing=60.0)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 100 %
    _submit(auth_client, event_id, s2, student_id, checkins[s2], "B")  # 0 %

    row = _results_for(event_id)[student_id]
    assert row["percentage"] == pytest.approx(50.0, abs=0.01)
    assert row["equivalent_grade"] == pytest.approx(
        round(compute_equivalent_grade(50.0, 60.0), 2), abs=0.01
    )


# ── Inmutabilidad tras el cierre ─────────────────────────────────────


def test_closed_event_with_snapshot_keeps_old_number(auth_client):
    """Evento `cerrado` cuyo `ECOEResult.percentage` se guardó con la fórmula
    vieja (razón de sumas): `GET /results` lo sirve tal cual y no coincide con
    `compute_results` en vivo (máximos heterogéneos). El snapshot manda.
    """
    event_id, (s1, s2), students = _build_event([20, 5], n_students=1)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 100 %
    _submit(auth_client, event_id, s2, student_id, checkins[s2], "B")  # 0 %

    _close(event_id)

    # Se reescribe el snapshot con el número de la fórmula vieja (80 %).
    with TestingSessionLocal() as db:
        snap = db.scalar(
            select(ECOEResult).where(
                ECOEResult.ecoe_event_id == event_id,
                ECOEResult.student_id == student_id,
            )
        )
        assert snap.percentage == pytest.approx(50.0, abs=0.01)  # OPT-17 al consolidar
        snap.percentage = 80.0
        snap.equivalent_grade = compute_equivalent_grade(80.0, 60.0)
        db.add(snap)
        db.commit()

    body = auth_client.get(f"/api/results/{event_id}").json()
    assert body["frozen"] is True
    served = next(r for r in body["results"] if r["student_id"] == student_id)
    assert served["percentage"] == pytest.approx(80.0, abs=0.01)  # snapshot congelado
    assert "stations_counted" not in served  # el snapshot no persiste el campo

    with TestingSessionLocal() as db:
        live = next(r for r in compute_results(db, event_id) if r["student_id"] == student_id)
    assert live["percentage"] == pytest.approx(50.0, abs=0.01)  # fórmula nueva en vivo


def test_closed_event_without_snapshot_uses_new_formula(auth_client):
    """Evento `cerrado` sin filas `ECOEResult` (cierre manual sin
    `persist_results`) → `read_results` cae al recálculo en vivo, que ya usa la
    fórmula nueva de OPT-17.
    """
    event_id, (s1, s2), students = _build_event([20, 5], n_students=1)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")  # 100 %
    _submit(auth_client, event_id, s2, student_id, checkins[s2], "B")  # 0 %
    _set_status(event_id, ECOEStatus.cerrado.value)  # sin snapshot

    with TestingSessionLocal() as db:
        assert not db.scalars(
            select(ECOEResult).where(ECOEResult.ecoe_event_id == event_id)
        ).all()
        rows, frozen, consolidated_at = read_results(db, event_id)
    assert frozen is False
    assert consolidated_at is None
    row = next(r for r in rows if r["student_id"] == student_id)
    assert row["percentage"] == pytest.approx(50.0, abs=0.01)
    assert row["stations_counted"] == 2


def test_persist_results_snapshot_uses_mean_formula(auth_client):
    """`persist_results` sobre un evento fresco con máximos heterogéneos →
    `ECOEResult.percentage` es la media de %-por-estación, no la razón de sumas.
    """
    event_id, (s1, s2), students = _build_event([20, 5], n_students=1)
    student_id, checkins = students[0]
    _submit(auth_client, event_id, s1, student_id, checkins[s1], "A")
    _submit(auth_client, event_id, s2, student_id, checkins[s2], "B")

    with TestingSessionLocal() as db:
        persist_results(db, event_id, actor_email="admin@ecoe.cl")
        snap = db.scalar(
            select(ECOEResult).where(
                ECOEResult.ecoe_event_id == event_id,
                ECOEResult.student_id == student_id,
            )
        )
    assert snap.total_score == 20
    assert snap.max_score == 25
    assert snap.percentage == pytest.approx(50.0, abs=0.01)
