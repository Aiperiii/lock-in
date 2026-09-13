import { useRef, useState } from 'react'
import { answerQuestion } from '../api/client'
import Button from './Button'
import Card from './Card'
import RichText from './RichText'
import MonoLabel from './MonoLabel'

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

/** MCQ's result strip: grading is deterministic, so a plain correct/not-quite
 * label plus the reference explanation is the right amount of directness. */
function AttemptResult({ isCorrect, feedback, explanation }) {
  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className={`font-sans text-sm font-medium ${isCorrect ? 'text-green' : 'text-amber-text'}`}>
        {isCorrect ? 'Correct' : 'Not quite'}
      </p>
      {feedback && <p className="mt-1 text-ink-muted"><RichText text={feedback} /></p>}
      {explanation && <p className="mt-1 text-ink-muted"><RichText text={explanation} /></p>}
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
      {feedback && (
        <p className={isCorrect ? 'mt-1 text-ink-muted' : 'text-ink-muted'}>
          <RichText text={feedback} />
        </p>
      )}
      <MonoLabel tone="faint" className="mt-2 block">
        Attempt {attemptCount}
      </MonoLabel>
    </div>
  )
}

/** The tag + prompt, doubling as the collapse/expand toggle when the
 * question is collapsible (lesson page only — see QuestionBlock). Collapsed,
 * the prompt clamps to two lines so a long question doesn't defeat the
 * point of collapsing it. Not a button at all on the quiz page: quizzes
 * always show every question fully open, so there's nothing to toggle. */
function QuestionHeader({ tone, label, prompt, collapsible, expanded, onToggle }) {
  if (!collapsible) {
    return (
      <>
        <MonoLabel tone={tone}>{label}</MonoLabel>
        <p className="mt-2 text-lg text-ink">
          <RichText text={prompt} />
        </p>
      </>
    )
  }
  return (
    <button type="button" onClick={onToggle} className="flex w-full items-start gap-3 text-left">
      <div className="min-w-0 flex-1">
        <MonoLabel tone={tone}>{label}</MonoLabel>
        <p className={`mt-2 text-lg text-ink ${expanded ? '' : 'line-clamp-2'}`}>
          <RichText text={prompt} />
        </p>
      </div>
      <div className="shrink-0 pt-0.5">
        <ChevronIcon expanded={expanded} />
      </div>
    </button>
  )
}

function McqQuestion({ question, collapsible }) {
  const [attempt, setAttempt] = useState(question.user_attempt)
  const [correctIndex, setCorrectIndex] = useState(question.correct_index)
  const [explanation, setExplanation] = useState(question.explanation)
  const [selected, setSelected] = useState(
    question.user_attempt ? Number(question.user_attempt.answer) : null,
  )
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  // Collapsed by default (book-like reading flow); already-answered
  // questions start open showing their result, but can still be re-collapsed.
  const [expanded, setExpanded] = useState(!collapsible || Boolean(question.user_attempt))

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
      <QuestionHeader
        tone="indigo"
        label="MCQ"
        prompt={question.prompt}
        collapsible={collapsible}
        expanded={expanded}
        onToggle={() => setExpanded((e) => !e)}
      />

      {expanded && (
        <>
          <div className="mt-4 flex flex-col gap-2">
            {question.options.map((option, index) => {
              const isCorrectOption =
                correctIndex !== null && correctIndex !== undefined && index === correctIndex
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
                  <span className="text-lg text-ink">
                    <RichText text={option} />
                  </span>
                </label>
              )
            })}
          </div>

          {!locked && (
            <Button
              variant="primary"
              className="mt-4"
              onClick={handleSubmit}
              disabled={selected === null || submitting}
            >
              {attempt ? 'Try again' : 'Submit'}
            </Button>
          )}

          {attempt && <AttemptResult isCorrect={attempt.is_correct} explanation={explanation} />}
          {error && <p className="mt-2 text-ink-muted">Couldn't submit that — try again.</p>}
        </>
      )}
    </Card>
  )
}

function OpenQuestion({ question, collapsible }) {
  const [attempt, setAttempt] = useState(question.user_attempt)
  const [text, setText] = useState(question.user_attempt?.answer ?? '')
  const [attemptCount, setAttemptCount] = useState(question.user_attempt?.attempt_number ?? 0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(!collapsible || Boolean(question.user_attempt))

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
      <QuestionHeader
        tone="orange"
        label="Open response"
        prompt={question.prompt}
        collapsible={collapsible}
        expanded={expanded}
        onToggle={() => setExpanded((e) => !e)}
      />

      {expanded && (
        <>
          {question.hint && (
            <p className="mt-1 text-lg italic text-ink-muted">
              <RichText text={question.hint} />
            </p>
          )}

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={locked || submitting}
            rows={4}
            placeholder="Type your answer…"
            className="mt-4 w-full rounded-lg border border-border bg-cream p-3 text-lg text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none disabled:opacity-70"
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
        </>
      )}
    </Card>
  )
}

/** Click-to-pair matching: click a left chip to arm it (teal ring), then a
 * right chip to place it there — a right chip already claimed by another
 * left is freed automatically, so there's never a duplicate assignment to
 * untangle. No drag-and-drop; ids (not array position) track a pairing, so
 * the right column's per-fetch shuffle (app/progress._matching_fields)
 * never invalidates one already made. Grading is all-or-nothing (docs/API.md),
 * but the per-chip green/amber highlight after an attempt still shows which
 * specific pairs were right — any further click clears that feedback back to
 * the plain teal editing view rather than leave it stale against edited pairs. */
