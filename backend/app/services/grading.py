"""Scoring of student form responses.

Questions in student_form_definition may declare:
  - points: float           puntaje de la pregunta (0 u omitido = no puntua)
  - correct_option: str     clave para single_choice
  - correct_options: [str]  clave para multiple_choice (match exacto del set)

Choice questions are auto-graded server-side at submit time; short_text
questions with points require manual grading by a content manager. A
response only carries a definitive score (score_obtained) once nothing is
pending, and only definitive scores enter the consolidated results.
"""

from fastapi import HTTPException

from app.models.entities import StudentResponse
from app.utils.clock import utcnow_naive

AUTO_GRADED_TYPES = {"single_choice", "multiple_choice"}


def is_answered(value) -> bool:
    """Whether a submitted answer carries actual content (OPT-20 F4, D4).

    ``None``/empty string/empty list/empty dict = not answered. A blank
    auto-submitted response still scores 0 over the max, but each blank item
    is flagged so the corrector and the export can tell an omission from a
    deliberate wrong answer.
    """
    if value is None:
        return False
    if isinstance(value, (str, list, tuple, set, dict)):
        return len(value) > 0
    return True


def grade_answers(form_definition: dict | None, answers: dict | None) -> dict:
    """Compute the auto-graded portion and the pending-manual layout."""
    questions = (form_definition or {}).get("questions") or []
    answers = answers or {}
    auto_score = 0.0
    auto_max = 0.0
    manual_max = 0.0
    per_question: dict[str, dict] = {}

    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            continue
        try:
            points = float(question.get("points") or 0)
        except (TypeError, ValueError):
            points = 0.0
        if points <= 0:
            continue
        key = f"question_{index + 1}"
        question_type = str(question.get("type") or "")
        answer = answers.get(key)
        answered = is_answered(answer)

        if question_type == "single_choice":
            auto_max += points
            correct = question.get("correct_option")
            earned = points if (correct is not None and answer == correct) else 0.0
            auto_score += earned
            per_question[key] = {
                "kind": "auto", "earned": earned, "max": points, "answered": answered,
            }
        elif question_type == "multiple_choice":
            auto_max += points
            correct = {str(item) for item in (question.get("correct_options") or [])}
            given = {str(item) for item in answer} if isinstance(answer, list) else set()
            earned = points if correct and given == correct else 0.0
            auto_score += earned
            per_question[key] = {
                "kind": "auto", "earned": earned, "max": points, "answered": answered,
            }
        else:
            manual_max += points
            per_question[key] = {
                "kind": "manual", "earned": None, "max": points, "answered": answered,
            }

    return {
        "auto_score": auto_score,
        "auto_max": auto_max,
        "manual_max": manual_max,
        "per_question": per_question,
    }


def apply_auto_grading(response: StudentResponse, form_definition: dict | None) -> None:
    """Attach the auto-graded portion to a freshly created response."""
    result = grade_answers(form_definition, response.answers)
    total_max = result["auto_max"] + result["manual_max"]
    if total_max <= 0:
        # Formulario sin puntajes definidos: no participa del consolidado.
        response.grading = {}
        response.score_obtained = None
        response.max_score = None
        return
    response.grading = result["per_question"]
    response.max_score = total_max
    if result["manual_max"] == 0:
        response.score_obtained = result["auto_score"]
        response.graded_by_email = "auto"
        response.graded_at = utcnow_naive()
    else:
        response.score_obtained = None


def pending_manual_keys(response: StudentResponse) -> list[str]:
    return [
        key
        for key, item in (response.grading or {}).items()
        if isinstance(item, dict) and item.get("kind") == "manual" and item.get("earned") is None
    ]


