"""Block generation: turns one lesson's text into interleaved prose/question
Block rows, using the prompt in docs/PROMPTS.md section 3 — "the call that
defines the product" (CLAUDE.md).

One call per lesson, batched per lesson rather than per question (per
CLAUDE.md's rate-limit guidance), on MODEL_FAST — same high-volume reasoning
as lesson splitting.

Unlike chapter/lesson splitting, block content comes back already assembled —
no fuzzy-matching needed. The model returns each block's actual prose or
question content directly, in order, rather than a marker to locate.

Every question field the DB requires NOT NULL is validated before a Question
row is created; a block whose question doesn't validate is dropped rather
than crashing the whole lesson. If nothing at all comes out usable, this
falls back to a single prose block holding the lesson's raw text verbatim, so
a lesson is never left with zero content. GeminiUnavailable propagates.
"""

import logging

from sqlalchemy.orm import Session

from app import models as m
from app.ai.client import MODEL_FAST, GeminiUnavailable, generate_json
from app.ai.prompts import block_generation_prompt
from app.database import SessionLocal
from app.paths import UPLOADS_DIR
from app.pipeline.jsonutil import coerce_list
from app.pipeline.lessons import estimate_minutes
from app.pipeline.validate import validate_question as _validate_question

logger = logging.getLogger(__name__)


def generate_blocks_for_lesson(lesson_id: str) -> None:
    """Standalone entry point for independent testing. Opens its own DB
    session and marks the owning book `failed` on any unhandled error."""
    db = SessionLocal()
    try:
        lesson = db.get(m.Lesson, lesson_id)
        if lesson is None:
            return
        try:
            run_for_lesson(db, lesson)
        except Exception as exc:
            db.rollback()
            lesson = db.get(m.Lesson, lesson_id)
            book = lesson.chapter.book
            book.status = "failed"
            book.processing_stage = f"Block generation failed: {exc}"
            db.commit()
    finally:
        db.close()


def run_for_lesson(db: Session, lesson: m.Lesson) -> list[m.Block]:
    """Generates Block (and Question) rows for `lesson`, and refines its
    estimated_minutes now that the real question count is known."""
    text = (UPLOADS_DIR / f"{lesson.id}.txt").read_text(encoding="utf-8")

    book = lesson.chapter.book
    book.processing_stage = f"Generating blocks for lesson {lesson.number}: {lesson.title}"
    db.commit()

    blocks_data = _generate_blocks(text, lesson.title)

    created: list[m.Block] = []
    question_count = 0
    for order, block_data in enumerate(blocks_data):
        if block_data["kind"] == "question":
            q = block_data["question"]
            question = m.Question(
                lesson_id=lesson.id,
                type=q["type"],
                prompt=q["prompt"],
                options=q["options"],
                correct_index=q["correct_index"],
                hint=q["hint"],
                explanation=q["explanation"],
                model_answer=q["model_answer"],
                concept_tag=q["concept_tag"],
                difficulty=q["difficulty"],
                source=q["source"],
            )
            db.add(question)
            db.flush()  # populates question.id
            row = m.Block(
                lesson_id=lesson.id, order=order, kind="question", question_id=question.id
            )
            question_count += 1
        else:
            row = m.Block(
                lesson_id=lesson.id, order=order, kind="prose", content=block_data["content"]
            )
        db.add(row)
        created.append(row)

    lesson.estimated_minutes = estimate_minutes(len(text.split()), question_count)
    db.commit()

    return created


def _generate_blocks(text: str, lesson_title: str) -> list[dict]:
    """Returns a normalized list of {"kind": "prose", "content"} or
    {"kind": "question", "question": {...validated fields...}} dicts. Never
    raises or returns empty — falls back to one prose block with the raw
    lesson text."""
    entries = _ask_gemini(text, lesson_title)

    result: list[dict] = []
    for entry in entries:
        if entry.get("kind") == "prose":
            content = (entry.get("content") or "").strip()
            if content:
                result.append({"kind": "prose", "content": content})
        elif entry.get("kind") == "question":
            question = _validate_question(entry.get("question"))
            if question:
                result.append({"kind": "question", "question": question})
        # anything else (missing/garbage "kind") is silently dropped

    if not result:
        return [{"kind": "prose", "content": text}]
    return result


def _ask_gemini(text: str, lesson_title: str) -> list[dict]:
    try:
        raw = generate_json(block_generation_prompt(lesson_title, text), model=MODEL_FAST)
    except GeminiUnavailable:
        raise
    except Exception:
        logger.warning("block generation: generate_json raised", exc_info=True)
        return []
    entries = coerce_list(raw, key_hint="blocks")
    if not entries:
        logger.warning("block generation: parsed JSON had no usable blocks: %r", raw)
    return entries
