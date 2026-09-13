"""Debug/tuning helper: delete a lesson's existing Block and Question rows
and regenerate them from scratch via app.pipeline.blocks.run_for_lesson —
the exact function the upload pipeline calls, so this exercises prompt
changes (docs/PROMPTS.md, app/ai/prompts.py) against real lesson text
without re-uploading a book.

Refuses to touch a lesson whose questions are already referenced by any
QuizQuestion, or that has real QuestionAttempt history — regenerating would
silently orphan a quiz row or erase a student's progress. Pick an untouched
lesson instead.

Usage:
    python scripts/regenerate_lesson_blocks.py <lesson_id>

Find a lesson id with:
    sqlite3 backend/lockedin.db "SELECT id, title FROM lessons;"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models as m  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.pipeline.blocks import run_for_lesson  # noqa: E402


def main(lesson_id: str) -> None:
    db = SessionLocal()
    try:
        lesson = db.get(m.Lesson, lesson_id)
        if lesson is None:
            print(f"no lesson with id {lesson_id}")
            return

        question_ids = [q.id for q in lesson.questions]
        in_quiz = (
            db.query(m.QuizQuestion).filter(m.QuizQuestion.question_id.in_(question_ids)).count()
            if question_ids
            else 0
        )
        if in_quiz:
            print(f"refusing: {in_quiz} of this lesson's questions are used in a quiz")
            return
        attempts = (
            db.query(m.QuestionAttempt).filter(m.QuestionAttempt.question_id.in_(question_ids)).count()
            if question_ids
            else 0
        )
        if attempts:
            print(f"refusing: this lesson has {attempts} real QuestionAttempt row(s)")
            return

        for block in list(lesson.blocks):
            db.delete(block)
        for question in list(lesson.questions):
            db.delete(question)
        db.commit()

        run_for_lesson(db, lesson)

        lesson = db.get(m.Lesson, lesson_id)
        print(f"regenerated {len(lesson.blocks)} block(s) for {lesson.title!r}\n")
        for block in sorted(lesson.blocks, key=lambda b: b.order):
            if block.kind in ("prose", "definition", "example"):
                print(f"[{block.kind}] {block.content}\n")
            else:
                q = block.question
                print(f"[{q.type}] ({q.source}) {q.prompt}")
                if q.options:
                    for i, opt in enumerate(q.options):
                        marker = "*" if i == q.correct_index else " "
                        print(f"  {marker} {opt}")
                if q.hint:
                    print(f"  hint: {q.hint}")
                print(f"  explanation: {q.explanation}\n")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/regenerate_lesson_blocks.py <lesson_id>")
        sys.exit(1)
    main(sys.argv[1])
