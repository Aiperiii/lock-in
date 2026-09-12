"""Open-response grading, docs/PROMPTS.md section 4.

Called once per open-response submission — high volume, so this uses
MODEL_FAST, the same tier as lesson splitting and block generation (chapter
detection is the only thing that gets the once-per-book quality tier).
"""

import logging

from app.ai.client import MODEL_FAST, generate_json
from app.ai.prompts import grading_prompt

logger = logging.getLogger(__name__)

# If grading genuinely fails (Gemini unavailable, or an unusable response even
# after generate_json's own retry), the answer is accepted rather than
# blocking the student on an infrastructure problem — in keeping with the
# grading prompt's own generous-by-design philosophy.
FALLBACK_FEEDBACK = "Thanks for your answer — grading hit a snag, so this one's marked correct for now."


def _lesson_excerpt(question) -> str:
    """The lesson's own prose, concatenated in order, as grounding for the
    grader. Reconstructed from Block rows rather than the pipeline's sidecar
    text files: those don't exist for lessons that were never AI-generated
    (e.g. the seeded demo book), while Block rows always do."""
    blocks = sorted(question.lesson.blocks, key=lambda b: b.order)
    prose = [b.content for b in blocks if b.kind == "prose" and b.content]
    return "\n\n".join(prose)


def grade_open_response(question, answer: str) -> tuple[bool, str]:
    """Returns (is_correct, feedback). Never raises."""
    prompt = grading_prompt(
        question_prompt=question.prompt,
        model_answer=question.model_answer or "",
        lesson_excerpt=_lesson_excerpt(question),
        answer=answer,
    )
    try:
        raw = generate_json(prompt, model=MODEL_FAST)
    except Exception:
        logger.warning("open-response grading: generate_json raised", exc_info=True)
        return True, FALLBACK_FEEDBACK

    if not isinstance(raw, dict) or "is_correct" not in raw or "feedback" not in raw:
        logger.warning("open-response grading: unusable response: %r", raw)
        return True, FALLBACK_FEEDBACK

    return bool(raw["is_correct"]), str(raw["feedback"])
