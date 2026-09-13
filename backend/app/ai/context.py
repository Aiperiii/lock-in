"""Shared grounding text for AI calls that need a lesson's own content —
open-response grading (app/grading.py) and the select-text AI panel
(app/routers/ai.py). Reconstructed from Block rows rather than the
pipeline's sidecar text files: those don't exist for a lesson that was never
AI-generated (e.g. the seeded demo book), while Block rows always do.
"""

from app import models as m


PROSE_LIKE_KINDS = ("prose", "definition", "example")


def lesson_prose_excerpt(lesson: "m.Lesson | None") -> str:
    if lesson is None:
        return ""
    blocks = sorted(lesson.blocks, key=lambda b: b.order)
    prose = [b.content for b in blocks if b.kind in PROSE_LIKE_KINDS and b.content]
    return "\n\n".join(prose)
