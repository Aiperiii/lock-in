"""One-off migration: relax questions.lesson_id to nullable.

Needed for quiz generation (see app/quizzes.py) — a freshly generated
top-up question doesn't belong to any lesson. SQLite enforces NOT NULL at
the table level regardless of what models.py says, and SQLite has no
ALTER COLUMN, so the table has to be rebuilt: rename it, create a fresh
`questions` table from the current (already-updated) SQLAlchemy model, copy
every row across, drop the renamed one.

Idempotent — checks the column's current nullability first and does nothing
if it's already nullable. Run with the backend's venv active:

    python scripts/migrate_questions_lesson_id_nullable.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models as m  # noqa: E402
from app.database import DB_PATH, engine  # noqa: E402

COLUMNS = [
    "id",
    "lesson_id",
    "type",
    "prompt",
    "options",
    "correct_index",
    "hint",
    "explanation",
    "model_answer",
    "concept_tag",
    "difficulty",
    "source",
    "parent_question_id",
]


def already_nullable(conn: sqlite3.Connection) -> bool:
    row = next(r for r in conn.execute("PRAGMA table_info(questions)") if r[1] == "lesson_id")
    notnull = row[3]
    return notnull == 0


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        if already_nullable(conn):
            print("questions.lesson_id is already nullable — nothing to do.")
            return

        before = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        print(f"migrating questions table ({before} rows)...")

        conn.execute("ALTER TABLE questions RENAME TO questions_pre_migration")
        conn.commit()

        # Build the new table from the current model (already declares
        # lesson_id nullable) so the schema stays in sync with models.py.
        m.Question.__table__.create(engine)

        cols = ", ".join(COLUMNS)
        conn.execute(f"INSERT INTO questions ({cols}) SELECT {cols} FROM questions_pre_migration")
        conn.commit()

        after = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if after != before:
            raise RuntimeError(f"row count mismatch after copy: before={before} after={after}")

        conn.execute("DROP TABLE questions_pre_migration")
        conn.commit()
        print(f"done — {after} rows preserved, lesson_id is now nullable.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