def apply_manual_scores(
    response: StudentResponse, scores: dict[str, float], *, graded_by_email: str
) -> None:
    """Resolve the pending manual questions of a response."""
    grading = dict(response.grading or {})
    manual = {
        key
        for key, item in grading.items()
        if isinstance(item, dict) and item.get("kind") == "manual"
    }
    if not manual:
        raise HTTPException(
            status_code=400,
            detail="Esta respuesta no tiene preguntas de corrección manual",
        )
    unknown = set(scores) - manual
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Preguntas no corregibles manualmente: {', '.join(sorted(unknown))}",
        )
    # Re-corrección de una pregunta ya resuelta: prohibida por este flujo. Cambiar
    # un puntaje ya asignado exige el procedimiento de rectificación (reabrir el
    # evento), no un reenvío silencioso de `scores`.
    already_resolved = {key for key in manual if grading[key].get("earned") is not None}
    regrade = set(scores) & already_resolved
    if regrade:
        raise HTTPException(
            status_code=409,
            detail=(
                f"La(s) pregunta(s) {', '.join(sorted(regrade))} ya tienen puntaje; "
                "usa el flujo de rectificación"
            ),
        )
    pending = manual - already_resolved
    missing = {key for key in pending if key not in scores}
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Faltan puntajes para: {', '.join(sorted(missing))}",
        )
    for key, value in scores.items():
        item = grading[key]
        try:
            earned = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Puntaje inválido para {key}") from exc
        if earned < 0 or earned > float(item["max"]):
            raise HTTPException(
                status_code=400,
                detail=f"El puntaje de {key} debe estar entre 0 y {item['max']}",
            )
        grading[key] = {**item, "earned": earned}

    total = sum(
        float(item.get("earned") or 0)
        for item in grading.values()
        if isinstance(item, dict)
    )
    response.grading = grading
    response.score_obtained = total
    response.graded_by_email = graded_by_email
    response.graded_at = utcnow_naive()


# ── Evaluador: puntaje autoritativo desde la pauta (PROC-10) ──────────


def evaluator_score_from_answers(db, station, answers: dict | None) -> float | None:
    """Suma del desglose por criterio (`answers["item_scores"]`) validada
    contra la pauta de la estación, o ``None`` si no viene desglose.

    El total que manda el navegador deja de ser la fuente: si hay desglose,
    cada criterio debe existir en la pauta y estar entre 0 y su puntaje, y la
    nota es su suma. Sin desglose (transcripción de un total en papel) el
    llamador conserva el total informado, acotado al máximo de la estación.
    """
    from sqlalchemy import select

    from app.models.entities import AssessmentItem

    raw = (answers or {}).get("item_scores") if isinstance(answers, dict) else None
    if not isinstance(raw, dict) or not raw or not station.assessment_tool_id:
        return None
    items = db.scalars(
        select(AssessmentItem).where(AssessmentItem.tool_id == station.assessment_tool_id)
    ).all()
    if not items:
        return None
    by_id = {str(item.id): item for item in items}
    by_order = {str(item.order_index): item for item in items}
    total = 0.0
    for key, value in raw.items():
        item = by_id.get(str(key)) or by_order.get(str(key))
        if item is None:
            raise HTTPException(
                status_code=400,
                detail="El desglose incluye un criterio que no pertenece a la pauta de la estación",
            )
        try:
            score = float(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Puntaje de criterio no válido") from None
        if score < 0 or score > float(item.score_per_item) + 1e-9:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El criterio «{item.label}» admite entre 0 y "
                    f"{item.score_per_item:g} puntos"
                ),
            )
        total += score
    return round(total, 4)


def ensure_score_matches_breakdown(db, station, answers: dict | None, score_obtained: float) -> float:
    """Devuelve el puntaje autoritativo; 400 si el total informado contradice
    la suma del desglose (señal de un cliente defectuoso o de una request
    armada a mano)."""
    server_score = evaluator_score_from_answers(db, station, answers)
    if server_score is None:
        return float(score_obtained)
    if abs(server_score - float(score_obtained)) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El puntaje informado ({score_obtained:g}) no coincide con la suma "
                f"de la pauta ({server_score:g})"
            ),
        )
    return server_score
