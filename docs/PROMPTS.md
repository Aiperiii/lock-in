# AI prompts

All calls go through `backend/app/ai/client.py`. Every JSON-returning call must
parse defensively and retry once with a "your last output was not valid JSON,
return only JSON" nudge.

Model: `gemini-2.0-flash` (generous free-tier RPM). Batch per section, never per
question — RPM is the limit you will hit, not tokens.

---

## 1. Chapter detection

Input: first ~15k chars of extracted text plus any TOC-looking region.

```
You are analyzing a textbook to split it into chapters.

Return ONLY a JSON array. No markdown fences, no preamble.

[{"number": 1, "title": "...", "start_marker": "first ~10 words of the chapter's
opening text, copied exactly"}]

Rules:
- Use the book's own chapter divisions. Do not invent your own.
- start_marker must be copied verbatim from the text so it can be located.
- Skip front matter (preface, acknowledgements, table of contents).
- If the text has no clear chapters, return one chapter titled after the document.

TEXT:
{text}
```

Locate each `start_marker` with a fuzzy find to get character offsets, then slice.

---

## 2. Lesson splitting

Input: one chapter's text.

```
Split this chapter into lessons a student can complete in one sitting
(8-20 minutes each).

Return ONLY JSON:
[{"number": 1, "title": "...", "kind": "reading"|"practice",
  "concept_tags": ["kebab-case-concept"],
  "start_marker": "first ~10 words, verbatim"}]

Rules:
- Each lesson covers ONE coherent idea. A lesson that needs "and" in its title is
  probably two lessons.
- kind is "practice" when the segment is mostly exercises rather than exposition.
- 3-6 lessons per chapter is typical.
- Titles should read like a good textbook's section headings, not like clickbait.

CHAPTER: {chapter_title}
TEXT: {text}
```

---

## 3. Block generation — the core call

Input: one lesson's text. This is the call that defines the product, so it gets the
most instruction.

```
Turn this lesson text into an interleaved reading experience: prose broken into
short passages, with comprehension questions placed at the moments a concept has
just landed.

Return ONLY JSON:
{
 "blocks": [
   {"kind": "prose", "content": "markdown, 2-4 sentences"},
   {"kind": "question", "question": {
      "type": "mcq",
      "prompt": "...",
      "options": ["...","...","...","..."],
      "correct_index": 0,
      "explanation": "why this is right, 1-2 sentences",
      "concept_tag": "kebab-case",
      "difficulty": "easy"|"medium"|"hard",
      "source": "book"|"ai"
   }}
 ]
}

Open-response questions use:
  {"type":"open","prompt":"...","hint":"italic nudge, phrased as a question",
   "model_answer":"what a full-credit answer contains",
   "explanation":"...","concept_tag":"...","difficulty":"...","source":"..."}

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
TEXT: {text}
```

---

## 4. Open-response grading

```
Grade a student's free-text answer. Be generous about wording, strict about
understanding.

Return ONLY JSON:
{"is_correct": true, "feedback": "2-3 sentences addressed to the student"}

Rules:
- Correct if they grasp the idea, even if informal or partial in phrasing.
- Incorrect if a core misconception is present.
- Feedback names specifically what they got right before what they missed.
- Never sarcastic, never disappointed. Encouraging and concrete.
- Address them as "you".

QUESTION: {prompt}
WHAT A GOOD ANSWER CONTAINS: {model_answer}
SOURCE TEXT: {lesson_excerpt}
STUDENT ANSWER: {answer}
```

---

## 5. Adaptive breakdown

Fired after a wrong answer, when the student asks for it.

```
A student got this wrong. Break the idea into 2-3 smaller steps, each with a short
explanation and one easy check, so they can rebuild the understanding piece by piece.

Return ONLY JSON:
{"steps": [{"explanation": "2-3 sentences on ONE small piece",
            "question": {"type":"mcq","prompt":"...","options":["..."],
                         "correct_index":0,"explanation":"...",
                         "concept_tag":"...","difficulty":"easy"}}]}

Rules:
- Step 1 must be genuinely easy — the goal is regaining footing, not testing again.
- Each step builds on the previous one.
- Address the specific misconception their wrong answer suggests.
- Never reference that they failed. No "since you struggled with".

QUESTION THEY MISSED: {prompt}
THEIR ANSWER: {answer}
CORRECT ANSWER: {correct}
SOURCE TEXT: {lesson_excerpt}
```

---

## 6. Memory quiz generation

```
Generate {count} questions testing these concepts in ways the student has NOT seen.

Return ONLY JSON: {"questions": [ ...same question shape as above... ]}

Rules:
- Test the same understanding from a different angle. If a previous question was
  recall, make this one apply-to-a-scenario. If it was a definition, make this one
  spot-the-error.
- Never paraphrase a question they have already seen.
- Vary difficulty across the set.

CONCEPTS: {concept_tags}
SOURCE TEXT: {relevant_excerpts}
QUESTIONS ALREADY SEEN: {previous_prompts}
```

---

## 7. Select-text AI panel

System prompt for the conversation:

```
You are helping a university student understand a passage from their textbook.

The passage they selected:
"{selected_text}"

Surrounding lesson context:
{lesson_excerpt}

Answer their questions about this passage. Stay anchored to it — if they drift far
off topic, gently bring it back. Be concise: 2-4 sentences unless they ask for
depth. Use their book's notation and terminology. Never invent facts the source
does not support; if the passage does not settle something, say so.
```

Shortcut buttons prefill the user message:
- **Deep dive** → "Explain this in more depth, including why it matters."
- **Practice questions** → "Give me 2 practice questions on this, with answers hidden until I ask."
- **More examples** → "Give me two concrete examples of this."

They are ordinary messages. No special casing in the endpoint.
