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
from app.config import USER_ID
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
    """The pipeline writes a sidecar text file per chapter (app/pipeline/
    chapters.py) for any book it actually processed. A seeded or otherwise
    manually-inserted book has no such file, so this falls back to the
    chapter's own lesson prose (Block rows) — thinner, but real content
    rather than an empty prompt that leaves the model nothing to ground on."""
    path = UPLOADS_DIR / f"{chapter.id}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    prose = [
        block.content
        for lesson in chapter.lessons
        for block in lesson.blocks
        if block.kind in ("prose", "definition", "example") and block.content
    ]
    return "\n\n".join(prose)


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


def quiz_summary(db: Session, quiz_id: str | None) -> dict | None:
    """Lightweight readiness summary for a book-page listing — the "End of
    chapter/course quiz" rows and the "Additional quizzes" section — without
    pulling the whole quiz payload the way serialize_quiz does.

    `completed` mirrors a lesson's done/not_started split, not the mastery
    rule: a quiz has no per-question retry loop of its own on the book page,
    so "you've gone through it" is the only distinction that matters here.

    `score` is null until at least one question's been attempted, then
    tracks live: correct count (by each question's latest attempt, so a
    corrected retry counts) out of the full question_count — so a
    part-way-through quiz honestly shows partial credit rather than hiding
    the score until `completed`.
    """
    if quiz_id is None:
        return None
    quiz = db.get(m.Quiz, quiz_id)
    if quiz is None:
        return None

    question_ids = [qq.question_id for qq in quiz.quiz_questions]
    # Ordered ascending by answered_at so, for a question answered more than
    # once, the dict's last write per question_id ends up holding its LATEST
    # attempt's is_correct rather than its first.
    latest_is_correct: dict[str, bool] = {}
    for question_id, is_correct in (
        db.query(m.QuestionAttempt.question_id, m.QuestionAttempt.is_correct)
        .filter(
            m.QuestionAttempt.user_id == USER_ID,
            m.QuestionAttempt.question_id.in_(question_ids),
        )
        .order_by(m.QuestionAttempt.answered_at)
    ):
        latest_is_correct[question_id] = is_correct

    attempted_ids = set(latest_is_correct.keys())
    completed = bool(question_ids) and attempted_ids == set(question_ids)
    score = (
        {"correct": sum(latest_is_correct.values()), "total": len(question_ids)}
        if attempted_ids
        else None
    )

    return {
        "id": quiz.id,
        "difficulty": quiz.difficulty,
        "question_count": len(question_ids),
        "completed": completed,
        "score": score,
    }


def list_manual_quizzes(db: Session, book: m.Book) -> list[dict]:
    """Quizzes for this book generated through the manual POST
    /api/quizzes/generate flow (the "Generate quiz" modal) — everything
    EXCEPT the automatic end-of-chapter/course ones already surfaced inline
    on the book page (app/pipeline/auto_quiz.py).

    There's no separate "kind" column marking a quiz as automatic vs.
    manual: a quiz is automatic exactly when some Chapter.quiz_id or
    Book.final_quiz_id points at it, so that set is computed directly here
    rather than duplicated as stored state that could drift out of sync.

    Ordered oldest-first (by created_at ascending) rather than the usual
    newest-first listing convention, since the frontend numbers these "Quiz
    1", "Quiz 2", ... by position in this list — numbering only reads
    sensibly if that position matches creation order top to bottom.
    """
    auto_ids = {chapter.quiz_id for chapter in book.chapters if chapter.quiz_id}
    if book.final_quiz_id:
        auto_ids.add(book.final_quiz_id)

    query = db.query(m.Quiz).filter(m.Quiz.book_id == book.id)
    if auto_ids:
        query = query.filter(m.Quiz.id.notin_(auto_ids))
    quizzes = query.order_by(m.Quiz.created_at.asc()).all()

    return [quiz_summary(db, quiz.id) for quiz in quizzes]
