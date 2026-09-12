from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models as m
from app.database import get_db
from app.progress import (
    book_last_opened_at,
    book_progress_percent,
    lesson_status,
    serialize_question_redacted,
)
from app.utils import iso8601

router = APIRouter(prefix="/api/books", tags=["books"])


@router.get("")
def list_books(db: Session = Depends(get_db)):
    """Library view. progress_percent is computed from lesson mastery, never
    stored. Sorted by most-recently-opened first; never-opened books last."""
    books = db.query(m.Book).all()
    results = [
        {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "cover_seed": book.cover_seed,
            "status": book.status,
            "progress_percent": book_progress_percent(db, book),
            "last_opened_at": iso8601(book_last_opened_at(db, book)),
        }
        for book in books
    ]
    results.sort(key=lambda b: b["last_opened_at"] or "", reverse=True)
    return results


@router.get("/{book_id}")
def get_book(book_id: str, db: Session = Depends(get_db)):
    """Full nested course — see mock/course.json for the base shape. Each
    lesson's status and the book's progress_percent are computed live from
    LessonProgress. Questions never reveal correct_index/explanation/
    model_answer here — this is a static course view, not an answer flow."""
    book = db.get(m.Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "cover_seed": book.cover_seed,
        "status": book.status,
        "progress_percent": book_progress_percent(db, book),
        "chapters": [
            {
                "id": chapter.id,
                "number": chapter.number,
                "title": chapter.title,
                "summary": chapter.summary,
                "lessons": [
                    {
                        "id": lesson.id,
                        "number": lesson.number,
                        "title": lesson.title,
                        "estimated_minutes": lesson.estimated_minutes,
                        "kind": lesson.kind,
                        "concept_tags": lesson.concept_tags,
                        "status": lesson_status(db, lesson.id),
                        "blocks": [
                            {
                                "id": block.id,
                                "order": block.order,
                                "kind": block.kind,
                                **(
                                    {"content": block.content}
                                    if block.kind == "prose"
                                    else {"question": serialize_question_redacted(block.question)}
                                ),
                            }
                            for block in lesson.blocks
                        ],
                    }
                    for lesson in chapter.lessons
                ],
            }
            for chapter in book.chapters
        ],
    }
