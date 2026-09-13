import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { getLesson } from '../api/client'
import AIPanel from '../components/AIPanel'
import MonoLabel from '../components/MonoLabel'
import QuestionBlock from '../components/QuestionCard'
import RichText from '../components/RichText'

// Both prose-like, both selectable for the AI panel (data-prose-block) —
// only the visual weight differs. A definition is boxed and tinted, the way
// a textbook sets one off; an example just gets a quiet label, per the
// explicit "doesn't need its own box" call in the request that added these.
function DefinitionBlock({ content }) {
  return (
    <div data-prose-block className="max-w-[760px] rounded-lg border border-border bg-green-bg px-5 py-4">
      <MonoLabel tone="green">Definition</MonoLabel>
      <p className="mt-2 text-lg leading-relaxed text-ink">
        <RichText text={content} />
      </p>
    </div>
  )
}

function ExampleBlock({ content }) {
  return (
    <div data-prose-block className="max-w-[760px]">
      <MonoLabel tone="faint">Example</MonoLabel>
      <p className="mt-1 text-lg leading-relaxed text-ink-muted">
        <RichText text={content} />
      </p>
    </div>
  )
}

function ArrowLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="19" y1="12" x2="5" y2="12" strokeLinecap="round" />
      <polyline points="12 19 5 12 12 5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

/** The nearest [data-prose-block] ancestor of a selection endpoint, or null.
 * Selecting a range that starts and ends in the same prose block is what
 * opens the AI panel — a selection that spans into a question card, or
 * across two blocks, doesn't count as "text within a prose block". */
function proseBlockOf(node) {
  const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node
  return el?.closest('[data-prose-block]') ?? null
}

export default function LessonPage() {
  const { id } = useParams()
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState(null)
  const [selection, setSelection] = useState(null) // {text, rect} | null

  useEffect(() => {
    let cancelled = false
    setLesson(null)
    setError(null)
    getLesson(id)
      .then((data) => {
        if (!cancelled) setLesson(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  useEffect(() => {
    function onMouseUp() {
      const sel = window.getSelection()
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) return
      const text = sel.toString().trim()
      if (!text) return

      const range = sel.getRangeAt(0)
      const startBlock = proseBlockOf(range.startContainer)
      const endBlock = proseBlockOf(range.endContainer)
      if (!startBlock || startBlock !== endBlock) return

      setSelection({ text, rect: range.getBoundingClientRect() })
    }
    document.addEventListener('mouseup', onMouseUp)
    return () => document.removeEventListener('mouseup', onMouseUp)
  }, [])

  if (error) {
    return <p className="mx-auto max-w-[1100px] px-6 py-10 text-ink-muted">Couldn't load this lesson.</p>
  }
  if (!lesson) {
    return <p className="mx-auto max-w-[1100px] px-6 py-10 text-ink-faint">Loading…</p>
  }

  return (
    <div className="mx-auto max-w-[1100px] px-6 py-10">
      <Link
        to={`/books/${lesson.book_id}`}
        className="flex items-center gap-1.5 font-mono text-xs text-ink-faint transition-colors hover:text-ink-muted"
      >
        <ArrowLeftIcon />
        Back to chapter
      </Link>

      <MonoLabel tone="faint" className="mt-4 block">
        {lesson.book_title} · Ch. {lesson.chapter_number} · {lesson.estimated_minutes} min
      </MonoLabel>
      <h1 className="mt-2 mb-8 font-serif text-3xl text-ink">{lesson.title}</h1>

      <div className="flex flex-col gap-6">
        {lesson.blocks.map((block) => {
          if (block.kind === 'question') {
            return <QuestionBlock key={block.id} question={block.question} collapsible />
          }
          if (block.kind === 'definition') {
            return <DefinitionBlock key={block.id} content={block.content} />
          }
          if (block.kind === 'example') {
            return <ExampleBlock key={block.id} content={block.content} />
          }
          return (
            // Capped narrower than the page itself — the page uses more of a
            // wide screen, but a line of prose still shouldn't stretch to
            // an unreadable line length just because there's room.
            <p
              key={block.id}
              data-prose-block
              className="max-w-[760px] text-lg leading-relaxed text-ink-muted"
            >
              <RichText text={block.content} />
            </p>
          )
        })}
      </div>

      {selection && (
        <AIPanel
          lessonId={lesson.id}
          selectedText={selection.text}
          anchorRect={selection.rect}
          onClose={() => setSelection(null)}
        />
      )}
    </div>
  )
}
