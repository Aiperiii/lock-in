"""Chapter detection: the first AI-driven stage of the PDF -> course pipeline.

Uses the prompt in docs/PROMPTS.md section 1 to ask Gemini for chapter
boundaries as {number, title, start_marker} triples, then locates each
start_marker in the book's actual extracted text to get real character
offsets, and slices the text into chapters from those offsets.

Nothing here is book-specific. Two things make textbooks awkward to split on
their own say-so, and both are handled generically:

1. The model's start_marker can come back not-quite-verbatim (PDF extraction
   introduces drop-cap word splits, hyphenation, odd whitespace), so locating
   it uses three progressively fuzzier strategies (see _find_occurrences).
2. A chapter's title/opening text often also appears in the table of contents
   and in running headers throughout the chapter body, so the same marker can
   match many places. The earliest match that is followed by real prose
   (rather than more dot-leaders, page numbers, and short heading-like lines)
   is taken as the true chapter start (see _prose_score).

If Gemini's output is unusable (empty, unparseable, no locatable markers),
this falls back to a single chapter spanning the whole book, named after it.
If Gemini itself is unavailable (both model tiers rate-limited), the book is
marked `failed` with a readable processing_stage instead — that's an
infrastructure problem, not a content one, and pretending otherwise would
misrepresent a real book as having no chapter structure.

Chapter detection runs once per book, so it uses MODEL_QUALITY (better at
telling real chapters from numbered subsections) rather than the default
high-volume tier — see app/ai/client.py.
"""

import difflib
import logging
import re
import time

from sqlalchemy.orm import Session

from app import models as m
from app.ai.client import MODEL_QUALITY, GeminiUnavailable, generate_json
from app.ai.prompts import chapter_detection_prompt
from app.database import SessionLocal
from app.paths import UPLOADS_DIR

logger = logging.getLogger(__name__)

# A single bounded window can only ever report chapters visible within it —
# for a real textbook a chapter alone can run past 200k characters, so one
# call cannot see the whole book. Detection instead makes repeated calls with
# the same section-1 prompt on successive windows, advancing past each newly
# found chapter, until the whole book is covered or nothing new turns up.
# Gemini's rate limit is per request, not per token (see CLAUDE.md), so a
# large window costs nothing there — it just means fewer calls are needed.
WINDOW_CHARS = 200_000
MAX_WINDOWS = 40
CALL_DELAY_SECONDS = 2

TOC_SEARCH_CHARS = 150_000
TOC_EXCERPT_CHARS = 4_000
PROSE_WINDOW_CHARS = 600
PROSE_THRESHOLD = 0.0
FUZZY_STRIDE = 15
FUZZY_THRESHOLD = 0.6
FUZZY_MARGIN = 10  # extra slack past marker length, to absorb a stray inserted
# character (e.g. a drop-cap line break) without the match window growing so
# generous it plateaus across many nearby offsets — see _fuzzy_find.

_TOC_PHRASE_RE = re.compile(r"table of contents", re.IGNORECASE)
_TOC_HEADING_LINE_RE = re.compile(r"^[ \t]*contents[ \t]*$", re.IGNORECASE | re.MULTILINE)
_DOT_LEADER_RE = re.compile(r"(?:\.[ \t]?){5,}")  # ". . . . ." style leaders, spaced or not
_WORD_RE = re.compile(r"[A-Za-z]{3,}")

# 1:1 character substitutions only, so offsets never shift.
_CHAR_FOLD = str.maketrans(
    {
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", " ": " ",
    }
)


def detect_chapters_for_book(book_id: str) -> None:
    """Background-task entry point. Opens its own DB session rather than
    reusing the upload request's — that session is already closed by the time
    a FastAPI BackgroundTask actually runs.

    Never lets an exception escape: this runs unattended in the background, so
    any failure (Gemini unavailable, a corrupt sidecar file, whatever) is
    caught here and turned into book.status = "failed" with a readable
    processing_stage, rather than leaving the book stuck at "processing"
    forever or crashing the background task silently.
    """
    db = SessionLocal()
    try:
        book = db.get(m.Book, book_id)
        if book is None:
            return
        try:
            _run(db, book)
        except Exception as exc:
            db.rollback()
            book = db.get(m.Book, book_id)
            book.status = "failed"
            book.processing_stage = f"Chapter detection failed: {exc}"
            db.commit()
    finally:
        db.close()


