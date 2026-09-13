import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { getBooks, getHome } from '../api/client'
import BookCover from '../components/BookCover'
import Button from '../components/Button'
import Card from '../components/Card'
import HeroBackground from '../components/HeroBackground'
import MonoLabel from '../components/MonoLabel'
import ProgressBar from '../components/ProgressBar'
import TopBar from '../components/TopBar'

function timeOfDayGreeting(hour = new Date().getHours()) {
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="12" y1="5" x2="12" y2="19" strokeLinecap="round" />
      <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round" />
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

export default function LibraryPage() {
  const [home, setHome] = useState(null)
  const [books, setBooks] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([getHome(), getBooks()])
      .then(([homeData, booksData]) => {
        if (cancelled) return
        setHome(homeData)
        setBooks(booksData)
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const loaded = home && books
  const continueBook = home?.continue

  return (
    <div>
      <TopBar initial={home?.greeting_name?.[0]} />

      {error && (
        <p className="mx-auto max-w-[1400px] px-6 py-10 text-ink-muted">
          Couldn't load your library. Is the backend running?
        </p>
      )}
      {!error && !loaded && <p className="mx-auto max-w-[1400px] px-6 py-10 text-ink-faint">Loading…</p>}

      {!error && loaded && (
        <>
          {/* Hero: full-bleed background behind the greeting + continue card
              only — it ends here, the library section below has none. */}
          <section className="relative overflow-hidden">
            <HeroBackground />
            <div className="relative mx-auto max-w-[1400px] px-6 pt-10 pb-12">
              <h1 className="mb-10 font-serif text-3xl text-ink">
                {timeOfDayGreeting()}, {home.greeting_name}
              </h1>

              {continueBook && (
                <Card className="flex flex-col gap-6 p-8 sm:min-h-56 sm:flex-row sm:items-center sm:gap-8">
                  <div className="w-32 shrink-0 sm:w-36">
                    <BookCover
                      coverSeed={continueBook.cover_seed}
                      title={continueBook.title}
                      author={continueBook.author}
                      size="sm"
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <MonoLabel tone="faint" size="sm">
                      Continue reading
                    </MonoLabel>
                    <h2 className="mt-1 truncate font-serif text-2xl text-ink">{continueBook.title}</h2>
                    <p className="truncate text-ink-muted">{continueBook.author}</p>
                    <ProgressBar value={continueBook.progress_percent} className="mt-4 max-w-xs" />
                  </div>
                  <Link to={`/books/${continueBook.book_id}`} className="shrink-0">
                    <Button variant="dark">
                      Continue
                      <ArrowIcon />
                    </Button>
                  </Link>
                </Card>
              )}
            </div>
          </section>

          <section className="mx-auto max-w-[1400px] px-6 pb-10">
            <h2 className="mb-4 font-mono text-sm uppercase tracking-wide text-ink-faint">Library</h2>
            <div className="grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-3 md:grid-cols-4">
              {books.map((book) => (
                <Link key={book.id} to={`/books/${book.id}`} className="min-w-0">
                  <BookCover coverSeed={book.cover_seed} title={book.title} author={book.author} />
                  <ProgressBar value={book.progress_percent} className="mt-2" />
                </Link>
              ))}
              <Link
                to="/upload"
                className="flex aspect-[3/4] w-full min-w-0 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border text-ink-muted transition-colors hover:border-ink-faint hover:text-ink"
              >
                <PlusIcon />
                <span className="font-mono text-xs">Add a book</span>
              </Link>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
