"""Debug helper: mark every lesson in a chapter as mastered for user_id 1,
then run the exact same end-of-chapter quiz generation the real trigger runs
(app/pipeline/auto_quiz._generate_chapter_quiz_task — called directly, not
reimplemented) — so the "End of chapter quiz" card can be seen on the book
page without manually answering every question in the chapter.

Usage:
    python scripts/force_complete_chapter.py <chapter_id>

Find a chapter id with:
    sqlite3 backend/lockedin.db "SELECT id, number, title FROM chapters;"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models as m  # noqa: E402
from app.config import USER_ID  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.pipeline.auto_quiz import _generate_chapter_quiz_task  # noqa: E402
from app.utils import utcnow_naive  # noqa: E402


def main(chapter_id: str) -> None:
    db = SessionLocal()
    try:
        chapter = db.get(m.Chapter, chapter_id)
        if chapter is None:
            print(f"no chapter with id {chapter_id}")
            return
        if not chapter.lessons:
            print(f"chapter {chapter.number} ({chapter.title!r}) has no lessons")
            return

        now = utcnow_naive()
        for lesson in chapter.lessons:
            progress = (
                db.query(m.LessonProgress).filter_by(user_id=USER_ID, lesson_id=lesson.id).first()
            )
            if progress is None:
                progress = m.LessonProgress(
                    user_id=USER_ID,
                    lesson_id=lesson.id,
                    status="mastered",
                    started_at=now,
                    completed_at=now,
                )
                db.add(progress)
            else:
                progress.status = "mastered"
                if progress.completed_at is None:
                    progress.completed_at = now
        db.commit()
        print(f"marked {len(chapter.lessons)} lesson(s) in chapter {chapter.number} ({chapter.title!r}) as mastered")
    finally:
        db.close()

    print("running end-of-chapter quiz generation (same function the real trigger calls)...")
    _generate_chapter_quiz_task(chapter_id)

    db = SessionLocal()
    try:
        chapter = db.get(m.Chapter, chapter_id)
        if chapter.quiz_id:
            print(f"done — chapter.quiz_id = {chapter.quiz_id}")
        else:
            print("quiz_id is still null — generation likely failed, check the server log")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/force_complete_chapter.py <chapter_id>")
        sys.exit(1)
    main(sys.argv[1])
