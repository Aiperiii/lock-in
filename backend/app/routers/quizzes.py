from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models as m
from app import scoring
from app.database import get_db
from app.pipeline.auto_quiz import maybe_trigger_auto_quiz
from app.quizzes import generate_quiz, serialize_quiz

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


class GenerateQuizRequest(BaseModel):
    book_id: str
    chapter_ids: list[str]
    difficulty: str = "mixed"
    count: int = 10


@router.post("/generate")
def generate_quiz_endpoint(payload: GenerateQuizRequest, db: Session = Depends(get_db)):
    book = db.get(m.Book, payload.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    valid_chapter_ids = {c.id for c in book.chapters}
    chapter_ids = [cid for cid in payload.chapter_ids if cid in valid_chapter_ids]
    if not chapter_ids:
        raise HTTPException(
            status_code=400, detail="chapter_ids must include at least one chapter of this book"
        )

    quiz = generate_quiz(db, book, chapter_ids, payload.difficulty, max(1, payload.count))
    return serialize_quiz(db, quiz)


@router.get("/{quiz_id}")
def get_quiz(quiz_id: str, db: Session = Depends(get_db)):
    quiz = db.get(m.Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return serialize_quiz(db, quiz)


class QuizAnswerEntry(BaseModel):
    question_id: str
    answer: str


class SubmitQuizRequest(BaseModel):
    answers: list[QuizAnswerEntry]


@router.post("/{quiz_id}/submit")
def submit_quiz(
    quiz_id: str,
    payload: SubmitQuizRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Grades each answer through the same write path a lesson question uses
    (app/scoring.answer_question) and returns an aggregate score alongside
    the per-question results, in the same shape POST /api/questions/{id}/answer
    returns for each one. Answers can be a subset of the quiz's questions —
    nothing requires submitting all of them in one call."""
    quiz = db.get(m.Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    quiz_question_ids = {qq.question_id for qq in quiz.quiz_questions}

    results = []
    answered_questions = []
    for entry in payload.answers:
        if entry.question_id not in quiz_question_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Question {entry.question_id} is not part of this quiz",
            )
        question = db.get(m.Question, entry.question_id)
        try:
            results.append(scoring.answer_question(db, question, entry.answer))
        except ValueError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        answered_questions.append(question)

    db.commit()

    # One shared `queued` set so two questions in this same submission that
    # both complete the same chapter (or book) don't each schedule their own
    # generation call.
    queued: set[str] = set()
    for question in answered_questions:
        maybe_trigger_auto_quiz(db, background_tasks, question, queued)

    total = len(results)
    correct = sum(1 for r in results if r["is_correct"])
    return {
        "quiz_id": quiz.id,
        "score": correct,
        "total": total,
        "percent": round(100 * correct / total) if total else 0,
        "results": results,
    }
