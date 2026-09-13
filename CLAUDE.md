# LockedIn

Turn a PDF textbook into a structured course: chapters, lessons, and prose with
comprehension questions woven directly into the reading. Tracks mastery, not pages.

Built for HackRice 16 — Work & Productivity track.

---

## The product in one paragraph

A university student uploads a textbook PDF. LockedIn extracts the text, detects
chapters, splits them into short lessons, and interleaves comprehension questions
directly into the prose — so reading is checked as you go rather than tested at the
end. Progress is tracked as *mastery* (did you answer its questions correctly), not
completion. The student can generate custom quizzes across any chapters, get memory
quizzes that resurface old material, and select any passage to open an AI conversation
about it.

---

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.11+ / FastAPI | `pymupdf` for PDF text |
| DB | SQLite via SQLAlchemy | one file, no server |
| Frontend | React + Vite + Tailwind | `react-router`, `zustand` |
| AI | Google Gemini (`google-genai`) | backend only, never client |
| Auth | none — hardcoded `user_id = 1` | out of scope for hackathon |

`.env` holds `GEMINI_API_KEY`. Never commit it. Never call Gemini from the frontend.

---

## Content model

```
Book → Chapter → Lesson → Block[]
```

A **Lesson** is a continuous scroll, not a page of text followed by a quiz. It is an
ordered list of **Blocks**. A block is either `prose` or `question`. Reading flows
naturally and gets checked at the moment the concept lands.

Two question types:
- `mcq` — four options, one correct
- `open` — free text with an italic hint, graded by AI

Two progress dimensions, deliberately separate:
- **done** — the student read/answered through the lesson
- **mastered** — every question in it answered correctly (retries allowed)

Every question carries a `source`: `book` (extracted from the textbook's own
exercises), `ai` (generated), or `hybrid`. Prefer book questions where they exist;
top up with AI. Show a small "from the textbook" tag on book-sourced questions.

---

## Feature priority

**P0 — must work, this is the demo spine**
1. PDF upload → text extraction → chapters → lessons → blocks
2. Library page with book cards and progress
3. Book page: chapters expanding into lessons with status
4. Lesson page: alternating prose and question blocks, MCQ answerable with feedback
5. Progress persistence

**P1 — the differentiators, build in this order**
6. Select-text AI panel (conversation, not just buttons)
7. Open-response AI grading
8. Adaptive breakdown — wrong answer expands into smaller explanation + simpler check
9. Generate-quiz modal (chapters / difficulty / count)
10. Memory quizzes with spaced repetition
11. Streak + review-due surfacing on home

**P2 — only if ahead**
12. Audio explanations
13. Anything social

---

## Design system

Calm, bookish, quiet. Closer to a reading app than an edtech product. It must not
look AI-generated: no gradients, no drop shadows, no emoji, no bright gamified
badges, no purple-on-white SaaS look.

**Colors**
```
--cream       #FAF9F5   page background
--card        #FFFFFF   card surfaces
--ink         #1C1B19   primary text
--ink-muted   #6B6A65   prose body text (deliberately softer than titles)
--ink-faint   #9C9A93   metadata, mono labels
--border      #E8E6DF   hairline, 1px
--green       #3D7355   primary accent, progress, mastered
--green-bg    #EDF3EF   green tint fills
--indigo      #5B5BD6   MCQ label only
--orange      #C2703D   OPEN RESPONSE label only
--teal        #2B8C82   MATCHING label and match-highlight only
--teal-bg     #E7F2F0   teal tint fill (matched-pair highlight)
--amber-bg    #FBF3E4   partial-progress badge fill
--amber-text  #8A5A18   partial-progress badge text
```

Indigo, orange, and teal are **question-type signals only**. Never use them for
buttons, links, or decoration.

**Type**
- Serif (`Fraunces`) — book titles, lesson titles, page headings
- Sans (`Inter`) — body copy, UI, buttons
- Mono (`JetBrains Mono`) — metadata lines, badges, labels, subject tags

**Rules**
- Borders are 1px `--border`. No shadows anywhere.
- Cards: white, 12px radius, 1px border.
- Lesson prose is `--ink-muted`, not `--ink` — this makes white question cards step
  forward off the page. Deliberate; do not "fix" it.
- Generous whitespace. Lesson/quiz pages max out at ~1100px so they don't sit as
  a narrow strip on wide screens, but prose paragraphs themselves cap at ~760px
  for a readable line length. Book/library page containers max out at ~1400px.
- Sentence case everywhere except book titles.
- Streaks stay quiet: one mono line under the greeting. Never a badge or a popup.

---

## Conventions

- Backend routes under `/api`. Frontend dev server proxies to it.
- All AI calls go through `backend/app/ai/client.py`. One place, one retry policy.
- Every AI call that expects JSON must parse defensively and retry once on failure.
- Cache all generated content in the DB. Never regenerate on page load.
- Batch AI calls per section, not per question — Gemini free tier is ~10 req/min and
  RPM is the limit you will hit.
- IDs are UUID strings.
- Timestamps are UTC ISO 8601.

---

## Demo notes

The demo is a live PDF upload that becomes a course. Two safeguards:
- Stream progress during processing — chapters appearing one by one. Never a bare
  spinner.
- Keep one pre-processed book seeded in the DB as a fallback if upload stalls.

Judging is 2 min demo + 1 min Q&A, four times. Know how the chunking works well
enough to explain it.
