import { useEffect, useRef, useState } from 'react'
import { askAI } from '../api/client'
import Button from './Button'
import RichText from './RichText'
import MonoLabel from './MonoLabel'

// Shortcut buttons prefill the user message — they're ordinary messages with
// canned text, no special casing on either side (docs/PROMPTS.md section 7).
const SHORTCUTS = [
  { label: 'Deep dive', message: 'Explain this in more depth, including why it matters.' },
  {
    label: 'Practice questions',
    message: 'Give me 2 practice questions on this, with answers hidden until I ask.',
  },
  { label: 'More examples', message: 'Give me two concrete examples of this.' },
]

const DEFAULT_WIDTH = 460
const DEFAULT_HEIGHT = 560
const MIN_WIDTH = 320
const MIN_HEIGHT = 280
// However tall the selection is, clear it by this much — a one-line
// selection and a three-line one both need the panel to start clear of it.
const ANCHOR_GAP = 20

function DragHandleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
      <circle cx="8" cy="6" r="1.4" />
      <circle cx="8" cy="12" r="1.4" />
      <circle cx="8" cy="18" r="1.4" />
      <circle cx="16" cy="6" r="1.4" />
      <circle cx="16" cy="12" r="1.4" />
      <circle cx="16" cy="18" r="1.4" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="6" y1="6" x2="18" y2="18" strokeLinecap="round" />
      <line x1="18" y1="6" x2="6" y2="18" strokeLinecap="round" />
    </svg>
  )
}

