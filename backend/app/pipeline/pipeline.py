"""Orchestrates the full PDF -> course pipeline as one background task:
chapter detection -> lesson splitting per chapter -> block generation per
lesson (docs/BUILD.md B6). Triggered once, right after upload.

Any unhandled failure anywhere in the chain marks the book `failed` with a
readable processing_stage — the pipeline must never leave a book stuck at
"processing" forever, nor crash the background task silently. (Each stage's
own module already does the same for calls it makes directly; this is the
outermost backstop.)
"""

import logging

from app import models as m
from app.database import SessionLocal
from app.pipeline import blocks, chapters, lessons, titles

logger = logging.getLogger(__name__)


def process_book(book_id: str) -> None:
    db = SessionLocal()
    try:
        book = db.get(m.Book, book_id)
        if book is None:
            return
        try:
            try:
                titles.refine_if_messy(db, book)
            except Exception:
                # A better title is a nice-to-have, not a core pipeline
                # stage — the cleaned-filename title already in place is a
                # perfectly fine fallback, so this never aborts the book.
                logger.warning("title refinement failed for book %s", book_id, exc_info=True)
                db.rollback()

            chapters.run_for_book(db, book)
            for chapter in book.chapters:
                lessons.run_for_chapter(db, chapter)
                for lesson in chapter.lessons:
                    blocks.run_for_lesson(db, lesson)

            book.status = "ready"
            book.processing_stage = None
            db.commit()
        except Exception as exc:
            logger.exception("pipeline failed for book %s", book_id)
            db.rollback()
            book = db.get(m.Book, book_id)
            book.status = "failed"
            book.processing_stage = f"Processing failed: {exc}"
            db.commit()
    finally:
        db.close()
