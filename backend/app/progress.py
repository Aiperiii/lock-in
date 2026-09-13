"""Progress is always derived live from LessonProgress / QuestionAttempt rows —
nothing here is cached or stored (see docs/SCHEMA.md: "Percentages are computed
from these rows, never stored, so nothing goes stale").
"""

import json
import random
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models as m
from app.config import USER_ID
from app.utils import iso8601


def lesson_status(db: Session, lesson_id: str) -> str:
    progress = (
        db.query(m.LessonProgress)
        .filter_by(user_id=USER_ID, lesson_id=lesson_id)
        .first()
    )
    return progress.status if progress else "not_started"


def _lesson_ids(book: m.Book) -> list[str]:
    return [lesson.id for chapter in book.chapters for lesson in chapter.lessons]


def book_progress_percent(db: Session, book: m.Book) -> int:
    """Percent of the book's lessons that are mastered."""
    lesson_ids = _lesson_ids(book)
    if not lesson_ids:
        return 0
    mastered = (
        db.query(m.LessonProgress)
        .filter(
            m.LessonProgress.user_id == USER_ID,
            m.LessonProgress.lesson_id.in_(lesson_ids),
            m.LessonProgress.status == "mastered",
        )
        .count()
    )
    return round(100 * mastered / len(lesson_ids))


def book_last_opened_at(db: Session, book: m.Book) -> datetime | None:
    """The most recent time any of the book's lessons was started — there is no
    dedicated "opened" event, so LessonProgress.started_at stands in for it."""
    lesson_ids = _lesson_ids(book)
    if not lesson_ids:
        return None
    return (
        db.query(func.max(m.LessonProgress.started_at))
        .filter(
            m.LessonProgress.user_id == USER_ID,
            m.LessonProgress.lesson_id.in_(lesson_ids),
        )
        .scalar()
    )


def latest_attempt(db: Session, question_id: str) -> m.QuestionAttempt | None:
    return (
        db.query(m.QuestionAttempt)
        .filter_by(user_id=USER_ID, question_id=question_id)
        .order_by(m.QuestionAttempt.attempt_number.desc())
        .first()
    )


def _matching_fields(question: m.Question, reveal: bool) -> dict:
    """left/right items for a matching question. The right side is shuffled
    on every call — nothing persists a shown order, so a reload shuffles
    again, same as a fresh MCQ option order would carry no meaning either.
    Each item keeps the id of its canonical pair index (its position in
    Question.options), which IS the correct pairing: left_id == right_id.
    That's never sent as such — `correct_pairs` stays null until `reveal` —
    simply because the shuffle already hides it, not because anything else
    is withheld."""
    pairs = question.options or []
    left_items = [{"id": str(i), "text": pair.get("left")} for i, pair in enumerate(pairs)]
    right_items = [{"id": str(i), "text": pair.get("right")} for i, pair in enumerate(pairs)]
    random.shuffle(right_items)
    return {
        "left_items": left_items,
        "right_items": right_items,
        "correct_pairs": {str(i): str(i) for i in range(len(pairs))} if reveal else None,
    }


_MATCHING_NULL_FIELDS = {"left_items": None, "right_items": None, "correct_pairs": None}


def serialize_question_redacted(question: m.Question) -> dict:
    """Question shape for contexts with no per-attempt awareness (book detail):
    the answer-revealing fields are always blanked out."""
    base = {
        "id": question.id,
        "type": question.type,
        "prompt": question.prompt,
        "options": None if question.type == "matching" else question.options,
        "correct_index": None,
        "hint": question.hint,
        "explanation": None,
        "model_answer": None,
        "concept_tag": question.concept_tag,
        "difficulty": question.difficulty,
        "source": question.source,
        **_MATCHING_NULL_FIELDS,
    }
    if question.type == "matching":
        base.update(_matching_fields(question, reveal=False))
    return base


def serialize_question_for_lesson(db: Session, question: m.Question) -> dict:
    """Question shape for the lesson reading view (and the quiz page, which
    reuses it — see app/quizzes.serialize_quiz).

    correct_index/explanation/model_answer (mcq, open) and correct_pairs
    (matching) carry real values only once the question has an attempt — per
    docs/API.md they are 'never sent to the client before an answer is
    submitted'. The keys are always present and null until then, so the
    client renders against one stable shape regardless of question type.
    """
    attempt = latest_attempt(db, question.id)
    answered = attempt is not None
    base = {
        "id": question.id,
        "type": question.type,
        "prompt": question.prompt,
        "options": None if question.type == "matching" else question.options,
        "hint": question.hint,
        "concept_tag": question.concept_tag,
        "difficulty": question.difficulty,
        "source": question.source,
        "correct_index": question.correct_index if answered else None,
        "explanation": question.explanation if answered else None,
        "model_answer": question.model_answer if answered else None,
        **_MATCHING_NULL_FIELDS,
        "user_attempt": {
            "answer": json.loads(attempt.answer) if question.type == "matching" else attempt.answer,
            "is_correct": attempt.is_correct,
            "feedback": attempt.feedback,
            "attempt_number": attempt.attempt_number,
            "answered_at": iso8601(attempt.answered_at),
        }
        if answered
        else None,
    }
    if question.type == "matching":
        base.update(_matching_fields(question, reveal=answered))
    return base
