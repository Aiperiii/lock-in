"""Seed the database from mock/course.json.

Loads the mock course as a full Book (chapters, lessons, blocks, questions),
then seeds progress so the demo has something to show immediately:

- Lesson 1.1 ("What Is an Algorithm?") is `mastered` — every question has a
  correct attempt.
- Lesson 1.2 ("Growth of Functions") is `in_progress` — of its 2 questions,
  1 has been answered correctly and 1 incorrectly. (The lesson only has 2
  questions in mock/course.json, not 3, so this is the closest honest match
  to "partially answered, not yet mastered".)
- A Streak of 6 days.

Safe to re-run: existing rows are cleared first.

Usage: python scripts/seed.py   (run from backend/)
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import models as m  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402

MOCK_COURSE_PATH = REPO_ROOT / "mock" / "course.json"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clear_all(session) -> None:
    """Delete existing rows, deepest tables first, so this script is idempotent."""
    for model in (
        m.AIMessage,
        m.AIConversation,
        m.ReviewItem,
        m.QuestionAttempt,
        m.LessonProgress,
        m.Block,
        m.Question,
        m.Lesson,
        m.Chapter,
        m.Book,
        m.Streak,
    ):
        session.query(model).delete()
    session.commit()


def build_question(session, lesson_id: str, q: dict) -> m.Question:
    question = m.Question(
        id=q["id"],
        lesson_id=lesson_id,
        type=q["type"],
        prompt=q["prompt"],
        options=q.get("options"),
        correct_index=q.get("correct_index"),
        hint=q.get("hint"),
        explanation=q["explanation"],
        model_answer=q.get("model_answer"),
        concept_tag=q["concept_tag"],
        difficulty=q["difficulty"],
        source=q["source"],
        parent_question_id=None,
    )
    session.add(question)
    return question


def build_lesson(session, chapter_id: str, lesson_json: dict) -> m.Lesson:
    lesson = m.Lesson(
        id=lesson_json["id"],
        chapter_id=chapter_id,
        number=lesson_json["number"],
        title=lesson_json["title"],
        estimated_minutes=lesson_json["estimated_minutes"],
        kind=lesson_json["kind"],
        concept_tags=lesson_json["concept_tags"],
    )
    session.add(lesson)

    for block_json in lesson_json["blocks"]:
        question_id = None
        if block_json["kind"] == "question":
            question = build_question(session, lesson.id, block_json["question"])
            question_id = question.id

        session.add(
            m.Block(
                id=block_json["id"],
                lesson_id=lesson.id,
                order=block_json["order"],
                kind=block_json["kind"],
                content=block_json.get("content"),
                question_id=question_id,
            )
        )

    return lesson


def build_chapter(session, book_id: str, chapter_json: dict) -> m.Chapter:
    chapter = m.Chapter(
        id=chapter_json["id"],
        book_id=book_id,
        number=chapter_json["number"],
        title=chapter_json["title"],
        summary=chapter_json.get("summary"),
    )
    session.add(chapter)

    for lesson_json in chapter_json["lessons"]:
        build_lesson(session, chapter.id, lesson_json)

    return chapter


def build_book(session, course: dict) -> m.Book:
    book = m.Book(
        id=course["id"],
        title=course["title"],
        author=course.get("author"),
        source_filename="introduction-to-algorithms.pdf",
        cover_seed=course["cover_seed"],
        status=course["status"],
        processing_stage=None,
        created_at=utcnow(),
    )
    session.add(book)

    for chapter_json in course["chapters"]:
        build_chapter(session, book.id, chapter_json)

    return book


def record_attempt(
    session, question: m.Question, answer: str, is_correct: bool, answered_at: datetime
) -> None:
    session.add(
        m.QuestionAttempt(
            user_id=1,
            question_id=question.id,
            answer=answer,
            is_correct=is_correct,
            feedback=None,
            attempt_number=1,
            answered_at=answered_at,
        )
    )


def seed_progress(session, book: m.Book) -> None:
    chapter_1 = next(c for c in book.chapters if c.number == 1)
    lesson_1_1 = next(l for l in chapter_1.lessons if l.number == 1)
    lesson_1_2 = next(l for l in chapter_1.lessons if l.number == 2)

    now = utcnow()

    # Lesson 1.1 — mastered: every question has a correct attempt.
    session.add(
        m.LessonProgress(
            user_id=1,
            lesson_id=lesson_1_1.id,
            status="mastered",
            started_at=now - timedelta(days=2),
            completed_at=now - timedelta(days=2, hours=-1),
        )
    )
    for question in lesson_1_1.questions:
        answer = str(question.correct_index) if question.type == "mcq" else question.model_answer
        record_attempt(session, question, answer, True, now - timedelta(days=2))

    # Lesson 1.2 — in_progress: 1 of its 2 questions answered correctly.
    session.add(
        m.LessonProgress(
            user_id=1,
            lesson_id=lesson_1_2.id,
            status="in_progress",
            started_at=now - timedelta(hours=3),
            completed_at=None,
        )
    )
    questions_1_2 = sorted(lesson_1_2.questions, key=lambda q: q.concept_tag)
    correct_q, wrong_q = questions_1_2[0], questions_1_2[1]
    record_attempt(session, correct_q, str(correct_q.correct_index), True, now - timedelta(hours=3))
    wrong_index = next(i for i in range(len(wrong_q.options)) if i != wrong_q.correct_index)
    record_attempt(session, wrong_q, str(wrong_index), False, now - timedelta(hours=2))


def seed_streak(session) -> None:
    session.add(
        m.Streak(
            user_id=1,
            current_days=6,
            longest_days=6,
            last_active_date=utcnow().date(),
        )
    )


def main() -> None:
    Base.metadata.create_all(bind=engine)

    with open(MOCK_COURSE_PATH) as f:
        course = json.load(f)

    session = SessionLocal()
    try:
        clear_all(session)
        book = build_book(session, course)
        session.flush()  # so relationships (book.chapters, etc.) are queryable below
        seed_progress(session, book)
        seed_streak(session)
        session.commit()
    finally:
        session.close()

    print(f"Seeded book {course['title']!r} ({course['id']})")


if __name__ == "__main__":
    main()
