"""Shared validation for a Gemini-produced question dict, before it becomes a
Question row.

Used by block generation (one call per lesson, docs/PROMPTS.md section 3) and
quiz generation's top-up step (app/quizzes.py) — both call Gemini for a
question in the exact same JSON shape, so the validation rules live in one
place instead of drifting between two copies.
"""

VALID_QUESTION_TYPES = ("mcq", "open", "matching")
VALID_DIFFICULTIES = ("easy", "medium", "hard")
VALID_SOURCES = ("book", "ai", "hybrid")
MIN_MATCHING_PAIRS = 4
MAX_MATCHING_PAIRS = 6


def validate_question(q) -> dict | None:
    """Every field the Question model requires NOT NULL is checked here —
    returns None (the caller drops it) rather than let a DB IntegrityError
    abort a whole lesson or quiz over one malformed question."""
    if not isinstance(q, dict):
        return None

    q_type = q.get("type")
    prompt = (q.get("prompt") or "").strip()
    explanation = (q.get("explanation") or "").strip()
    concept_tag = (q.get("concept_tag") or "").strip()
    if q_type not in VALID_QUESTION_TYPES or not (prompt and explanation and concept_tag):
        return None

    difficulty = q.get("difficulty") if q.get("difficulty") in VALID_DIFFICULTIES else "medium"
    source = q.get("source") if q.get("source") in VALID_SOURCES else "ai"

    if q_type == "mcq":
        options = q.get("options")
        correct_index = q.get("correct_index")
        if not (
            isinstance(options, list)
            and len(options) >= 2
            and isinstance(correct_index, int)
            and 0 <= correct_index < len(options)
        ):
            return None
        hint, model_answer = None, None
    elif q_type == "matching":
        # docs/PROMPTS.md section 8 — stored in Question.options as
        # [{"left": ..., "right": ...}, ...], same field MCQ uses for its
        # option list. Index in this list IS the pairing: the client is
        # never shown it in this order (app/progress.py shuffles the right
        # side before serving), so there's no separate "correct answer"
        # field to validate here.
        pairs = q.get("pairs")
        if not (isinstance(pairs, list) and MIN_MATCHING_PAIRS <= len(pairs) <= MAX_MATCHING_PAIRS):
            return None
        options = []
        for pair in pairs:
            if not isinstance(pair, dict):
                return None
            left = (pair.get("left") or "").strip()
            right = (pair.get("right") or "").strip()
            if not left or not right:
                return None
            options.append({"left": left, "right": right})
        correct_index, hint, model_answer = None, None, None
    else:  # open
        model_answer = (q.get("model_answer") or "").strip()
        if not model_answer:
            return None
        options, correct_index = None, None
        hint = q.get("hint")

    return {
        "type": q_type,
        "prompt": prompt,
        "options": options,
        "correct_index": correct_index,
        "hint": hint,
        "explanation": explanation,
        "model_answer": model_answer,
        "concept_tag": concept_tag,
        "difficulty": difficulty,
        "source": source,
    }
