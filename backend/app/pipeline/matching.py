"""Shared fuzzy text-location logic: given a short marker string a model
claims is copied verbatim from a larger text, find where it actually is.

Three progressively fuzzier strategies, each only tried if the previous one
finds nothing:
1. Exact match, tolerant of whitespace differences (line-wrap variation).
2. Same, after folding smart quotes/dashes to ASCII (1:1 substitutions, so
   offsets never shift).
3. Approximate match via difflib, for anything else — hyphenation, drop-cap
   artifacts, minor typos. Bounded cost even across a multi-million-character
   book: a strided coarse scan followed by a small local refinement.

Used by both chapter detection and lesson splitting.
"""

import difflib
import re

FUZZY_STRIDE = 15
FUZZY_THRESHOLD = 0.6
FUZZY_MARGIN = 10  # extra slack past marker length, to absorb a stray inserted
# character (e.g. a drop-cap line break) without the match window growing so
# generous it plateaus across many nearby offsets — see fuzzy_find.

# 1:1 character substitutions only, so offsets never shift.
CHAR_FOLD = str.maketrans(
    {
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", " ": " ",
    }
)


def find_occurrences(marker: str, haystack: str, start: int = 0) -> list[int]:
    """All offsets (ascending, >= start) where `marker` approximately occurs,
    trying progressively fuzzier strategies until one finds something."""
    region = haystack[start:]

    pattern = tolerant_pattern(marker)
    hits = [start + mo.start() for mo in pattern.finditer(region)]
    if hits:
        return hits

    folded_pattern = tolerant_pattern(marker.translate(CHAR_FOLD))
    hits = [start + mo.start() for mo in folded_pattern.finditer(region.translate(CHAR_FOLD))]
    if hits:
        return hits

    fuzzy = fuzzy_find(marker.translate(CHAR_FOLD), region.translate(CHAR_FOLD))
    return [start + fuzzy] if fuzzy is not None else []


def tolerant_pattern(marker: str) -> re.Pattern:
    """A regex matching `marker`'s words in order with flexible whitespace
    between them — tolerates line-wrap differences without any fuzziness."""
    words = marker.split()
    return re.compile(r"\s+".join(re.escape(word) for word in words))


def fuzzy_find(marker: str, region: str) -> int | None:
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
