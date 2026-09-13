import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { generateQuiz } from '../api/client'
import Badge from './Badge'
import Button from './Button'
import Card from './Card'
import MonoLabel from './MonoLabel'

// No "mixed" — picking a difficulty means every question in the quiz should
// land at roughly that level, not a blend across the set.
const DIFFICULTIES = ['easy', 'medium', 'hard']

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="6" y1="6" x2="18" y2="18" strokeLinecap="round" />
      <line x1="18" y1="6" x2="6" y2="18" strokeLinecap="round" />
    </svg>
  )
}

/** The manual generate-quiz flow (docs/API.md POST /api/quizzes/generate):
 * pick chapters, difficulty and a question count, generate, then go straight
 * to /quizzes/{id} — same destination the automatic end-of-chapter/course
 * rows link to (BookPage.jsx), since it's the same generate_quiz() call
 * either way. */
export default function QuizModal({ book, onClose }) {
  const navigate = useNavigate()
  const [selectedIds, setSelectedIds] = useState(() => new Set(book.chapters.map((c) => c.id)))
  const [difficulty, setDifficulty] = useState('medium')
  const [count, setCount] = useState(10)
  const [status, setStatus] = useState('idle') // idle | loading | error
  const [error, setError] = useState(null)

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  function toggleChapter(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleGenerate() {
    setStatus('loading')
    setError(null)
    try {
      const quiz = await generateQuiz({
        bookId: book.id,
        chapterIds: [...selectedIds],
        difficulty,
        count: Number(count) || 10,
      })
      navigate(`/quizzes/${quiz.id}`)
    } catch (err) {
      setError(err)
      setStatus('error')
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      onClick={onClose}
    >
      <Card className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="font-serif text-xl text-ink">Generate quiz</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-ink-faint transition-colors hover:text-ink-muted"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="mt-5 flex flex-col gap-5">
          <div>
            <MonoLabel tone="faint">Chapters</MonoLabel>
            <div className="mt-2 flex flex-col gap-2">
              {book.chapters.map((chapter) => (
                <label key={chapter.id} className="flex items-center gap-2 text-ink">
                  <input
                    type="checkbox"
                    className="accent-green"
                    checked={selectedIds.has(chapter.id)}
                    onChange={() => toggleChapter(chapter.id)}
                  />
                  {chapter.title}
                </label>
              ))}
            </div>
          </div>

          <div className="flex gap-4">
            <label className="flex-1">
              <MonoLabel tone="faint">Difficulty</MonoLabel>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                className="mt-2 w-full rounded-lg border border-border bg-cream px-3 py-2 text-ink focus:border-ink-faint focus:outline-none"
              >
                {DIFFICULTIES.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <label className="w-28">
              <MonoLabel tone="faint">Number of questions</MonoLabel>
              <input
                type="number"
                min={1}
                max={30}
                value={count}
                onChange={(e) => setCount(e.target.value)}
                className="mt-2 w-full rounded-lg border border-border bg-cream px-3 py-2 text-ink focus:border-ink-faint focus:outline-none"
              />
            </label>
          </div>

          {status === 'error' && (
            <p className="text-sm text-ink-muted">
              Couldn't generate that quiz{error?.message ? `: ${error.message}` : '.'} Try again.
            </p>
          )}

          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              onClick={handleGenerate}
              disabled={selectedIds.size === 0 || status === 'loading'}
            >
              {status === 'loading' ? 'Generating…' : 'Generate'}
            </Button>
            {status === 'loading' && <Badge tone="neutral">This can take a moment</Badge>}
          </div>
        </div>
      </Card>
    </div>
  )
}
