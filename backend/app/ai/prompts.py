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
    return f"""Turn this lesson text into an interleaved reading experience: the book's own
prose broken into short passages, with comprehension questions placed at the
moments a concept has just landed.

Return ONLY JSON:
{{
 "blocks": [
   {{"kind": "prose", "content": "markdown, 2-4 sentences"}},
   {{"kind": "definition", "content": "markdown, the formal definition, near-verbatim"}},
   {{"kind": "example", "content": "markdown, the worked example, near-verbatim"}},
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
- Default to the book's own sentences, verbatim or near-verbatim. This is not a
  paraphrase-everything pass — the student should feel they are reading the real
  book, not a summary written by an AI.
- Only rephrase a specific sentence when it is genuinely unclear or overly dense
  out of context (e.g. it leans on something several pages earlier). Even then,
  stay close to the original wording and terminology — a light clarification, not
  a rewrite.
- Never add claims the source does not make.
- 2-4 sentences per prose block. Long walls defeat the point — split with the
  book's own paragraph and sentence breaks, don't compress them into a summary.
- Preserve notation, formulas, and examples from the source.
- Light emphasis for scanning, not decoration: **bold** a key term the first time
  it's defined in the lesson (e.g. "a **tautology** is a compound proposition that
  is always true"), and *italicize* a technical or mathematical term used
  descriptively elsewhere. At most one or two emphasized spans per prose block —
  most blocks need none at all. Never bold or italicize a whole sentence.

Rules for definitions and examples:
- Use "definition" when the source text itself presents something as a formal
  definition — a bolded/introduced term, an explicit "Definition N.N" marker, a
  set-off definition box in the original, or a sentence structured as "A/An X is
  a Y that...". Content should be that definition, near-verbatim.
- Use "example" when the source marks something as a worked example (an
  "Example N.N" marker, "For example, ...", a solved problem walked through
  step by step). Keep the book's own steps and numbers; don't invent a new
  example or shorten away the working.
- Don't force it — most lessons will have a handful of definition/example blocks
  at most, not one per paragraph. Ordinary prose stays kind "prose".

Rules for questions:
- A question comes right after the passage that answers it, never before.
- Roughly 1 question per 2-3 prose blocks.
- Every question must test something the student needs to understand this
  chapter's core material — never tangential facts, historical trivia, or
  name-dropped topics mentioned only in passing.
- If the source text contains its own exercises, USE THEM. Set source to "book" and
  keep the original wording. Only generate your own to fill gaps, marked "ai".
- Mix MCQ styles across the lesson — don't repeat one pattern for every question:
  - "spot the error": present a flawed statement or a worked step with a mistake
    in it; the options name what's wrong with it.
  - "fill in the blank": a sentence or equation missing one term, with four
    candidate terms to choose from.
  - straightforward concept-check — keep some of these, just not all of them.
  MCQ distractors must be plausible misconceptions a student would actually hold.
  Never absurd options, never strawmen, never "all of the above".
- Mix open-response styles too:
  - "explain why" / "in your own words" — keep some of these.
  - "apply this to a new example" — pose a scenario not found in the source text
    and ask the student to apply the concept to it.
  - "compare/contrast" two related concepts from the text.
- Mix question types: about 70% mcq, 30% open.
- Test only what is in this text. Never require outside knowledge.

LESSON: {lesson_title}
TEXT: {text}"""


def quiz_generation_prompt(
    count: int,
    difficulty: str,
    concept_tags: list[str],
    source_text: str,
    existing_prompts: list[str],
) -> str:
    """POST /api/quizzes/generate's "top up with freshly generated ones" step
    (docs/API.md) has no dedicated template of its own in docs/PROMPTS.md —
    this adapts section 6 (memory quiz generation), the closest existing
    shape: "generate N fresh questions on these concepts, distinct from ones
    already asked." Returns the same per-question JSON shape as block
    generation (section 3) so the result validates through the same
    app/pipeline/validate.py rules.
    """
    difficulty_rule = (
        "Vary difficulty across the set."
        if difficulty == "mixed"
        else f'Every question should be "{difficulty}" difficulty.'
    )
    seen = "\n".join(f"- {p}" for p in existing_prompts) or "(none yet)"
    tags = ", ".join(concept_tags) or "(none given — infer from the source text)"
    return f"""Generate {count} questions testing understanding of these concepts, grounded
only in the source text below.

Return ONLY JSON:
{{"questions": [
  {{"type": "mcq", "prompt": "...", "options": ["...","...","...","..."],
    "correct_index": 0, "explanation": "why this is right, 1-2 sentences",
    "concept_tag": "kebab-case", "difficulty": "easy"|"medium"|"hard"}},
  {{"type": "open", "prompt": "...", "hint": "italic nudge, phrased as a question",
    "model_answer": "what a full-credit answer contains", "explanation": "...",
    "concept_tag": "kebab-case", "difficulty": "easy"|"medium"|"hard"}}
]}}

Rules:
- Test understanding, not trivia recall. Never require outside knowledge — only
  what the source text supports.
- Every question must test something the student needs to understand this
  chapter's core material — never tangential facts, historical trivia, or
  name-dropped topics mentioned only in passing.
- Never paraphrase a question that has already been asked (listed below).
- {difficulty_rule}
- Mix MCQ styles — don't repeat one pattern:
  - "spot the error": a flawed statement or worked step; the options name what's
    wrong with it.
  - "fill in the blank": a sentence or equation missing one term, four candidates.
  - straightforward concept-check — keep some, just not all.
  MCQ distractors must be plausible misconceptions, never absurd, never
  strawmen, never "all of the above".
- Mix open-response styles: "explain why" (keep some), "apply this to a new
  example" not in the source text, and "compare/contrast" two related concepts.
- Mix question types: about 70% mcq, 30% open.

CONCEPTS: {tags}
SOURCE TEXT: {source_text}
QUESTIONS ALREADY ASKED: {seen}"""


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


def select_text_panel_prompt(selected_text: str, lesson_excerpt: str) -> str:
    """docs/PROMPTS.md section 7. This is the CONVERSATION'S system prompt,
    not a per-message prompt — passed as generate_text's system_instruction
    and re-sent unchanged on every turn of the thread, while the student's
    actual message (shortcut or free-text, "ordinary messages, no special
    casing" per docs/PROMPTS.md) goes through as the turn itself."""
    return f"""You are helping a university student understand a passage from their textbook.

The passage they selected:
"{selected_text}"

Surrounding lesson context:
{lesson_excerpt}

Answer their questions about this passage. Stay anchored to it — if they drift far
off topic, gently bring it back. Be concise: 2-4 sentences unless they ask for
depth. Use their book's notation and terminology. Never invent facts the source
does not support; if the passage does not settle something, say so."""
