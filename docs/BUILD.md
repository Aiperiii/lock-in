# Build order

Each task is scoped so you can read the diff, run it, and commit. Do not skip the
running. Do not batch three tasks before testing.

Before starting: `claude` in the repo root, then say
"Read CLAUDE.md, docs/SCHEMA.md, docs/API.md and docs/PROMPTS.md before we begin."

---

## Backend

### B1 — Scaffold (~20 min)
> Set up a FastAPI backend in `backend/`. Create the SQLAlchemy models exactly as
> specified in docs/SCHEMA.md, using SQLite at `backend/lockedin.db`. Add CORS for
> localhost:5173. Add a `GET /api/health` route. Include a `requirements.txt`.
> Do not create any other routes yet.

Test: `uvicorn app.main:app --reload`, open `/docs`, hit health.
Commit.

### B2 — Seed from mock (~15 min)
> Write `backend/scripts/seed.py` that loads `mock/course.json` and inserts it into
> the database as a Book with its chapters, lessons, blocks and questions. Also seed
> LessonProgress so lesson 1.1 is `mastered` and lesson 1.2 is `in_progress` with 2
> of 3 questions answered correctly, and a Streak of 6 days.

Test: run it, then check the DB has rows. This gives the frontend something real
immediately and is your demo fallback.
Commit.

### B3 — Read endpoints (~25 min)
> Implement `GET /api/books`, `GET /api/books/{id}`, `GET /api/lessons/{id}` and
> `GET /api/home` exactly as specified in docs/API.md. Compute progress percentages
> from LessonProgress and QuestionAttempt rows — never store them. Never send
> correct_index, explanation or model_answer to the client before an answer is
> submitted.

Test: hit each in `/docs`, compare shape against docs/API.md.
Commit.

### B4 — Answering (~30 min)
> Implement `POST /api/questions/{id}/answer`. MCQ is checked locally with no AI
> call. Log a QuestionAttempt every time including retries. Recompute lesson status
> using the mastery rule in docs/SCHEMA.md. Update Streak. Create or update the
> ReviewItem using the SM-2-lite rules. Leave open-response grading returning a
> stub for now.

Test: answer right, answer wrong, answer again. Check attempts accumulate and
lesson status changes.
Commit.

### B5 — Gemini client (~20 min)
> Create `backend/app/ai/client.py` with a single `generate_json(prompt)` helper
> using google-genai and GEMINI_API_KEY from .env, model gemini-2.0-flash. It must
> strip markdown fences, parse JSON, and retry once with a corrective nudge if
> parsing fails. Add a `generate_text(prompt, history)` for conversational calls.
> Write a tiny script that proves both work.

Test: run the script. This must work before anything else AI-related.
Commit.

### B6 — PDF pipeline (~90 min, the risky one)
Do this in four separate turns, testing between each:

> a) Add `POST /api/books/upload` that saves the PDF to `backend/uploads/`, extracts
> text with pymupdf, creates a Book row with status=processing, and returns the id.
> Add `GET /api/books/{id}/status`.

> b) Add chapter detection using the prompt in docs/PROMPTS.md section 1. Locate
> each start_marker in the text with fuzzy matching to get offsets, then slice the
> text into chapters. Store them and update processing_stage as it goes.

> c) Add lesson splitting per chapter using section 2 of docs/PROMPTS.md.

> d) Add block generation per lesson using section 3. Run the whole pipeline as a
> FastAPI BackgroundTask. Batch calls and add a small delay between them so we stay
> under Gemini's rate limit.

Test each stage with a real chapter PDF before moving to the next.
Commit after each.

### B7 — Open-response grading (~20 min)
Prompt section 4. Wire into the answer endpoint.

### B8 — AI panel (~25 min)
`POST /api/ai/ask` with conversation persistence, prompt section 7.

### B9 — Breakdown, quiz generation, review
Prompt sections 5, 6. Endpoints per docs/API.md.

---

## Frontend

### F1 — Foundation (~30 min)
> Set up React + Vite + Tailwind in `frontend/`. Configure the exact colors and
> fonts from the design system in CLAUDE.md as Tailwind theme tokens. Load Fraunces,
> Inter and JetBrains Mono from Google Fonts. Build shared primitives only: Card,
> Button, ProgressBar, Badge, MonoLabel. No pages yet.

### F2 — Cover art (~20 min)
> Build a `BookCover` component that deterministically generates a pastel patterned
> cover from a `cover_seed` integer — a soft background tint plus a repeating
> geometric motif, with the title and author overlaid in serif. Four palettes: sage
> green, lavender, powder blue, warm sand. No images, pure CSS or inline SVG.

### F3 — Library page (~40 min)
Screenshot 1. Serif greeting, mono subject tags, continue-reading card, grid, add tile.

### F4 — Book page (~50 min)
Screenshot 2. Header with mastery ring, expandable chapters, lesson rows with badges.

### F5 — Lesson page (~60 min)
Screenshots 3-5. The alternating block scroll. Prose in `--ink-muted`. MCQ and open
cards with mono labels in indigo and orange.

### F6 — AI panel (~45 min)
Text selection, anchored panel, quoted selection, three shortcut buttons, free-text
input, threaded replies.

### F7 — Upload flow (~40 min)
Drop zone, then a live processing view that polls status and shows chapters
appearing one by one. Never a bare spinner — this is demo-critical.

### F8 — Quiz modal, review, polish

---

## Rules

- Run after every task. Commit after every task that runs.
- Frontend builds against `mock/course.json` until B3 is done, then switches.
- If a task's diff is longer than you want to read, the task was too big. Revert
  and split it.
- Two-thirds through your time: whatever exists must work end to end.
- Three hours before the deadline: stop building. Bug fixes and demo prep only.
