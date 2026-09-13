import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { getQuiz } from '../api/client'
import MonoLabel from '../components/MonoLabel'
import QuestionBlock from '../components/QuestionCard'

function ArrowLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="19" y1="12" x2="5" y2="12" strokeLinecap="round" />
      <polyline points="12 19 5 12 12 5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

/** A quiz's questions answer exactly like a lesson's — same QuestionBlock,
 * same POST /api/questions/{id}/answer per question — just without lesson
 * prose in between and with a quiz-scoped header instead of a lesson one. */
export default function QuizPage() {
  const { id } = useParams()
  const [quiz, setQuiz] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setQuiz(null)
    setError(null)
    getQuiz(id)
      .then((data) => {
        if (!cancelled) setQuiz(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) {
    return <p className="mx-auto max-w-[1100px] px-6 py-10 text-ink-muted">Couldn't load this quiz.</p>
  }
  if (!quiz) {
    return <p className="mx-auto max-w-[1100px] px-6 py-10 text-ink-faint">Loading…</p>
  }

  return (
    <div className="mx-auto max-w-[1100px] px-6 py-10">
      <Link
        to={`/books/${quiz.book_id}`}
        className="flex items-center gap-1.5 font-mono text-xs text-ink-faint transition-colors hover:text-ink-muted"
      >
        <ArrowLeftIcon />
        Back to book
      </Link>

      <MonoLabel tone="faint" className="mt-4 block">
        {quiz.questions.length} question{quiz.questions.length === 1 ? '' : 's'} · {quiz.difficulty}
      </MonoLabel>
      <h1 className="mt-2 mb-8 font-serif text-3xl text-ink">Quiz</h1>

      <div className="flex flex-col gap-6">
        {quiz.questions.map((question) => (
          <QuestionBlock key={question.id} question={question} />
        ))}
      </div>
    </div>
  )
}
