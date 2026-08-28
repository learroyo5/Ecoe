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

        if question_type == "single_choice":
            auto_max += points
            correct = question.get("correct_option")
            earned = points if (correct is not None and answer == correct) else 0.0
            auto_score += earned
            per_question[key] = {"kind": "auto", "earned": earned, "max": points}
        elif question_type == "multiple_choice":
            auto_max += points
            correct = {str(item) for item in (question.get("correct_options") or [])}
            given = {str(item) for item in answer} if isinstance(answer, list) else set()
            earned = points if correct and given == correct else 0.0
            auto_score += earned
            per_question[key] = {"kind": "auto", "earned": earned, "max": points}
        else:
            manual_max += points
            per_question[key] = {"kind": "manual", "earned": None, "max": points}

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
