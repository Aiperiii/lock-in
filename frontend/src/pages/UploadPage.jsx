import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { getBook, getBookStatus, uploadBook } from '../api/client'
import Button from '../components/Button'
import MonoLabel from '../components/MonoLabel'

const POLL_INTERVAL_MS = 2000

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M12 16V4M12 4L7 9M12 4l5 5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
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

function DropZone({ onFile, error }) {
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef(null)

  function handleFiles(fileList) {
    const file = fileList?.[0]
    if (!file) return
    onFile(file)
    // Reset so selecting the same file again (e.g. after an error) still fires onChange.
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragActive(true)
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragActive(false)
          handleFiles(e.dataTransfer.files)
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-16 text-center transition-colors ${
          dragActive ? 'border-green bg-green-bg' : 'border-border hover:border-ink-faint'
        }`}
      >
        <UploadIcon />
        <p className="text-ink">Drop a PDF here, or click to browse</p>
        <MonoLabel tone="faint">PDF only</MonoLabel>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {error && <p className="mt-3 text-amber-text">{error}</p>}
    </div>
  )
}

/** The live processing view — book title once known, chapters appearing one
 * by one as chapters_done grows, current stage text throughout. Never a bare
 * spinner: there's always descriptive text, and a small pulse next to it
 * signals ongoing activity rather than standing in for the whole state. */
function ProcessingView({ book, status }) {
  return (
    <div>
      {book?.title ? (
        <h2 className="font-serif text-2xl text-ink">{book.title}</h2>
      ) : (
        <p className="text-ink-faint">Reading your PDF…</p>
      )}

      {status?.stage && (
        <div className="mt-2 flex items-center gap-2">
          <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-green" />
          <MonoLabel tone="faint">{status.stage}</MonoLabel>
        </div>
      )}

      {book?.chapters?.length > 0 && (
        <ul className="mt-6 flex flex-col gap-2">
          {book.chapters.map((chapter) => (
            <li key={chapter.id} className="flex items-center gap-3">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green text-white">
                <CheckIcon />
              </span>
              <span className="text-ink-muted">{chapter.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function UploadPage() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState('idle') // idle | uploading | processing | failed
  const [error, setError] = useState(null)
  const [bookId, setBookId] = useState(null)
  const [status, setStatus] = useState(null)
  const [book, setBook] = useState(null)

  async function handleFile(file) {
    const looksLikePdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    if (!looksLikePdf) {
      setError('Only PDF files are supported.')
      return
    }
    setError(null)
    setPhase('uploading')
    try {
      const result = await uploadBook(file)
      setBookId(result.book_id)
      setPhase('processing')
    } catch (err) {
      setError(err.message || "Couldn't upload that file — try again.")
      setPhase('idle')
    }
  }

  function reset() {
    setPhase('idle')
    setError(null)
    setBookId(null)
    setStatus(null)
    setBook(null)
  }

  useEffect(() => {
    if (phase !== 'processing' || !bookId) return
    let cancelled = false

    async function poll() {
      try {
        const [statusData, bookData] = await Promise.all([getBookStatus(bookId), getBook(bookId)])
        if (cancelled) return
        setStatus(statusData)
        setBook(bookData)
        if (statusData.status === 'ready') {
          navigate(`/books/${bookId}`)
        } else if (statusData.status === 'failed') {
          setPhase('failed')
        }
      } catch {
        // A transient network hiccup mid-poll isn't fatal — the next tick retries.
      }
    }

    poll()
    const interval = setInterval(poll, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [phase, bookId, navigate])

  return (
    <div className="mx-auto max-w-[680px] px-6 py-16">
      <h1 className="mb-8 font-serif text-3xl text-ink">Add a book</h1>

      {(phase === 'idle' || phase === 'uploading') && (
        <>
          <DropZone onFile={handleFile} error={error} />
          {phase === 'uploading' && <p className="mt-4 text-ink-faint">Uploading…</p>}
        </>
      )}

      {phase === 'processing' && <ProcessingView book={book} status={status} />}

      {phase === 'failed' && (
        <div>
          <p className="text-amber-text">{status?.stage ?? 'Something went wrong while processing that PDF.'}</p>
          <Button variant="secondary" className="mt-4" onClick={reset}>
            Try another file
          </Button>
        </div>
      )}
    </div>
  )
}
