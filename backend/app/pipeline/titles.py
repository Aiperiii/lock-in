"""Book title cleanup. Uploaded PDFs are often named after however the source
scraped/exported them — "[Book] Discrete mathematics and its applications
(2019)_0.pdf" rather than a real title — so the filename-derived title gets
cleaned up in two stages:

1. Cheap, always-applied regex cleanup (clean_title_basic): strips a leading
   "[Book]" tag, a parenthesized publication year, a trailing "_0" part
   marker, and turns underscores into spaces. Runs synchronously in the
   upload endpoint — it's free, so there's no reason to defer it.

2. If the cleaned title still looks unreliable (looks_messy), the background
   pipeline asks Gemini to read the real title and author off the book's own
   opening text (refine_if_messy). This is a nice-to-have, not a core pipeline
   stage: unlike chapter detection, a failure here is swallowed rather than
   marking the book `failed` — a slightly-off title is a much smaller problem
   than a broken course, and the cleaned filename is still a usable fallback.
"""

import logging
import re

from sqlalchemy.orm import Session

from app import models as m
from app.ai.client import MODEL_FAST, generate_json
from app.paths import UPLOADS_DIR

logger = logging.getLogger(__name__)

AI_EXCERPT_CHARS = 8_000

_BOOK_TAG_RE = re.compile(r"^\s*\[book\]\s*", re.IGNORECASE)
_YEAR_PAREN_RE = re.compile(r"\s*\(\s*(?:19|20)\d{2}\s*\)")
_TRAILING_PART_RE = re.compile(r"[\s_-]*_0\s*$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

_MESSY_RE = re.compile(r"[_\[\]{}]|(?<!\d)\d{3,}(?!\d)")


def clean_title_basic(raw: str) -> str:
    """Cheap, always-applied filename cleanup — no AI call."""
    title = _BOOK_TAG_RE.sub("", raw)
    title = _YEAR_PAREN_RE.sub("", title)
    title = _TRAILING_PART_RE.sub("", title)
    title = title.replace("_", " ")
    title = _WHITESPACE_RE.sub(" ", title).strip()
    return title or raw.strip()  # never hand back an empty title


def looks_messy(title: str) -> bool:
    """True if `title` still looks like a raw filename rather than a real
    title: leftover bracket/underscore artifacts, a stray numeric run (an
    ISBN or id fragment), too short to be a real title, every letter
    lowercase (a hyphenated slug with no spaces to split on), or — the common
    case that those checks alone miss — more than half its words starting
    lowercase. A filename that was already spaced into words ("Discrete
    mathematics and its applications") reads as plausible at a glance, but is
    sentence-cased rather than the book's real title case."""
    if not title or len(title.strip()) < 3:
        return True
    if _MESSY_RE.search(title):
        return True

    letters = [c for c in title if c.isalpha()]
    if letters and all(c.islower() for c in letters):
        return True  # e.g. a hyphenated slug with no spaces to split on

    words = [w for w in title.split() if w[:1].isalpha()]
    if not words:
        return True
    lowercase_first = sum(1 for w in words if w[0].islower())
    return len(words) > 1 and lowercase_first / len(words) > 0.5


def refine_if_messy(db: Session, book: m.Book) -> None:
    """Background-pipeline step: if `book.title` still looks messy after the
    basic cleanup, ask Gemini to read the real title/author off the book's
    own opening text. Never raises — any failure here just leaves the
    cleaned-filename title in place."""
    if not looks_messy(book.title):
        return

    text_path = UPLOADS_DIR / f"{book.id}.txt"
    if not text_path.exists():
        return

    excerpt = text_path.read_text(encoding="utf-8")[:AI_EXCERPT_CHARS]
    result = _extract_title_author(excerpt)
    if result is None:
        return

    title, author = result
    book.title = title
    if author:
        book.author = author
    db.commit()


def _extract_title_author(text_excerpt: str) -> tuple[str, str | None] | None:
    prompt = f"""You are looking at the first page(s) of a textbook's extracted text. The
book's filename produced a messy or unreliable title, so read the real title
and author off the text itself.

Return ONLY JSON: {{"title": "...", "author": "..." or null}}

Rules:
- title is the book's actual title as it appears on the title page, in
  standard title case, without added subtitle clutter unless it's clearly
  part of the real title.
- author is the author or author list as it would normally be cited (e.g.
  "Cormen, Leiserson, Rivest & Stein"), or null if the text doesn't make it
  determinable.
- If you cannot confidently determine the title, give your best guess rather
  than refusing — the fallback is a raw filename, so any reasonable guess is
  an improvement.

TEXT:
{text_excerpt}"""

    try:
        raw = generate_json(prompt, model=MODEL_FAST)
    except Exception:
        logger.warning("title extraction: generate_json raised", exc_info=True)
        return None

    if not isinstance(raw, dict):
        return None
    title = (raw.get("title") or "").strip()
    if not title:
        return None
    author = (raw.get("author") or "").strip() or None
    return title, author