def _run(db: Session, book: m.Book) -> None:
    full_text = (UPLOADS_DIR / f"{book.id}.txt").read_text(encoding="utf-8")

    book.processing_stage = "Detecting chapters"
    db.commit()

    chapters = _detect_chapter_boundaries(full_text, fallback_title=book.title)

    total = len(chapters)
    for i, chapter in enumerate(chapters, start=1):
        row = m.Chapter(
            book_id=book.id,
            number=chapter["number"],
            title=chapter["title"],
            summary=None,
        )
        db.add(row)
        db.flush()  # populates row.id
        (UPLOADS_DIR / f"{row.id}.txt").write_text(chapter["text"], encoding="utf-8")
        book.processing_stage = f"Found chapter {i} of {total}: {chapter['title']}"
        db.commit()

    plural = "s" if total != 1 else ""
    book.processing_stage = f"Detected {total} chapter{plural}, waiting for lesson splitting"
    db.commit()


def _detect_chapter_boundaries(full_text: str, fallback_title: str) -> list[dict]:
    """Returns [{"number", "title", "text"}, ...] in body order. Never raises
    or returns an empty list — falls back to one chapter spanning the book."""
    placed: list[dict] = []
    seen_numbers: set = set()
    search_floor = 0  # every located chapter start must be at/after this
    cursor = 0  # where the next call's window starts reading from

    for i in range(MAX_WINDOWS):
        if cursor >= len(full_text):
            break

        window_start = cursor
        window = _first_window(full_text) if i == 0 else full_text[window_start : window_start + WINDOW_CHARS]
        entries = _ask_gemini(window)
        new_entries = [
            e
            for e in entries
            if e.get("number") not in seen_numbers and (e.get("start_marker") or "").strip()
        ]

        for entry in new_entries:
            raw_number = entry.get("number")
            if raw_number in seen_numbers:
                continue  # guards against a duplicate number within one response
            marker = entry["start_marker"].strip()
            offset = _pick_body_offset(marker, full_text, search_floor)
            if offset is None:
                continue
            title = (entry.get("title") or "").strip() or f"Chapter {len(placed) + 1}"
            number = raw_number if isinstance(raw_number, int) else len(placed) + 1
            seen_numbers.add(raw_number)
            placed.append({"number": number, "title": title, "start_offset": offset})
            search_floor = offset + len(marker)

        # Always the next window's worth, from where THIS window started — not
        # from the last found offset. Jumping ahead to a found offset (rather
        # than just past this window) would skip whatever fell in between
        # without ever showing it to the model, silently dropping any chapter
        # that happens to sit in that gap.
        cursor = window_start + WINDOW_CHARS
        if i > 0 and not entries:
            # A window with nothing at all (not even an unusable/duplicate
            # entry) suggests we've run past the last real chapter.
            break
        time.sleep(CALL_DELAY_SECONDS)

    if not placed:
        return [{"number": 1, "title": fallback_title, "text": full_text}]

    placed.sort(key=lambda c: c["start_offset"])
    return [
        {
            "number": chapter["number"],
            "title": chapter["title"],
            "text": full_text[
                chapter["start_offset"] : (
                    placed[i + 1]["start_offset"] if i + 1 < len(placed) else len(full_text)
                )
            ],
        }
        for i, chapter in enumerate(placed)
    ]


def _ask_gemini(window: str) -> list[dict]:
    """Calls Gemini on one window and coerces its reply into a list of entry
    dicts. Returns [] on a content-level failure (bad/empty JSON) — the
    caller's single-chapter fallback takes over from there. GeminiUnavailable
    (both model tiers rate-limited) is re-raised rather than swallowed: that's
    an infrastructure failure the caller needs to know about, not something a
    fallback chapter should paper over."""
    try:
        raw = generate_json(chapter_detection_prompt(window), model=MODEL_QUALITY)
    except GeminiUnavailable:
        raise
    except Exception:
        logger.warning("chapter detection: generate_json raised", exc_info=True)
        return []
    entries = _coerce_entries(raw)
    if not entries:
        # generate_json already logs the raw response text; this makes clear
        # *why* nothing came of it — an empty/malformed JSON shape rather than
        # a swallowed exception.
        logger.warning("chapter detection: parsed JSON had no usable chapter entries: %r", raw)
    return entries


def _coerce_entries(raw) -> list[dict]:
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, list):
                return [e for e in value if isinstance(e, dict)]
    return []


def _first_window(full_text: str) -> str:
    """docs/PROMPTS.md says "first ~15k chars... plus any TOC-looking region",
    but the window here is much larger than 15k: many textbooks pad their
    table of contents with dot-leader lines (". . . . . 47") dense enough to
    burn through 15k characters before any real chapter body text is visible
    at all — leaving the model nothing to build a genuine start_marker from.
    The TOC-heading search below is a best-effort supplement for the rarer
    case where front matter is so long even this window doesn't reach it.
    """
    base = full_text[:WINDOW_CHARS]

    search_zone = full_text[:TOC_SEARCH_CHARS]
    match = _TOC_PHRASE_RE.search(search_zone) or _TOC_HEADING_LINE_RE.search(search_zone)
    if match is None or match.start() < WINDOW_CHARS:
        return base

    toc_excerpt = full_text[match.start() : match.start() + TOC_EXCERPT_CHARS]
    return (
        f"{base}\n\n"
        "[Excerpt found later in the document, likely the table of contents]\n"
        f"{toc_excerpt}"
    )


