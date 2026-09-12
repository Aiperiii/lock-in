from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models as m
from app.database import get_db
from app.progress import lesson_status, serialize_question_for_lesson

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("/{lesson_id}")
def get_lesson(lesson_id: str, db: Session = Depends(get_db)):
    """Lesson with its ordered blocks, questions inlined, plus the user's prior
    attempts so the UI can render already-answered questions in their answered
    state. correct_index/explanation/model_answer are included only for
    questions that already have an attempt."""
    lesson = db.get(m.Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    chapter = lesson.chapter
    book = chapter.book

    blocks = []
    for block in lesson.blocks:
        entry = {"id": block.id, "order": block.order, "kind": block.kind}
        if block.kind == "prose":
            entry["content"] = block.content
        else:
            entry["question"] = serialize_question_for_lesson(db, block.question)
        blocks.append(entry)

    return {
        "id": lesson.id,
        "title": lesson.title,
        "book_id": book.id,
        "book_title": book.title,
        "chapter_number": chapter.number,
        "estimated_minutes": lesson.estimated_minutes,
        "status": lesson_status(db, lesson.id),
        "blocks": blocks,
    }
