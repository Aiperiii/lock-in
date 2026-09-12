"""One-off migration: add chapters.quiz_id and books.final_quiz_id.

Unlike the lesson_id nullability change, these are plain nullable columns
being added to existing tables — SQLite supports ALTER TABLE ADD COLUMN
directly for that, no table rebuild needed. Idempotent: checks each column's
presence first.

Run with the backend's venv active:

    python scripts/migrate_add_quiz_ready_columns.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import DB_PATH  # noqa: E402


def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        if not has_column(conn, "chapters", "quiz_id"):
            conn.execute("ALTER TABLE chapters ADD COLUMN quiz_id VARCHAR REFERENCES quizzes(id)")
            print("added chapters.quiz_id")
        else:
            print("chapters.quiz_id already exists")

        if not has_column(conn, "books", "final_quiz_id"):
            conn.execute("ALTER TABLE books ADD COLUMN final_quiz_id VARCHAR REFERENCES quizzes(id)")
            print("added books.final_quiz_id")
        else:
            print("books.final_quiz_id already exists")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
