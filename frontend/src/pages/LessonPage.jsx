import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { answerQuestion, getLesson } from '../api/client'
import Button from '../components/Button'
import Card from '../components/Card'
import MonoLabel from '../components/MonoLabel'

function ArrowLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="19" y1="12" x2="5" y2="12" strokeLinecap="round" />
      <polyline points="12 19 5 12 12 5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

/** MCQ's result strip: grading is deterministic, so a plain correct/not-quite
 * label plus the reference explanation is the right amount of directness. */
function AttemptResult({ isCorrect, feedback, explanation }) {
  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className={`font-sans text-sm font-medium ${isCorrect ? 'text-green' : 'text-amber-text'}`}>
        {isCorrect ? 'Correct' : 'Not quite'}
      </p>
      {feedback && <p className="mt-1 text-ink-muted">{feedback}</p>}
      {explanation && <p className="mt-1 text-ink-muted">{explanation}</p>}
    </div>
  )
}

/** Open response's result strip: grading is a judgment call, not a lookup, so
 * a wrong attempt never says "incorrect" — just the AI's own conversational
 * feedback (which per docs/PROMPTS.md already names what they got right
 * before what they missed) and a quiet attempt count. Retries aren't capped,
 * so there's no "attempts remaining" framing, just a running tally. */
function OpenAttemptResult({ isCorrect, feedback, attemptCount }) {
  return (
    <div className="mt-4 border-t border-border pt-4">
      {isCorrect && <p className="font-sans text-sm font-medium text-green">Correct</p>}
      {feedback && <p className={isCorrect ? 'mt-1 text-ink-muted' : 'text-ink-muted'}>{feedback}</p>}
      <MonoLabel tone="faint" className="mt-2 block">
        Attempt {attemptCount}
      </MonoLabel>
    </div>
  )
}

function McqQuestion({ question }) {
  const [attempt, setAttempt] = useState(question.user_attempt)
  const [correctIndex, setCorrectIndex] = useState(question.correct_index)
  const [explanation, setExplanation] = useState(question.explanation)
  const [selected, setSelected] = useState(
    question.user_attempt ? Number(question.user_attempt.answer) : null,
  )
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Never re-answerable once right; a wrong attempt can always be retried.
  const locked = attempt?.is_correct === true

  async function handleSubmit() {
    if (selected === null || submitting || locked) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await answerQuestion(question.id, String(selected))
      setAttempt({ answer: String(selected), is_correct: result.is_correct })
      setCorrectIndex(result.correct_index)
      setExplanation(result.explanation)
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <MonoLabel tone="indigo">MCQ</MonoLabel>
      <p className="mt-2 text-ink">{question.prompt}</p>

      <div className="mt-4 flex flex-col gap-2">
        {question.options.map((option, index) => {
          const isCorrectOption = correctIndex !== null && correctIndex !== undefined && index === correctIndex
          const isWrongSelected = attempt && !attempt.is_correct && index === selected && !isCorrectOption
          return (
            <label
              key={option}
              className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition-colors ${
                isCorrectOption
                  ? 'border-green bg-green-bg'
                  : isWrongSelected
                    ? 'border-amber-text bg-amber-bg'
                    : 'border-border'
              } ${locked ? '' : 'cursor-pointer hover:border-ink-faint'}`}
            >
              <input
                type="radio"
                name={question.id}
                className="accent-green"
                checked={selected === index}
                disabled={locked || submitting}
                onChange={() => setSelected(index)}
              />
              <span className="text-ink">{option}</span>
            </label>
          )
        })}
      </div>

      {!locked && (
        <Button variant="primary" className="mt-4" onClick={handleSubmit} disabled={selected === null || submitting}>
          {attempt ? 'Try again' : 'Submit'}
        </Button>
      )}

      {attempt && <AttemptResult isCorrect={attempt.is_correct} explanation={explanation} />}
      {error && <p className="mt-2 text-ink-muted">Couldn't submit that — try again.</p>}
    </Card>
  )
}

function OpenQuestion({ question }) {
  const [attempt, setAttempt] = useState(question.user_attempt)
  const [text, setText] = useState(question.user_attempt?.answer ?? '')
  const [attemptCount, setAttemptCount] = useState(question.user_attempt?.attempt_number ?? 0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Never re-answerable once right; a wrong attempt is always retriable, with
  // no limit on how many times.
  const locked = attempt?.is_correct === true

  async function handleSubmit() {
    const trimmed = text.trim()
    if (!trimmed || submitting || locked) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await answerQuestion(question.id, trimmed)
      setAttempt({ answer: trimmed, is_correct: result.is_correct, feedback: result.feedback })
      setAttemptCount(result.attempt_number)
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <MonoLabel tone="orange">Open response</MonoLabel>
      <p className="mt-2 text-ink">{question.prompt}</p>
      {question.hint && <p className="mt-1 italic text-ink-muted">{question.hint}</p>}

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={locked || submitting}
        rows={4}
        placeholder="Type your answer…"
        className="mt-4 w-full rounded-lg border border-border bg-cream p-3 text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none disabled:opacity-70"
      />

      {!locked && (
        <Button variant="primary" className="mt-3" onClick={handleSubmit} disabled={!text.trim() || submitting}>
          {attempt ? 'Try again' : 'Submit'}
        </Button>
      )}

      {attempt && (
        <OpenAttemptResult isCorrect={attempt.is_correct} feedback={attempt.feedback} attemptCount={attemptCount} />
      )}
      {error && <p className="mt-2 text-ink-muted">Couldn't submit that — try again.</p>}
    </Card>
  )
}

function QuestionBlock({ question }) {
  return question.type === 'mcq' ? <McqQuestion question={question} /> : <OpenQuestion question={question} />
}

export default function LessonPage() {
  const { id } = useParams()
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState(null)

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

  if (error) {
    return <p className="mx-auto max-w-[680px] px-6 py-10 text-ink-muted">Couldn't load this lesson.</p>
  }
  if (!lesson) {
    return <p className="mx-auto max-w-[680px] px-6 py-10 text-ink-faint">Loading…</p>
  }

  return (
    <div className="mx-auto max-w-[680px] px-6 py-10">
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
        {lesson.blocks.map((block) =>
          block.kind === 'prose' ? (
            <p key={block.id} className="leading-relaxed text-ink-muted">
              {block.content}
            </p>
          ) : (
            <QuestionBlock key={block.id} question={block.question} />
          ),
        )}
      </div>
    </div>
  )
}