function MatchingQuestion({ question, collapsible }) {
  const [attempt, setAttempt] = useState(question.user_attempt)
  const [correctPairs, setCorrectPairs] = useState(question.correct_pairs)
  const [pairs, setPairs] = useState(question.user_attempt?.answer ?? {}) // {leftId: rightId}
  const [selectedLeft, setSelectedLeft] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(!collapsible || Boolean(question.user_attempt))

  // Mirrors `selectedLeft` for reading inside selectRight — two clicks
  // dispatched back to back (fast deliberate clicking, a double-tap, a
  // scripted/automated click) can land before React re-renders between
  // them, so the `selectedLeft` closed over at render time can be stale.
  // A ref updates synchronously and is exempt from StrictMode's
  // double-invocation of state updaters, unlike nesting this read inside
  // setSelectedLeft's own updater (tried first; StrictMode's deliberate
  // double-call of that updater in dev then double-fired the setPairs
  // side effect nested inside it, dropping pairs — updater functions must
  // stay pure, with no other setState calls inside them).
  const selectedLeftRef = useRef(null)

  const locked = attempt?.is_correct === true
  const allPaired = question.left_items.every((item) => pairs[item.id] !== undefined)

  function clearStaleFeedback() {
    if (attempt) {
      setAttempt(null)
      setCorrectPairs(null)
    }
  }

  function armLeft(leftId) {
    selectedLeftRef.current = leftId
    setSelectedLeft(leftId)
  }

  function selectLeft(leftId) {
    if (locked || submitting) return
    clearStaleFeedback()
    armLeft(selectedLeftRef.current === leftId ? null : leftId)
  }

  function selectRight(rightId) {
    if (locked || submitting) return
    const currentLeft = selectedLeftRef.current
    if (currentLeft === null) return
    clearStaleFeedback()
    setPairs((prev) => {
      const next = {}
      for (const [left, right] of Object.entries(prev)) {
        if (right !== rightId) next[left] = right
      }
      next[currentLeft] = rightId
      return next
    })
    armLeft(null)
  }

  async function handleSubmit() {
    if (!allPaired || submitting || locked) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await answerQuestion(question.id, pairs)
      setAttempt({ answer: pairs, is_correct: result.is_correct })
      setCorrectPairs(result.correct_pairs)
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  function leftIdFor(rightId) {
    return Object.keys(pairs).find((left) => pairs[left] === rightId) ?? null
  }

  return (
    <Card>
      <QuestionHeader
        tone="teal"
        label="Matching"
        prompt={question.prompt}
        collapsible={collapsible}
        expanded={expanded}
        onToggle={() => setExpanded((e) => !e)}
      />

      {expanded && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-2">
              {question.left_items.map((item) => {
                const isPaired = pairs[item.id] !== undefined
                const isSelected = selectedLeft === item.id
                const isCorrect = attempt && correctPairs && pairs[item.id] === correctPairs[item.id]
                const stateClasses = attempt
                  ? isCorrect
                    ? 'border-green bg-green-bg'
                    : 'border-amber-text bg-amber-bg'
                  : isSelected
                    ? 'border-teal'
                    : isPaired
                      ? 'border-teal bg-teal-bg'
                      : 'border-border hover:border-ink-faint'
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectLeft(item.id)}
                    disabled={locked || submitting}
                    className={`rounded-lg border px-3 py-2.5 text-left text-lg text-ink transition-colors ${stateClasses}`}
                  >
                    <RichText text={item.text} />
                  </button>
                )
              })}
            </div>
            <div className="flex flex-col gap-2">
              {question.right_items.map((item) => {
                const claimedBy = leftIdFor(item.id)
                const isCorrect = attempt && correctPairs && claimedBy && correctPairs[claimedBy] === item.id
                const stateClasses = attempt
                  ? claimedBy
                    ? isCorrect
                      ? 'border-green bg-green-bg'
                      : 'border-amber-text bg-amber-bg'
                    : 'border-border'
                  : claimedBy
                    ? 'border-teal bg-teal-bg'
                    : 'border-border hover:border-ink-faint'
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectRight(item.id)}
                    disabled={locked || submitting || selectedLeft === null}
                    className={`rounded-lg border px-3 py-2.5 text-left text-lg text-ink transition-colors ${stateClasses}`}
                  >
                    <RichText text={item.text} />
                  </button>
                )
              })}
            </div>
          </div>

          {!locked && (
            <Button variant="primary" className="mt-4" onClick={handleSubmit} disabled={!allPaired || submitting}>
              {attempt ? 'Try again' : 'Check answers'}
            </Button>
          )}

          {attempt && <AttemptResult isCorrect={attempt.is_correct} explanation={question.explanation} />}
          {error && <p className="mt-2 text-ink-muted">Couldn't submit that — try again.</p>}
        </>
      )}
    </Card>
  )
}

/** Shared by the lesson page and the quiz page — a question answers exactly
 * the same way whether it's reached from its lesson or from a quiz (same
 * backend write path, app/scoring.answer_question).
 *
 * `collapsible` makes it a book-like collapsed-by-default block (lesson
 * page only, per CLAUDE.md's reading-flow intent); the quiz page omits it
 * so every question there stays fully open, matching how a quiz is meant to
 * be taken as a single continuous set rather than revealed piece by piece. */
export default function QuestionBlock({ question, collapsible = false }) {
  if (question.type === 'mcq') {
    return <McqQuestion question={question} collapsible={collapsible} />
  }
  if (question.type === 'matching') {
    return <MatchingQuestion question={question} collapsible={collapsible} />
  }
  return <OpenQuestion question={question} collapsible={collapsible} />
}
