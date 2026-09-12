# Schema

SQLAlchemy models. All IDs are UUID strings. All timestamps UTC.

---

## Book

| field | type | notes |
|---|---|---|
| id | str PK | uuid |
| title | str | extracted or filename fallback |
| author | str nullable | extracted if findable |
| source_filename | str | original upload name |
| cover_seed | int | drives generated cover pattern + palette |
| status | str | `processing` \| `ready` \| `failed` |
| processing_stage | str nullable | human-readable, shown during upload |
| created_at | datetime | |

`cover_seed` is a random int stored at creation. The frontend derives the cover
pattern and palette from it deterministically, so covers are stable across reloads.

## Chapter

| field | type | notes |
|---|---|---|
| id | str PK | |
| book_id | str FK | |
| number | int | 1-based, display order |
| title | str | |
| summary | str nullable | one line, AI-generated |

## Lesson

| field | type | notes |
|---|---|---|
| id | str PK | |
| chapter_id | str FK | |
| number | int | order within chapter |
| title | str | |
| estimated_minutes | int | from word count + question count |
| kind | str | `reading` \| `practice` |
| concept_tags | JSON list[str] | drives memory quiz selection |

`practice` lessons are mostly questions with little prose — used when the source
chapter has a dense exercise set.

## Block

| field | type | notes |
|---|---|---|
| id | str PK | |
| lesson_id | str FK | |
| order | int | position in the lesson scroll |
| kind | str | `prose` \| `question` |
| content | text nullable | markdown, when kind=prose |
| question_id | str FK nullable | when kind=question |

## Question

| field | type | notes |
|---|---|---|
| id | str PK | |
| lesson_id | str FK | owning lesson |
| type | str | `mcq` \| `open` |
| prompt | text | |
| options | JSON list[str] nullable | mcq only, 4 items |
| correct_index | int nullable | mcq only |
| hint | str nullable | open only, rendered italic |
| explanation | text | why the answer is right |
| model_answer | text nullable | open only, used for grading |
| concept_tag | str | what this tests — used by memory quizzes |
| difficulty | str | `easy` \| `medium` \| `hard` |
| source | str | `book` \| `ai` \| `hybrid` |
| parent_question_id | str FK nullable | set on adaptive-breakdown children |

## LessonProgress

| field | type | notes |
|---|---|---|
| id | str PK | |
| user_id | int | always 1 |
| lesson_id | str FK | |
| status | str | `not_started` \| `in_progress` \| `done` \| `mastered` |
| started_at | datetime nullable | |
| completed_at | datetime nullable | |

Unique on (user_id, lesson_id).

**Mastery rule:** a lesson is `mastered` when every question belonging to it has at
least one correct attempt. Retries allowed and expected — mastery is about eventual
understanding, not first-try performance. `done` means the student reached the end
without mastering everything.

## QuestionAttempt

| field | type | notes |
|---|---|---|
| id | str PK | |
| user_id | int | |
| question_id | str FK | |
| answer | text | index as string for mcq, raw text for open |
| is_correct | bool | |
| feedback | text nullable | AI grader output, open only |
| attempt_number | int | 1-based per (user, question) |
| answered_at | datetime | |

Every attempt is logged, including retries. Percentages are computed from these
rows, never stored, so nothing goes stale.

## ReviewItem

| field | type | notes |
|---|---|---|
| id | str PK | |
| user_id | int | |
| question_id | str FK | |
| concept_tag | str | denormalized for fast selection |
| due_at | datetime | |
| interval_days | float | |
| ease | float | default 2.5 |

Spaced repetition, SM-2-lite:
- correct → `interval = max(1, interval * ease)`, `ease += 0.1` (cap 3.0)
- wrong → `interval = 1`, `ease = max(1.3, ease - 0.2)`
- `due_at = now + interval_days`

Created the first time a question is answered.

## Streak

| field | type | notes |
|---|---|---|
| user_id | int PK | |
| current_days | int | |
| longest_days | int | |
| last_active_date | date | |

Updated on any question attempt. Same day = no change; consecutive day = increment;
gap = reset to 1.

## AIConversation / AIMessage

For the select-text panel. Conversation holds `lesson_id` and `selected_text`;
messages hold `role` (`user` \| `assistant`) and `content`. Ephemeral — no UI for
browsing past conversations, but persisting them makes follow-up context trivial.
