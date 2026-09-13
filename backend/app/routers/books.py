import random
import uuid
from pathlib import Path

import pymupdf
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models as m
from app.database import get_db
from app.paths import UPLOADS_DIR
from app.pipeline.pipeline import process_book
from app.pipeline.titles import clean_title_basic
from app.progress import (
    book_last_opened_at,
    book_progress_percent,
    lesson_status,
    serialize_question_redacted,
)
from app.quizzes import list_manual_quizzes, quiz_summary
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
        "final_quiz": quiz_summary(db, book.final_quiz_id),
        "manual_quizzes": list_manual_quizzes(db, book),
        "chapters": [
            {
                "id": chapter.id,
                "number": chapter.number,
                "title": chapter.title,
                "summary": chapter.summary,
                "quiz": quiz_summary(db, chapter.quiz_id),
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
                                    {"question": serialize_question_redacted(block.question)}
                                    if block.kind == "question"
                                    # prose, definition, example — all carry markdown content
                                    else {"content": block.content}
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


@router.post("/upload")
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Save the PDF, extract its text with pymupdf, and create a Book row in
    `processing` status. Returns immediately — extraction is fast (no AI call),
    but the rest of the pipeline (chapter detection, lesson splitting, block
    generation) calls Gemini repeatedly, so it runs as one background task
    kicked off after the response is sent; poll GET /{id}/status to watch it.
    """
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    book_id = str(uuid.uuid4())
    pdf_path = UPLOADS_DIR / f"{book_id}.pdf"
    pdf_path.write_bytes(await file.read())

    try:
        doc = pymupdf.open(pdf_path)
        try:
            text = "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()
    except Exception as e:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {e}")

    # Raw extracted text is pipeline-internal, not part of the documented schema
    # (docs/SCHEMA.md), so it lives as a sidecar file next to the PDF rather than
    # a DB column. Later pipeline steps read it back from here.
    (UPLOADS_DIR / f"{book_id}.txt").write_text(text, encoding="utf-8")

    book = m.Book(
        id=book_id,
        title=clean_title_basic(Path(filename).stem),
        author=None,
        source_filename=filename,
        cover_seed=random.randint(1, 999_999),
        status="processing",
        processing_stage="Extracted text, waiting for chapter detection",
    )
    db.add(book)
    db.commit()

    background_tasks.add_task(process_book, book.id)

    return {"book_id": book.id, "status": book.status}


@router.get("/{book_id}/status")
def get_book_status(book_id: str, db: Session = Depends(get_db)):
    """Poll during processing. chapters_done is a live count of Chapter rows,
    so the frontend can show chapters landing one by one as chapter detection
    stores each of them. chapters_total has no backing field (docs/SCHEMA.md
    has none for it) and stays null — processing_stage carries the same
    information as human-readable text (e.g. "Found chapter 3 of 8: ...")."""
    book = db.get(m.Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    return {
        "status": book.status,
        "stage": book.processing_stage,
        "chapters_done": db.query(m.Chapter).filter_by(book_id=book.id).count(),
        "chapters_total": None,
    }
