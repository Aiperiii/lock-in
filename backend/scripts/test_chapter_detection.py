"""Runs chapter detection end-to-end (DB included) against an already-uploaded
book and prints the resulting Chapter rows. Doesn't require a running server —
calls the same function the upload endpoint's background task calls.

Usage: python3 scripts/test_chapter_detection.py <book_id>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models as m  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.pipeline.chapters import detect_chapters_for_book  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    book_id = sys.argv[1]

    db = SessionLocal()
    book = db.get(m.Book, book_id)
    if book is None:
        print(f"No book with id {book_id!r}")
        sys.exit(1)
    print(f"Detecting chapters for {book.title!r} ({book.status})...")
    db.close()

    detect_chapters_for_book(book_id)

    db = SessionLocal()
    book = db.get(m.Book, book_id)
    chapters = (
        db.query(m.Chapter).filter_by(book_id=book_id).order_by(m.Chapter.number).all()
    )
    print(f"\nbook.status={book.status!r} book.processing_stage={book.processing_stage!r}")
    print(f"{len(chapters)} chapter row(s):")
    for chapter in chapters:
        text_path = Path(__file__).resolve().parent.parent / "uploads" / f"{chapter.id}.txt"
        length = len(text_path.read_text(encoding="utf-8")) if text_path.exists() else -1
        preview = text_path.read_text(encoding="utf-8")[:80].replace("\n", " ") if text_path.exists() else ""
        print(f"  #{chapter.number:>3} len={length:>8}  {chapter.title!r}")
        print(f"        opens: {preview!r}")
    db.close()


if __name__ == "__main__":
    main()
