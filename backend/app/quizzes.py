"""Quiz generation and serialization — the manual quiz feature from
docs/API.md, which had no implementation yet (only the route names were
documented).

Selection logic (docs/API.md): "prefer unused book-sourced questions from the
chosen chapters, top up with freshly generated ones." Here, "unused" means
not already attached to an earlier quiz via QuizQuestion — a book-sourced
question still gets answered plenty of times as part of its own lesson; a
quiz just avoids handing out the same one across two separate quizzes.

Freshly generated top-up questions are persisted as ordinary Question rows
with lesson_id left null (see the comment on Question.lesson_id in
models.py), so they're answerable through the exact same
POST /api/questions/{id}/answer machinery as a lesson question — MCQ checked
locally, open response graded by the same grader, every attempt logged,
review-item scheduling included (see app/scoring.py). The one thing that
doesn't apply to them is lesson mastery, since they have no lesson.
"""

import logging
import random

from sqlalchemy.orm import Session

from app import models as m
from app.ai.client import MODEL_FAST, GeminiUnavailable, generate_json
from app.ai.prompts import quiz_generation_prompt
from app.paths import UPLOADS_DIR
from app.pipeline.jsonutil import coerce_list
from app.pipeline.validate import validate_question
from app.progress import serialize_question_for_lesson
from app.utils import iso8601

logger = logging.getLogger(__name__)

# Bounds how much chapter text goes into one top-up call — a whole chapter of
# a real textbook can be huge, and this call only needs enough to write a
# handful of grounded questions, not the full text block generation gets.
CHARS_PER_CHAPTER_CAP = 20_000


def generate_quiz(
    db: Session, book: m.Book, chapter_ids: list[str], difficulty: str, count: int
) -> m.Quiz:
    chapters = [c for c in book.chapters if c.id in chapter_ids]
    lessons = [lesson for chapter in chapters for lesson in chapter.lessons]
    bank_questions = [q for lesson in lessons for q in lesson.questions if q.source == "book"]

    scoped = (
        bank_questions
        if difficulty == "mixed"
        else [q for q in bank_questions if q.difficulty == difficulty]
    )

    used_ids = {row[0] for row in db.query(m.QuizQuestion.question_id).distinct()}
    unused = [q for q in scoped if q.id not in used_ids]
    random.shuffle(unused)

    selected: list[m.Question] = unused[:count]
    remaining = count - len(selected)
    if remaining > 0:
        selected += _generate_fresh_questions(
            db, chapters, lessons, difficulty, remaining, existing=bank_questions
        )

    quiz = m.Quiz(book_id=book.id, chapter_ids=chapter_ids, difficulty=difficulty)
    db.add(quiz)
    db.flush()  # populates quiz.id

    for order, question in enumerate(selected):
        db.add(m.QuizQuestion(quiz_id=quiz.id, question_id=question.id, order=order))

    db.commit()
    return quiz


def _generate_fresh_questions(
    db: Session,
    chapters: list[m.Chapter],
    lessons: list[m.Lesson],
    difficulty: str,
    count: int,
    existing: list[m.Question],
) -> list[m.Question]:
    """Never raises — if Gemini is unavailable or returns nothing usable, the
    quiz just ships with fewer questions than requested rather than failing
    outright (the same generous-degradation stance as the rest of the AI
    call sites)."""
    concept_tags = sorted({tag for lesson in lessons for tag in (lesson.concept_tags or [])})
    source_text = "\n\n".join(_chapter_text(chapter)[:CHARS_PER_CHAPTER_CAP] for chapter in chapters)
    existing_prompts = [q.prompt for q in existing]

    try:
        raw = generate_json(
            quiz_generation_prompt(count, difficulty, concept_tags, source_text, existing_prompts),
            model=MODEL_FAST,
        )
    except GeminiUnavailable:
        logger.warning("quiz generation: Gemini unavailable, shipping quiz with fewer questions")
        return []
    except Exception:
        logger.warning("quiz generation: generate_json raised", exc_info=True)
        return []

    entries = coerce_list(raw, key_hint="questions")
    created: list[m.Question] = []
    for entry in entries[:count]:
        validated = validate_question(entry)
        if not validated:
            continue
        # Force "ai" regardless of what the model claimed — a quiz top-up
        # question was never literally lifted from the book's own exercises,
        # and CLAUDE.md's "from the textbook" tag depends on `source` being
        # trustworthy.
        validated["source"] = "ai"
        question = m.Question(lesson_id=None, **validated)
        db.add(question)
        created.append(question)

    if created:
        db.flush()  # populates each question.id for the QuizQuestion rows above
    return created


def _chapter_text(chapter: m.Chapter) -> str:
    path = UPLOADS_DIR / f"{chapter.id}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def serialize_quiz(db: Session, quiz: m.Quiz) -> dict:
    """Same question shape as a lesson's (serialize_question_for_lesson) —
    docs/API.md: "Returns a quiz with questions in the same shape as lesson
    questions" — so correct_index/explanation/model_answer stay null until
    each question has an attempt, exactly like the lesson reading view."""
    return {
        "id": quiz.id,
        "book_id": quiz.book_id,
        "chapter_ids": quiz.chapter_ids,
        "difficulty": quiz.difficulty,
        "created_at": iso8601(quiz.created_at),
        "questions": [
            serialize_question_for_lesson(db, qq.question) for qq in quiz.quiz_questions
        ],
    }
