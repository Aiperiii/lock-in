# API

All routes under `/api`. JSON in, JSON out. `user_id` is always 1 — no auth.

---

## Books

### `POST /api/books/upload`
Multipart, field `file`. Returns immediately; processing runs in the background.

```json
{ "book_id": "uuid", "status": "processing" }
```

### `GET /api/books/{id}/status`
Poll this during processing. Frontend shows `stage` and the chapters as they land.

```json
{
  "status": "processing",
  "stage": "Splitting chapter 3 into lessons",
  "chapters_done": 3,
  "chapters_total": 8
}
```

### `GET /api/books`
Library view. Progress percent computed from lesson mastery.

```json
[{
  "id": "uuid", "title": "Introduction to Algorithms",
  "author": "Cormen, Leiserson, Rivest & Stein",
  "cover_seed": 42, "status": "ready",
  "progress_percent": 11,
  "last_opened_at": "2026-09-12T09:14:00Z"
}]
```

### `GET /api/books/{id}`
Full nested course. See `mock/course.json` for the exact shape.

### `DELETE /api/books/{id}`

---

## Lessons

### `GET /api/lessons/{id}`
Lesson with its ordered blocks, questions inlined, plus the user's prior attempts so
the UI can render already-answered questions in their answered state.

```json
{
  "id": "uuid", "title": "Big-O, Θ, and Ω Notation",
  "book_title": "Introduction to Algorithms",
  "chapter_number": 1, "estimated_minutes": 18,
  "status": "in_progress",
  "blocks": [
    { "id": "uuid", "order": 0, "kind": "prose",
      "content": "An algorithm's time complexity describes..." },
    { "id": "uuid", "order": 1, "kind": "question",
      "question": {
        "id": "uuid", "type": "mcq",
        "prompt": "A nested loop where the outer runs n times...",
        "options": ["O(n)", "O(n log n)", "O(n²)", "O(2ⁿ)"],
        "concept_tag": "nested-loop-complexity",
        "difficulty": "easy", "source": "book",
        "user_attempt": null
      }
    }
  ]
}
```

`correct_index`, `explanation`, and `model_answer` are **never** sent to the client
before an answer is submitted. Send them back in the answer response.

### `POST /api/lessons/{id}/complete`
Marks `done`, recomputes whether it is `mastered`.

---

## Answering

### `POST /api/questions/{id}/answer`

```json
{ "answer": "2" }
```

MCQ is checked locally — no AI call, instant. Open response goes to the grader.

```json
{
  "is_correct": true,
  "correct_index": 2,
  "explanation": "Each of the n outer iterations runs n inner iterations...",
  "feedback": null,
  "lesson_status": "in_progress",
  "streak_days": 6
}
```

For open responses, `feedback` carries the grader's response and `is_correct`
reflects its verdict.

### `POST /api/questions/{id}/breakdown`
Adaptive breakdown. Called after a wrong answer when the student taps "break this
down". Generates smaller sub-explanations with a simpler check, caches them as child
questions with `parent_question_id` set.

```json
{
  "steps": [
    { "explanation": "First, just count the outer loop...",
      "question": { "id": "uuid", "type": "mcq", "prompt": "...", "options": ["..."] } }
  ]
}
```

---

## Quizzes

### `POST /api/quizzes/generate`

```json
{ "book_id": "uuid", "chapter_ids": ["uuid"], "difficulty": "mixed", "count": 10 }
```

Selection logic: prefer unused `book`-sourced questions from the chosen chapters,
top up with freshly generated ones. Returns a quiz with questions in the same shape
as lesson questions.

### `GET /api/quizzes/{id}` / `POST /api/quizzes/{id}/submit`

---

## Review

### `GET /api/review/due`
Questions with `due_at <= now`, ordered by how badly they were failed. Powers the
"3 to review" card on home.

### `POST /api/review/generate`
Fresh questions on concepts the student has struggled with. Pass the questions they
have already seen so the model produces genuinely new ones, not paraphrases.

---

## AI panel

### `POST /api/ai/ask`

```json
{
  "lesson_id": "uuid",
  "selected_text": "Big-O notation captures the worst-case upper bound",
  "message": "why do we discard constants?",
  "conversation_id": null
}
```

Returns `{ "conversation_id": "uuid", "reply": "..." }`. Pass `conversation_id` back
on follow-ups to keep the thread. The three shortcut buttons just prefill `message`
with a canned prompt — same endpoint, no special casing.

---

## Home

### `GET /api/home`

```json
{
  "greeting_name": "Aya",
  "subject_tags": ["algorithms", "data structures", "discrete math"],
  "streak_days": 6,
  "review_due_count": 3,
  "continue": { "book_id": "uuid", "title": "...", "author": "...",
                "cover_seed": 42, "progress_percent": 11 }
}
```
