import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { getBook } from '../api/client'
import Badge from '../components/Badge'
import BookCover from '../components/BookCover'
import Button from '../components/Button'
import MasteryRing from '../components/MasteryRing'
import MonoLabel from '../components/MonoLabel'

const LESSON_BADGE = {
  mastered: { tone: 'mastered', label: 'Mastered' },
  in_progress: { tone: 'partial', label: 'In progress' },
  done: { tone: 'neutral', label: 'Done' },
  // not_started gets no badge — a quiet default needs no announcing.
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

  const stats = useMemo(() => {
    if (!book) return null
    const lessons = book.chapters.flatMap((c) => c.lessons)
    const mastered = lessons.filter((l) => l.status === 'mastered').length
    return { mastered, total: lessons.length, continueLesson: findContinueLesson(book.chapters) }
  }, [book])

  if (error) {
    return <p className="mx-auto max-w-6xl px-6 py-10 text-ink-muted">Couldn't load this book.</p>
  }
  if (!book || !stats) {
    return <p className="mx-auto max-w-6xl px-6 py-10 text-ink-faint">Loading…</p>
  }

  return (
    <div>
      <header className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-2 gap-y-3 px-6 py-5">
        <Link
          to="/"
          className="flex shrink-0 items-center gap-1.5 font-mono text-xs text-ink-faint transition-colors hover:text-ink-muted"
        >
          <ArrowLeftIcon />
          Library
        </Link>
        <h1 className="min-w-0 flex-1 truncate font-serif text-sm text-ink-muted">{book.title}</h1>
        <Button variant="secondary" className="shrink-0">
          Generate quiz
        </Button>
      </header>

      <div className="mx-auto max-w-6xl px-6">
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

      <div className="mx-auto max-w-6xl px-6 py-10">
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
      </div>
    </div>
  )
}
