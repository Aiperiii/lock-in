"""Lesson splitting: turns one chapter's text into Lesson rows, using the
prompt in docs/PROMPTS.md section 2.

Unlike chapter detection, this is a single call per chapter — no multi-window
loop. The demo book is single-chapter and modest in length, and even a large
chapter fits in one call (Gemini's rate limit is per request, not per token,
per CLAUDE.md). Uses MODEL_FAST: this runs once per chapter rather than once
per book, much higher volume than chapter detection.

Lesson start_markers are located within the CHAPTER's own text (not the whole
book) via the same fuzzy matching as chapter detection (see
app/pipeline/matching.py), but without the TOC-vs-body disambiguation —
there's no table-of-contents-like structure inside a single chapter to
confuse a lesson boundary with, so the first located occurrence is used
directly.

Failure modes mirror chapter detection: a content-level failure (bad/empty
JSON, no locatable markers) falls back to one lesson spanning the chapter;
GeminiUnavailable (both model tiers rate-limited) propagates so the caller can
mark the book `failed` rather than paper over an infrastructure problem.
"""

import logging

from sqlalchemy.orm import Session

from app import models as m
from app.ai.client import MODEL_FAST, GeminiUnavailable, generate_json
from app.ai.prompts import lesson_splitting_prompt
from app.database import SessionLocal
from app.paths import UPLOADS_DIR
from app.pipeline.jsonutil import coerce_list
from app.pipeline.matching import find_occurrences

logger = logging.getLogger(__name__)

WORDS_PER_MINUTE = 200
MINUTES_PER_QUESTION = 1

VALID_KINDS = ("reading", "practice")


def estimate_minutes(word_count: int, question_count: int = 0) -> int:
    """docs/SCHEMA.md: "estimated_minutes ... from word count + question
    count." Before block generation runs, question_count is 0 — a rough
    estimate from prose length alone, refined once blocks exist."""
    return max(1, round(word_count / WORDS_PER_MINUTE) + question_count * MINUTES_PER_QUESTION)


def split_lessons_for_chapter(chapter_id: str) -> None:
    """Standalone entry point for independent testing (docs/BUILD.md: "test
    each stage... before moving to the next"). Opens its own DB session and
    marks the owning book `failed` on any unhandled error."""
    db = SessionLocal()
    try:
        chapter = db.get(m.Chapter, chapter_id)
        if chapter is None:
            return
        try:
            run_for_chapter(db, chapter)
        except Exception as exc:
            db.rollback()
            chapter = db.get(m.Chapter, chapter_id)
            book = chapter.book
            book.status = "failed"
            book.processing_stage = f"Lesson splitting failed: {exc}"
            db.commit()
    finally:
        db.close()


def run_for_chapter(db: Session, chapter: m.Chapter) -> list[m.Lesson]:
    """Splits `chapter` into Lesson rows and their text sidecars."""
    text = (UPLOADS_DIR / f"{chapter.id}.txt").read_text(encoding="utf-8")

    book = chapter.book
    book.processing_stage = f"Splitting chapter {chapter.number} into lessons"
    db.commit()

    lessons_data = _split_lesson_boundaries(text, chapter.title)

    created: list[m.Lesson] = []
    for lesson_data in lessons_data:
        row = m.Lesson(
            chapter_id=chapter.id,
            number=lesson_data["number"],
            title=lesson_data["title"],
            estimated_minutes=estimate_minutes(len(lesson_data["text"].split())),
            kind=lesson_data["kind"],
            concept_tags=lesson_data["concept_tags"],
        )
        db.add(row)
        db.flush()  # populates row.id
        (UPLOADS_DIR / f"{row.id}.txt").write_text(lesson_data["text"], encoding="utf-8")
        created.append(row)
    db.commit()

    return created


def _split_lesson_boundaries(text: str, chapter_title: str) -> list[dict]:
    """Returns [{"number", "title", "kind", "concept_tags", "text"}, ...] in
    order. Never raises or returns empty — falls back to one lesson spanning
    the whole chapter."""
    entries = _ask_gemini(text, chapter_title)

    placed: list[dict] = []
    search_floor = 0
    for entry in entries:
        marker = (entry.get("start_marker") or "").strip()
        if not marker:
            continue
        offsets = find_occurrences(marker, text, search_floor)
        if not offsets:
            continue
        offset = offsets[0]
        raw_number = entry.get("number")
        title = (entry.get("title") or "").strip() or f"Lesson {len(placed) + 1}"
        kind = entry.get("kind") if entry.get("kind") in VALID_KINDS else "reading"
        tags = entry.get("concept_tags")
        concept_tags = [str(t) for t in tags] if isinstance(tags, list) else []
        number = raw_number if isinstance(raw_number, int) else len(placed) + 1
        placed.append(
            {
                "number": number,
                "title": title,
                "kind": kind,
                "concept_tags": concept_tags,
                "start_offset": offset,
            }
        )
        search_floor = offset + len(marker)

    if not placed:
        return [
            {
                "number": 1,
                "title": chapter_title,
                "kind": "reading",
                "concept_tags": [],
                "text": text,
            }
        ]

    placed.sort(key=lambda lesson: lesson["start_offset"])
    return [
        {
            "number": lesson["number"],
            "title": lesson["title"],
            "kind": lesson["kind"],
            "concept_tags": lesson["concept_tags"],
            "text": text[
                lesson["start_offset"] : (
                    placed[i + 1]["start_offset"] if i + 1 < len(placed) else len(text)
                )
            ],
        }
        for i, lesson in enumerate(placed)
    ]


def _ask_gemini(text: str, chapter_title: str) -> list[dict]:
    try:
        raw = generate_json(lesson_splitting_prompt(chapter_title, text), model=MODEL_FAST)
    except GeminiUnavailable:
        raise
    except Exception:
        logger.warning("lesson splitting: generate_json raised", exc_info=True)
        return []
    entries = coerce_list(raw)
    if not entries:
        logger.warning("lesson splitting: parsed JSON had no usable lesson entries: %r", raw)
    return entries
