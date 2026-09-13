import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { getBook } from '../api/client'
import Badge from '../components/Badge'
import BookCover from '../components/BookCover'
import Button from '../components/Button'
import MasteryRing from '../components/MasteryRing'
import MonoLabel from '../components/MonoLabel'
import QuizModal from '../components/QuizModal'

const LESSON_BADGE = {
  mastered: { tone: 'mastered', label: 'Mastered' },
  in_progress: { tone: 'partial', label: 'In progress' },
  done: { tone: 'neutral', label: 'Done' },
  // not_started gets no badge — a quiet default needs no announcing.
}

// Mirrors DONE_STATUSES in app/pipeline/auto_quiz.py — the same condition
// that decides whether a chapter/book is complete enough to trigger a quiz.
const DONE_STATUSES = new Set(['done', 'mastered'])

function isBookComplete(book) {
  return book.chapters.every((c) => c.lessons.every((l) => DONE_STATUSES.has(l.status)))
}

function ArrowLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="19" y1="12" x2="5" y2="12" strokeLinecap="round" />
      <polyline points="12 19 5 12 12 5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round" />
      <polyline points="12 5 19 12 12 19" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

function ChevronIcon({ expanded }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`h-4 w-4 shrink-0 text-ink-faint transition-transform ${expanded ? 'rotate-180' : ''}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <polyline points="6 9 12 15 18 9" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="20 6 9 17 4 12" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

function SparkleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-green" fill="currentColor">
      <path d="M12 2.5c.4 3.2 1.1 5.3 2.1 6.4 1 1 3.1 1.8 6.4 2.1-3.3.4-5.3 1.1-6.4 2.1-1 1-1.7 3.1-2.1 6.4-.4-3.3-1.1-5.3-2.1-6.4-1-1-3.1-1.7-6.4-2.1 3.3-.4 5.3-1.1 6.4-2.1 1-1 1.7-3.1 2.1-6.4z" />
    </svg>
  )
}

function StatusCircle({ status }) {
  if (status === 'mastered') {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green text-white">
        <CheckIcon />
      </span>
    )
  }
  if (status === 'in_progress' || status === 'done') {
    return <span className="h-5 w-5 shrink-0 rounded-full border-2 border-amber-text" />
  }
  return <span className="h-5 w-5 shrink-0 rounded-full border border-border" />
}

function LessonRow({ lesson }) {
  const badge = LESSON_BADGE[lesson.status]
  return (
    <Link
      to={`/lessons/${lesson.id}`}
      className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-card"
    >
      <StatusCircle status={lesson.status} />
      <span className="min-w-0 flex-1 truncate text-ink">{lesson.title}</span>
      <MonoLabel tone="faint">{lesson.estimated_minutes} min</MonoLabel>
      {badge && <Badge tone={badge.tone}>{badge.label}</Badge>}
    </Link>
  )
}

/** An automatically generated quiz (end of chapter or end of course, see
 * app/pipeline/auto_quiz.py) — deliberately NOT styled like a lesson row.
 * It's a bonus that appears once every real lesson is already mastered, not
 * one more thing standing between the chapter and its 100%, so it gets its
 * own visual language: a green-tinted pill instead of a plain list row, a
 * sparkle instead of the lesson status circle, and its meta line called out
 * in the accent color rather than the quiet faint tone lesson metadata uses.
 * (CLAUDE.md's design tokens don't define a --text-accent; --green is the
 * documented "primary accent" color, so that's what this uses for it.) */
function QuizRow({ quiz, label }) {
  return (
    <Link
      to={`/quizzes/${quiz.id}`}
      className="flex items-center gap-3 rounded-full bg-green-bg px-4 py-2.5 transition-colors hover:bg-green-bg/70"
    >
      <SparkleIcon />
      <span className="min-w-0 flex-1 truncate text-ink">{label}</span>
      <MonoLabel tone="green">
        {quiz.question_count} question{quiz.question_count === 1 ? '' : 's'}
      </MonoLabel>
    </Link>
  )
}

/** A quiz generated through the manual "Generate quiz" flow rather than an
 * automatic chapter/course trigger — listed flatly under its own "Additional
 * quizzes" heading, so it doesn't need the pill treatment QuizRow uses to
 * keep an automatic quiz from reading as an unfinished lesson; there's no
 * lesson list here for it to be confused with. No score shown until it's
 * been started at least once — same "a quiet default needs no announcing"
 * rule LessonRow's badge follows.
 *
 * `number` is this quiz's 1-based position in the book's manual-quizzes
 * list, which the backend returns oldest-first specifically so "Quiz 1",
 * "Quiz 2", ... reads as creation order rather than an arbitrary index. */
function ManualQuizRow({ quiz, number }) {
  return (
    <Link
      to={`/quizzes/${quiz.id}`}
      className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-card"
    >
      <SparkleIcon />
      <span className="min-w-0 flex-1 truncate text-ink">
        Quiz {number} · {quiz.difficulty} · {quiz.question_count} questions
      </span>
      {quiz.score && (
        <MonoLabel tone="faint">
          {quiz.score.correct}/{quiz.score.total} correct
        </MonoLabel>
      )}
    </Link>
  )
}

function ChapterRow({ chapter, expanded, onToggle }) {
  const total = chapter.lessons.length
  const mastered = chapter.lessons.filter((l) => l.status === 'mastered').length
  const percent = total > 0 ? Math.round((100 * mastered) / total) : 0
  const badgeTone = percent === 100 ? 'mastered' : percent > 0 ? 'partial' : 'neutral'

  return (
    <div className="border-b border-border">
      <button type="button" onClick={onToggle} className="flex w-full items-center gap-4 py-5 text-left">
        <span className="w-8 shrink-0 font-serif text-xl text-ink-faint">
          {String(chapter.number).padStart(2, '0')}
        </span>
        <span className="min-w-0 flex-1 truncate font-serif text-lg text-ink">{chapter.title}</span>
        <MonoLabel tone="faint" className="hidden sm:inline">
          {mastered}/{total} mastered
        </MonoLabel>
        <Badge tone={badgeTone}>{percent}%</Badge>
        <ChevronIcon expanded={expanded} />
      </button>
      {expanded && (
        <div className="pb-4 pl-12">
          {chapter.lessons.map((lesson) => (
            <LessonRow key={lesson.id} lesson={lesson} />
          ))}
          {chapter.quiz && (
            <>
              {/* Dashed, not the solid hairline elsewhere in this design system —
                  a deliberate visual break so the quiz never reads as "one more
                  lesson row" continuing the list above it. */}
              <div className="my-3 border-t border-dashed border-border" />
              <QuizRow quiz={chapter.quiz} label="End of chapter quiz" />
            </>
          )}
        </div>
      )}
    </div>
  )
}

/** First in_progress lesson in reading order, else the first not_started
 * one, else null — where "Continue" should send the student. */
function findContinueLesson(chapters) {
  const lessons = chapters.flatMap((c) => c.lessons)
  return (
    lessons.find((l) => l.status === 'in_progress') ?? lessons.find((l) => l.status === 'not_started') ?? null
  )
}

export default function BookPage() {
  const { id } = useParams()
  const [book, setBook] = useState(null)
  const [error, setError] = useState(null)
  const [expandedIds, setExpandedIds] = useState(null)
  const [quizModalOpen, setQuizModalOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    setBook(null)
    setError(null)
    getBook(id)
      .then((data) => {
        if (cancelled) return
        setBook(data)
        // Default-expand whichever chapter holds the "continue" lesson, so
        // the student sees relevant context without an extra click.
        const continueLesson = findContinueLesson(data.chapters)
        const chapterToExpand = data.chapters.find((c) =>
          c.lessons.some((l) => l.id === continueLesson?.id),
        )
        setExpandedIds(new Set(chapterToExpand ? [chapterToExpand.id] : []))
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  // An automatic quiz (app/pipeline/auto_quiz.py) can appear seconds after
  // the answer that triggers it, generated in a background task — nothing
  // pushes that update to an open book page, so without this the new "End
  // of chapter/course quiz" row only shows up after a manual reload. Poll
  // while there's still something to become complete; once every chapter's
  // lessons are done/mastered there's nothing left to trigger, so it stops
  // on its own rather than polling an already-finished book forever.
  const complete = book ? isBookComplete(book) : true
  useEffect(() => {
    if (complete) return
    let cancelled = false
    const timer = setInterval(() => {
      getBook(id)
        .then((data) => {
          if (!cancelled) setBook(data)
        })
        .catch(() => {})
    }, 4000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [id, complete])

  const stats = useMemo(() => {
    if (!book) return null
    const lessons = book.chapters.flatMap((c) => c.lessons)
    const mastered = lessons.filter((l) => l.status === 'mastered').length
    return { mastered, total: lessons.length, continueLesson: findContinueLesson(book.chapters) }
  }, [book])

  if (error) {
    return <p className="mx-auto max-w-[1400px] px-6 py-10 text-ink-muted">Couldn't load this book.</p>
  }
  if (!book || !stats) {
    return <p className="mx-auto max-w-[1400px] px-6 py-10 text-ink-faint">Loading…</p>
  }

  return (
    <div>
      <header className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-2 gap-y-3 px-6 py-5">
        <Link
          to="/"
          className="flex shrink-0 items-center gap-1.5 font-mono text-sm text-ink-faint transition-colors hover:text-ink-muted"
        >
          <ArrowLeftIcon />
          Library
        </Link>
        <h1 className="min-w-0 flex-1 truncate font-serif text-sm text-ink-muted">{book.title}</h1>
        <Button variant="secondary" className="shrink-0" onClick={() => setQuizModalOpen(true)}>
          Generate quiz
        </Button>
      </header>

      {quizModalOpen && <QuizModal book={book} onClose={() => setQuizModalOpen(false)} />}

      <div className="mx-auto max-w-[1400px] px-6">
        <div className="flex flex-col gap-6 rounded-xl border border-border bg-green-bg p-8 sm:flex-row sm:items-center">
          <div className="w-28 shrink-0 sm:w-32">
            <BookCover coverSeed={book.cover_seed} title={book.title} author={book.author} size="sm" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="font-serif text-2xl text-ink sm:text-3xl">{book.title}</h2>
            {book.author && <p className="mt-1 text-ink-muted">{book.author}</p>}
          </div>
          <div className="flex items-center gap-4">
            <div className="flex flex-col items-center gap-1">
              <MasteryRing percent={book.progress_percent} />
              <MonoLabel tone="faint" className="whitespace-nowrap">
                {stats.mastered} of {stats.total} mastered
              </MonoLabel>
            </div>
            {stats.continueLesson && (
              <Link to={`/lessons/${stats.continueLesson.id}`}>
                <Button variant="dark">
                  Continue
                  <ArrowIcon />
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] px-6 py-10">
        {book.final_quiz && (
          <Link
            to={`/quizzes/${book.final_quiz.id}`}
            className="mb-6 flex items-center gap-3 rounded-full bg-green-bg px-6 py-3 transition-colors hover:bg-green-bg/70"
          >
            <SparkleIcon />
            <span className="min-w-0 flex-1 truncate font-serif text-lg text-ink">End of course quiz</span>
            <MonoLabel tone="green">
              {book.final_quiz.question_count} question{book.final_quiz.question_count === 1 ? '' : 's'}
            </MonoLabel>
          </Link>
        )}
        {book.chapters.map((chapter) => (
          <ChapterRow
            key={chapter.id}
            chapter={chapter}
            expanded={expandedIds.has(chapter.id)}
            onToggle={() =>
              setExpandedIds((prev) => {
                const next = new Set(prev)
                if (next.has(chapter.id)) next.delete(chapter.id)
                else next.add(chapter.id)
                return next
              })
            }
          />
        ))}

        {book.manual_quizzes.length > 0 && (
          <div className="mt-10">
            <h2 className="mb-4 font-mono text-xs uppercase tracking-wide text-ink-faint">
              Additional quizzes
            </h2>
            <div className="flex flex-col gap-1">
              {book.manual_quizzes.map((quiz, i) => (
                <ManualQuizRow key={quiz.id} quiz={quiz} number={i + 1} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
