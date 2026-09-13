"""Write-path logic for answering a question.

Everything that changes when a student submits an answer lives here: the attempt
log, the lesson's mastery status, the streak, and the spaced-repetition item.
Read-side derivations stay in progress.py.

`answer_question()` is the single entry point that ties all of it together —
it's shared by POST /api/questions/{id}/answer and quiz submission
(POST /api/quizzes/{id}/submit, app/routers/quizzes.py), so a quiz question is
graded and tracked exactly like a lesson question: same MCQ check, same AI
grader for open response, same attempt log, same streak and review
scheduling. The only thing that doesn't apply to a quiz-only question (one
generated fresh to top up a quiz, with lesson_id null) is lesson mastery,
since it doesn't belong to a lesson.
"""

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app import models as m
from app.config import USER_ID
from app.grading import grade_open_response
from app.utils import utcnow_naive


def _check_mcq(question: m.Question, answer: str) -> bool:
    """MCQ is graded locally — no AI call, instant. Raises ValueError on a
    malformed answer; callers translate that to an HTTP 400."""
    try:
        chosen = int(answer.strip())
    except (ValueError, AttributeError):
        raise ValueError("MCQ answer must be an option index, sent as a string")
    options = question.options or []
    if not 0 <= chosen < len(options):
        raise ValueError(f"Option index {chosen} is out of range for this question")
    return chosen == question.correct_index


def _check_matching(question: m.Question, answer: dict) -> bool:
    """Correct iff every left_id maps to the matching right_id — all or
    nothing, no partial credit (a hackathon-scope call, not a rule the
    grading model was asked to weigh in on). left_id == right_id is the
    correct pairing by construction: both are the pair's index in
    Question.options (see app/progress._matching_fields)."""
    if not isinstance(answer, dict):
        raise ValueError("Matching answer must be an object mapping left_id to right_id")
    pairs = question.options or []
    if len(answer) != len(pairs):
        return False
    return all(answer.get(str(i)) == str(i) for i in range(len(pairs)))


def answer_question(db: Session, question: m.Question, answer) -> dict:
    """Grade one answer and apply every downstream effect. `answer` is a str
    for mcq/open, a {left_id: right_id} dict for matching. Raises ValueError
    on a malformed answer; does not commit — the caller commits once it has
    applied this (and, for a quiz, every other) answer."""
    if question.type == "mcq":
        is_correct = _check_mcq(question, answer)
        feedback = None
    elif question.type == "matching":
        is_correct = _check_matching(question, answer)
        feedback = None
    else:
        is_correct, feedback = grade_open_response(question, answer)

    # QuestionAttempt.answer is a Text column — a matching answer is a dict,
    # so it's JSON-encoded going in and decoded back out in
    # app/progress.serialize_question_for_lesson.
    stored_answer = json.dumps(answer, sort_keys=True) if question.type == "matching" else answer

    attempt = record_attempt(db, question, stored_answer, is_correct, feedback)
    db.flush()  # so the mastery recount below sees this attempt

    upsert_review_item(db, question, is_correct)
    lesson_status = recompute_lesson_status(db, question.lesson) if question.lesson_id else None
    streak_days = update_streak(db)

    correct_pairs = None
    if question.type == "matching":
        correct_pairs = {str(i): str(i) for i in range(len(question.options or []))}

    return {
        "question_id": question.id,
        "is_correct": is_correct,
        "correct_index": question.correct_index,
        "correct_pairs": correct_pairs,
        "explanation": question.explanation,
        "feedback": feedback,
        "lesson_status": lesson_status,
        "streak_days": streak_days,
        "attempt_number": attempt.attempt_number,
    }


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
