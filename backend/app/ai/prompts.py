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


def lesson_splitting_prompt(chapter_title: str, text: str) -> str:
    """docs/PROMPTS.md section 2. `text` is one chapter's full text."""
    return f"""Split this chapter into lessons a student can complete in one sitting
(8-20 minutes each).

Return ONLY JSON:
[{{"number": 1, "title": "...", "kind": "reading"|"practice",
  "concept_tags": ["kebab-case-concept"],
  "start_marker": "first ~10 words, verbatim"}}]

Rules:
- Each lesson covers ONE coherent idea. A lesson that needs "and" in its title is
  probably two lessons.
- kind is "practice" when the segment is mostly exercises rather than exposition.
- 3-6 lessons per chapter is typical.
- Titles should read like a good textbook's section headings, not like clickbait.

CHAPTER: {chapter_title}
TEXT: {text}"""


def block_generation_prompt(lesson_title: str, text: str) -> str:
    """docs/PROMPTS.md section 3 — the call that defines the product."""
    return f"""Turn this lesson text into an interleaved reading experience: prose broken into
short passages, with comprehension questions placed at the moments a concept has
just landed.

Return ONLY JSON:
{{
 "blocks": [
   {{"kind": "prose", "content": "markdown, 2-4 sentences"}},
   {{"kind": "question", "question": {{
      "type": "mcq",
      "prompt": "...",
      "options": ["...","...","...","..."],
      "correct_index": 0,
      "explanation": "why this is right, 1-2 sentences",
      "concept_tag": "kebab-case",
      "difficulty": "easy"|"medium"|"hard",
      "source": "book"|"ai"
   }}}}
 ]
}}

Open-response questions use:
  {{"type":"open","prompt":"...","hint":"italic nudge, phrased as a question",
   "model_answer":"what a full-credit answer contains",
   "explanation":"...","concept_tag":"...","difficulty":"...","source":"..."}}

Rules for prose:
- Rewrite for clarity but keep the book's technical content exactly. Never add
  claims the source does not make.
- 2-4 sentences per prose block. Long walls defeat the point.
- Preserve notation, formulas, and examples from the source.

Rules for questions:
- A question comes right after the passage that answers it, never before.
- Roughly 1 question per 2-3 prose blocks. Do not check trivia; check understanding.
- If the source text contains its own exercises, USE THEM. Set source to "book" and
  keep the original wording. Only generate your own to fill gaps, marked "ai".
- MCQ distractors must be plausible misconceptions a student would actually hold.
  Never absurd options, never "all of the above".
- Mix question types: about 70% mcq, 30% open. Open questions are for "explain why"
  and "in your own words", never for facts with one short answer.
- Test only what is in this text. Never require outside knowledge.

LESSON: {lesson_title}
TEXT: {text}"""


def grading_prompt(question_prompt: str, model_answer: str, lesson_excerpt: str, answer: str) -> str:
    """docs/PROMPTS.md section 4."""
    return f"""Grade a student's free-text answer. Be generous about wording, strict about
understanding.

Return ONLY JSON:
{{"is_correct": true, "feedback": "2-3 sentences addressed to the student"}}

Rules:
- Correct if they grasp the idea, even if informal or partial in phrasing.
- Incorrect if a core misconception is present.
- Feedback names specifically what they got right before what they missed.
- Never sarcastic, never disappointed. Encouraging and concrete.
- Address them as "you".

QUESTION: {question_prompt}
WHAT A GOOD ANSWER CONTAINS: {model_answer}
SOURCE TEXT: {lesson_excerpt}
STUDENT ANSWER: {answer}"""