def _pick_body_offset(marker: str, full_text: str, search_start: int) -> int | None:
    """Among all occurrences of `marker` at or after search_start, return the
    earliest one followed by real prose rather than more TOC/heading matter.
    Falls back to the first occurrence at all if none clearly look like prose
    (better to place the chapter a little off than to drop it)."""
    offsets = _find_occurrences(marker, full_text, search_start)
    if not offsets:
        return None
    for offset in offsets:
        window = full_text[offset + len(marker) : offset + len(marker) + PROSE_WINDOW_CHARS]
        if _prose_score(window) >= PROSE_THRESHOLD:
            return offset
    return offsets[0]


def _prose_score(window: str) -> float:
    """Higher = more likely this is body prose; lower/negative = more likely a
    table-of-contents listing (dot leaders, page numbers, many short lines)."""
    if not window.strip():
        return -999.0
    words = _WORD_RE.findall(window)
    digit_chars = sum(ch.isdigit() for ch in window)
    dot_leaders = len(_DOT_LEADER_RE.findall(window))
    lines = [line for line in window.splitlines() if line.strip()]
    avg_line_len = sum(len(line) for line in lines) / len(lines) if lines else 0
    short_lines = sum(1 for line in lines if len(line.strip()) < 60)
    return (
        len(words)
        + avg_line_len * 0.3
        - digit_chars * 0.4
        - dot_leaders * 15
        - short_lines * 2
    )


def _find_occurrences(marker: str, haystack: str, start: int) -> list[int]:
    """All offsets (ascending, >= start) where `marker` approximately occurs,
    trying progressively fuzzier strategies until one finds something."""
    region = haystack[start:]

    pattern = _tolerant_pattern(marker)
    hits = [start + mo.start() for mo in pattern.finditer(region)]
    if hits:
        return hits

    folded_pattern = _tolerant_pattern(marker.translate(_CHAR_FOLD))
    hits = [start + mo.start() for mo in folded_pattern.finditer(region.translate(_CHAR_FOLD))]
    if hits:
        return hits

    fuzzy = _fuzzy_find(marker.translate(_CHAR_FOLD), region.translate(_CHAR_FOLD))
    return [start + fuzzy] if fuzzy is not None else []


def _tolerant_pattern(marker: str) -> re.Pattern:
    """A regex matching `marker`'s words in order with flexible whitespace
    between them — tolerates line-wrap differences without any fuzziness."""
    words = marker.split()
    return re.compile(r"\s+".join(re.escape(word) for word in words))


def _fuzzy_find(marker: str, region: str) -> int | None:
    """Last-resort approximate search: a strided coarse scan (cheap) followed
    by a local refinement around the best candidate. Bounded cost even across
    a multi-million-character book, since the stride keeps the coarse pass
    linear in the region size regardless of marker length.

    Ties prefer the LATEST candidate position, not the first: a match window
    generous enough to contain the whole marker scores identically for every
    position that still fully contains it, and the least-slack (latest) one
    is the one actually aligned with the marker's start rather than including
    a few extra characters of whatever precedes it.
    """
    n = len(marker)
    if n == 0 or len(region) < n:
        return None

    matcher = difflib.SequenceMatcher(None)
    matcher.set_seq2(marker)

    best_pos, best_ratio = None, -1.0
    for pos in range(0, len(region) - n + 1, FUZZY_STRIDE):
        matcher.set_seq1(region[pos : pos + n + FUZZY_MARGIN])
        ratio = matcher.quick_ratio()
        if ratio >= best_ratio:
            best_pos, best_ratio = pos, ratio
    if best_pos is None:
        return None

    refine_lo = max(0, best_pos - FUZZY_STRIDE)
    refine_hi = min(len(region) - n, best_pos + FUZZY_STRIDE)
    best_local_pos, best_local_ratio = best_pos, -1.0
    for pos in range(refine_lo, refine_hi + 1):
        ratio = difflib.SequenceMatcher(None, region[pos : pos + n + FUZZY_MARGIN], marker).ratio()
        if ratio >= best_local_ratio:
            best_local_pos, best_local_ratio = pos, ratio

    return best_local_pos if best_local_ratio >= FUZZY_THRESHOLD else None