function ChevronIcon({ expanded }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`h-3.5 w-3.5 shrink-0 text-ink-faint transition-transform ${expanded ? 'rotate-180' : ''}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <polyline points="6 9 12 15 18 9" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

/** A flat [user, assistant, user, assistant, ...] thread grouped into Q/A
 * pairs for collapsing. The last pair's `assistant` is null while a reply is
 * still in flight — that pair is never collapsible until it has an answer. */
function pairsOf(thread) {
  const pairs = []
  for (let i = 0; i < thread.length; i += 2) {
    pairs.push({ user: thread[i], assistant: thread[i + 1] ?? null })
  }
  return pairs
}

/** Floating panel anchored near a text selection inside a lesson's prose
 * (see the selection-tracking effect in LessonPage.jsx). One AIConversation
 * per selection — conversation_id starts null and is reused for every
 * follow-up in the same open panel, per docs/API.md.
 *
 * Positioned below the selection with a clearing gap so it never starts
 * out covering the text the student just highlighted; from there it's fully
 * draggable (via the header) and resizable (native CSS resize, bottom-right
 * corner) in case it still ends up over something else on the page. */
export default function AIPanel({ lessonId, selectedText, anchorRect, onClose }) {
  const panelRef = useRef(null)
  const dragRef = useRef(null) // {startX, startY, originTop, originLeft} while dragging

  const [position, setPosition] = useState(() => initialPosition(anchorRect))
  const [conversationId, setConversationId] = useState(null)
  const [thread, setThread] = useState([]) // [{role: 'user'|'assistant', content}]
  const [collapsed, setCollapsed] = useState(() => new Set()) // pair indices
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    function onMouseDown(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('mousedown', onMouseDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('mousedown', onMouseDown)
    }
  }, [onClose])

  useEffect(() => {
    function onMouseMove(e) {
      const drag = dragRef.current
      if (!drag) return
      setPosition({
        top: clamp(drag.originTop + (e.clientY - drag.startY), 8, window.innerHeight - 40),
        left: clamp(drag.originLeft + (e.clientX - drag.startX), 8, window.innerWidth - 40),
      })
    }
    function onMouseUp() {
      dragRef.current = null
    }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    return () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  function startDrag(e) {
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      originTop: position.top,
      originLeft: position.left,
    }
  }

  async function send(message) {
    const trimmed = message.trim()
    if (!trimmed || sending) return
    setSending(true)
    setError(null)
    setInput('')
    setThread((prev) => [...prev, { role: 'user', content: trimmed }])
    try {
      const result = await askAI({ lessonId, selectedText, message: trimmed, conversationId })
      setConversationId(result.conversation_id)
      setThread((prev) => [...prev, { role: 'assistant', content: result.reply }])
    } catch (err) {
      setError(err)
      // Drop the optimistic turn so a retry doesn't leave a duplicate behind.
      setThread((prev) => prev.slice(0, -1))
    } finally {
      setSending(false)
    }
  }

  function toggle(pairIndex) {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(pairIndex)) next.delete(pairIndex)
      else next.add(pairIndex)
      return next
    })
  }

  const pairs = pairsOf(thread)

  return (
    <div
      ref={(el) => {
        panelRef.current = el
        // Set once, imperatively, so a later re-render (every new message)
        // never stomps a size the user dragged the resize handle to.
        if (el && !el.style.width) {
          el.style.width = `${DEFAULT_WIDTH}px`
          el.style.height = `${DEFAULT_HEIGHT}px`
        }
      }}
      style={{
        top: position.top,
        left: position.left,
        minWidth: MIN_WIDTH,
        minHeight: MIN_HEIGHT,
      }}
      className="fixed z-50 flex resize overflow-auto rounded-xl border border-border bg-card p-4"
    >
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div
          onMouseDown={startDrag}
          className="-mx-4 -mt-4 mb-3 flex shrink-0 cursor-move items-center justify-between rounded-t-xl border-b border-border bg-cream px-4 py-2"
        >
          <span className="text-ink-faint">
            <DragHandleIcon />
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-ink-faint transition-colors hover:text-ink-muted"
          >
            <CloseIcon />
          </button>
        </div>

        <blockquote className="shrink-0 border-l-2 border-border pl-3 text-sm italic text-ink-muted">
          "{selectedText}"
        </blockquote>

        {pairs.length > 0 && (
          <div className="mt-3 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
            {pairs.map((pair, i) => {
              const isCollapsed = collapsed.has(i) && pair.assistant
              return (
                <div key={i} className={i > 0 ? 'border-t border-border pt-3' : ''}>
                  <button
                    type="button"
                    onClick={() => pair.assistant && toggle(i)}
                    className="flex w-full items-start gap-2 text-left disabled:cursor-default"
                    disabled={!pair.assistant}
                  >
                    <div className="min-w-0 flex-1">
                      <MonoLabel tone="faint">You</MonoLabel>
                      <p className="mt-0.5 text-sm text-ink">
                        <RichText text={pair.user.content} />
                      </p>
                    </div>
                    {pair.assistant && <ChevronIcon expanded={!isCollapsed} />}
                  </button>
                  {!isCollapsed && (
                    <div className="mt-2">
                      <MonoLabel tone="faint">AI</MonoLabel>
                      {pair.assistant ? (
                        <p className="mt-0.5 text-sm text-ink-muted">
                          <RichText text={pair.assistant.content} />
                        </p>
                      ) : (
                        <p className="mt-0.5 text-sm text-ink-faint">Thinking…</p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {thread.length === 0 && (
          <div className="mt-3 flex shrink-0 flex-wrap gap-2">
            {SHORTCUTS.map((shortcut) => (
              <button
                key={shortcut.label}
                type="button"
                onClick={() => send(shortcut.message)}
                disabled={sending}
                className="rounded-full border border-border px-3 py-1 font-mono text-xs text-ink-muted transition-colors hover:border-ink-faint hover:text-ink disabled:pointer-events-none disabled:opacity-50"
              >
                {shortcut.label}
              </button>
            ))}
          </div>
        )}

        {error && <p className="mt-2 shrink-0 text-sm text-ink-muted">Couldn't reach the AI — try again.</p>}

        <form
          className="mt-3 flex shrink-0 items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
            placeholder="Ask a follow-up…"
            className="min-w-0 flex-1 rounded-lg border border-border bg-cream px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none disabled:opacity-70"
          />
          <Button variant="primary" type="submit" disabled={!input.trim() || sending}>
            Send
          </Button>
        </form>
      </div>
    </div>
  )
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), Math.max(min, max))
}

/** Below the selection with a clearing gap, kept on-screen on every side —
 * a selection near the right or bottom edge must not push the panel (fixed
 * at DEFAULT_WIDTH x DEFAULT_HEIGHT) off the viewport. */
function initialPosition(anchorRect) {
  if (!anchorRect) return { top: 80, left: 80 }
  const top = clamp(anchorRect.bottom + ANCHOR_GAP, 8, window.innerHeight - DEFAULT_HEIGHT - 8)
  const left = clamp(anchorRect.left, 8, window.innerWidth - DEFAULT_WIDTH - 8)
  return { top, left }
}
