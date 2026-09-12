from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models as m
from app.config import GREETING_NAME, SUBJECT_TAGS, USER_ID
from app.database import get_db
from app.progress import book_last_opened_at, book_progress_percent
from app.utils import utcnow_naive

router = APIRouter(prefix="/api/home", tags=["home"])


@router.get("")
def get_home(db: Session = Depends(get_db)):
    streak = db.get(m.Streak, USER_ID)
    streak_days = streak.current_days if streak else 0

    review_due_count = (
        db.query(m.ReviewItem)
        .filter(m.ReviewItem.user_id == USER_ID, m.ReviewItem.due_at <= utcnow_naive())
        .count()
    )

    # "Continue" is whichever book was most recently opened (no dedicated
    # "opened" event exists, so this reuses the same last-opened derivation as
    # the library view).
    continue_book = None
    best_opened_at = None
    for book in db.query(m.Book).all():
        opened_at = book_last_opened_at(db, book)
        if opened_at and (best_opened_at is None or opened_at > best_opened_at):
            best_opened_at = opened_at
            continue_book = book

    continue_payload = None
    if continue_book:
        continue_payload = {
            "book_id": continue_book.id,
            "title": continue_book.title,
            "author": continue_book.author,
            "cover_seed": continue_book.cover_seed,
            "progress_percent": book_progress_percent(db, continue_book),
        }

    return {
        "greeting_name": GREETING_NAME,
        "subject_tags": SUBJECT_TAGS,
        "streak_days": streak_days,
        "review_due_count": review_due_count,
        "continue": continue_payload,
    }
