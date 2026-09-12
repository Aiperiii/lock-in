"""Automatic quiz generation triggers.

Two trigger conditions, both just app/quizzes.generate_quiz() with a
different chapter scope and a completion check — no new selection or
generation logic:

- End-of-chapter: every lesson in a chapter becomes `done` or `mastered` ->
  generate one quiz scoped to that chapter, recorded on Chapter.quiz_id.
- End-of-course: every chapter in the book reaches that same completion ->
  generate one larger quiz scoped to every chapter in the book, recorded on
  Book.final_quiz_id.

Checked right after a lesson's LessonProgress status changes, since that's
the only place completion can newly happen. Generation itself always runs as
a FastAPI background task — it can call Gemini, which must never block the
request that triggered it — each with its own DB session (the pattern
app/pipeline/pipeline.py already uses for the upload pipeline).
"""

import logging

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app import models as m
from app.database import SessionLocal
from app.progress import lesson_status
from app.quizzes import generate_quiz

logger = logging.getLogger(__name__)

DONE_STATUSES = ("done", "mastered")
CHAPTER_QUIZ_COUNT = 10
COURSE_QUIZ_COUNT = 20


def _chapter_complete(db: Session, chapter: m.Chapter) -> bool:
    if not chapter.lessons:
        return False
    return all(lesson_status(db, lesson.id) in DONE_STATUSES for lesson in chapter.lessons)


def maybe_trigger_auto_quiz(
    db: Session,
    background_tasks: BackgroundTasks,
    question: m.Question,
    queued: set[str] | None = None,
) -> None:
    """Call once per answered question, after its attempt is committed.
    Cheap (a handful of status lookups, no AI call on this request's time)
    unless the answer just completed a chapter or the whole book.

    `queued` lets a caller answering several questions in one request (quiz
    submission) share one set across the whole batch, so two questions that
    both complete the same chapter in the same request don't each schedule
    their own generation call.
    """
    if question.lesson_id is None:
        return  # a quiz-only question isn't part of any chapter

    if queued is None:
        queued = set()

    chapter = question.lesson.chapter
    if chapter.id in queued or chapter.quiz_id is not None:
        pass  # already has one, or already queued this request
    elif _chapter_complete(db, chapter):
        queued.add(chapter.id)
        logger.info("chapter %s complete — queuing chapter quiz", chapter.id)
        background_tasks.add_task(_generate_chapter_quiz_task, chapter.id)

    book = chapter.book
    if book.id in queued or book.final_quiz_id is not None:
        return
    if all(_chapter_complete(db, c) for c in book.chapters):
        queued.add(book.id)
        logger.info("book %s complete — queuing end-of-course quiz", book.id)
        background_tasks.add_task(_generate_course_quiz_task, book.id)


def _generate_chapter_quiz_task(chapter_id: str) -> None:
    db = SessionLocal()
    try:
        chapter = db.get(m.Chapter, chapter_id)
        if chapter is None or chapter.quiz_id is not None:
            return
        try:
            quiz = generate_quiz(db, chapter.book, [chapter.id], "mixed", CHAPTER_QUIZ_COUNT)
            chapter.quiz_id = quiz.id
            db.commit()
            logger.info("end-of-chapter quiz ready: chapter=%s quiz=%s", chapter_id, quiz.id)
        except Exception:
            logger.exception("chapter quiz generation failed for chapter %s", chapter_id)
            db.rollback()
    finally:
        db.close()


def _generate_course_quiz_task(book_id: str) -> None:
    db = SessionLocal()
    try:
        book = db.get(m.Book, book_id)
        if book is None or book.final_quiz_id is not None:
            return
        try:
            chapter_ids = [c.id for c in book.chapters]
            quiz = generate_quiz(db, book, chapter_ids, "mixed", COURSE_QUIZ_COUNT)
            book.final_quiz_id = quiz.id
            db.commit()
            logger.info("end-of-course quiz ready: book=%s quiz=%s", book_id, quiz.id)
        except Exception:
            logger.exception("course quiz generation failed for book %s", book_id)
            db.rollback()
    finally:
        db.close()
