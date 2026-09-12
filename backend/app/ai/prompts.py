"""Prompt templates from docs/PROMPTS.md. Kept separate from client.py so each
pipeline stage owns its own template as more get added (lesson splitting, block
generation, grading, ...).
"""


def chapter_detection_prompt(text: str) -> str:
    """docs/PROMPTS.md section 1. `text` is the model's input: the first ~15k
    characters of extracted text, plus any TOC-looking region found further in
    (see app/pipeline/chapters.py)."""
    return f"""You are analyzing a textbook to split it into chapters.

Return ONLY a JSON array. No markdown fences, no preamble.

[{{"number": 1, "title": "...", "start_marker": "first ~10 words of the chapter's
opening text, copied exactly"}}]

Rules:
- Use the book's own chapter divisions. Do not invent your own.
- Chapters are the book's major top-level divisions — typically 5 to 20 of them
  in a whole book. Do NOT report numbered subsections (e.g. "1.1", "1.2", "2.3")
  as if they were chapters; those live inside a chapter, they don't start one.
- start_marker must be copied verbatim from the text so it can be located.
- Skip front matter (preface, acknowledgements, table of contents).
- If the text has no clear chapters, return one chapter titled after the document.

TEXT:
{text}"""
