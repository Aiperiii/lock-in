"""Write-path logic for answering a question.

Everything that changes when a student submits an answer lives here: the attempt
log, the lesson's mastery status, the streak, and the spaced-repetition item.
Read-side derivations stay in progress.py.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from app import models as m
from app.config import USER_ID
from app.utils import utcnow_naive


def record_attempt(
    db: Session,
    question: m.Question,
    answer: str,
    is_correct: bool,
    feedback: str | None,
) -> m.QuestionAttempt:
    """Log every attempt, retries included — nothing is overwritten."""
    prior_attempts = (
        db.query(m.QuestionAttempt)
        .filter_by(user_id=USER_ID, question_id=question.id)
        .count()
    )
    attempt = m.QuestionAttempt(
        user_id=USER_ID,
        question_id=question.id,
        answer=answer,
        is_correct=is_correct,
        feedback=feedback,
        attempt_number=prior_attempts + 1,
        answered_at=utcnow_naive(),
    )
    db.add(attempt)
    return attempt


def recompute_lesson_status(db: Session, lesson: m.Lesson) -> str:
    """Apply the mastery rule from docs/SCHEMA.md: a lesson is `mastered` when
    every question belonging to it has at least one correct attempt. Retries are
    expected, so a later wrong answer never revokes mastery.

    A lesson already marked `done` stays `done` until it earns `mastered` —
    reaching the end is not something an extra attempt can undo.
    """
    question_ids = [question.id for question in lesson.questions]
    correct_ids = {
        row[0]
        for row in db.query(m.QuestionAttempt.question_id)
        .filter(
            m.QuestionAttempt.user_id == USER_ID,
            m.QuestionAttempt.question_id.in_(question_ids),
            m.QuestionAttempt.is_correct.is_(True),
        )
        .distinct()
    }
    all_correct = bool(question_ids) and all(qid in correct_ids for qid in question_ids)

    now = utcnow_naive()
    progress = (
        db.query(m.LessonProgress)
        .filter_by(user_id=USER_ID, lesson_id=lesson.id)
        .first()
    )
    if progress is None:
        progress = m.LessonProgress(
            user_id=USER_ID,
            lesson_id=lesson.id,
            status="in_progress",
            started_at=now,
        )
        db.add(progress)
    elif progress.started_at is None:
        progress.started_at = now

    if all_correct:
        progress.status = "mastered"
        if progress.completed_at is None:
            progress.completed_at = now
    elif progress.status != "done":
        progress.status = "in_progress"

    return progress.status


def update_streak(db: Session) -> int:
    """Same day = no change; consecutive day = increment; gap = reset to 1."""
    today = utcnow_naive().date()
    streak = db.get(m.Streak, USER_ID)

    if streak is None:
        db.add(
            m.Streak(
                user_id=USER_ID,
                current_days=1,
                longest_days=1,
                last_active_date=today,
            )
        )
        return 1

    last_active = streak.last_active_date
    if last_active == today:
        pass
    elif last_active is not None and (today - last_active).days == 1:
        streak.current_days += 1
    else:
        streak.current_days = 1

    streak.last_active_date = today
    streak.longest_days = max(streak.longest_days, streak.current_days)
    return streak.current_days


def upsert_review_item(
    db: Session, question: m.Question, is_correct: bool
) -> m.ReviewItem:
    """SM-2-lite, per docs/SCHEMA.md:
    correct → interval = max(1, interval * ease), ease += 0.1 (cap 3.0)
    wrong   → interval = 1, ease = max(1.3, ease - 0.2)
    due_at  = now + interval_days
    """
    item = (
        db.query(m.ReviewItem)
        .filter_by(user_id=USER_ID, question_id=question.id)
        .first()
    )
    if item is None:
        # Created the first time a question is answered. interval starts at 0 so
        # a first correct answer schedules it one day out.
        item = m.ReviewItem(
            user_id=USER_ID,
            question_id=question.id,
            concept_tag=question.concept_tag,
            due_at=utcnow_naive(),
            interval_days=0.0,
            ease=2.5,
        )
        db.add(item)

    if is_correct:
        item.interval_days = max(1.0, item.interval_days * item.ease)
        item.ease = min(3.0, item.ease + 0.1)
    else:
        item.interval_days = 1.0
        item.ease = max(1.3, item.ease - 0.2)

    item.due_at = utcnow_naive() + timedelta(days=item.interval_days)
    return item
