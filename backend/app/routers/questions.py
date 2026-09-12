from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models as m
from app.database import get_db
from app.grading import grade_open_response
from app.scoring import (
    recompute_lesson_status,
    record_attempt,
    update_streak,
    upsert_review_item,
)

router = APIRouter(prefix="/api/questions", tags=["questions"])


class AnswerRequest(BaseModel):
    answer: str


def _check_mcq(question: m.Question, answer: str) -> bool:
    """MCQ is graded locally — no AI call, instant."""
    try:
        chosen = int(answer.strip())
    except ValueError:
        raise HTTPException(
            status_code=400, detail="MCQ answer must be an option index, sent as a string"
        )
    options = question.options or []
    if not 0 <= chosen < len(options):
        raise HTTPException(
            status_code=400,
            detail=f"Option index {chosen} is out of range for this question",
        )
    return chosen == question.correct_index


@router.post("/{question_id}/answer")
def answer_question(
    question_id: str, payload: AnswerRequest, db: Session = Depends(get_db)
):
    question = db.get(m.Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if question.type == "mcq":
        is_correct = _check_mcq(question, payload.answer)
        feedback = None
    else:
        is_correct, feedback = grade_open_response(question, payload.answer)

    attempt = record_attempt(db, question, payload.answer, is_correct, feedback)
    db.flush()  # so the mastery recount below sees this attempt

    upsert_review_item(db, question, is_correct)
    lesson_status = recompute_lesson_status(db, question.lesson)
    streak_days = update_streak(db)
    db.commit()

    return {
        "is_correct": is_correct,
        "correct_index": question.correct_index,
        "explanation": question.explanation,
        "feedback": feedback,
        "lesson_status": lesson_status,
        "streak_days": streak_days,
        "attempt_number": attempt.attempt_number,
    }
