import katex from 'katex'
import { useMemo } from 'react'

// $$...$$ (display) or $...$ (inline) — the delimiters the block-generation
// and quiz-generation prompts are told to use for notation (docs/PROMPTS.md
// sections 3 and 6: "Preserve notation, formulas, and examples from the
// source"). Inline math can't contain a newline, so a stray unpaired "$"
// (e.g. someone typing a dollar amount in the AI panel) doesn't swallow the
// rest of the paragraph looking for a closer.
const MATH_PATTERN = /\$\$([^$]+)\$\$|\$([^$\n]+)\$/g

// **bold** / *italic* — the only two spans docs/PROMPTS.md section 3 asks
// the block-generation prompt to produce, used sparingly (a key term the
// first time it's defined; a technical term used descriptively). No nested
// or multi-line spans: prose blocks are 2-4 sentences, and requiring a
// non-space on each inner edge keeps a stray "*" (bare multiplication, an
// unmatched asterisk) from being swallowed as an emphasis marker.
const BOLD_PATTERN = /\*\*(\S(?:[^*]*\S)?)\*\*/g
const ITALIC_PATTERN = /\*(\S(?:[^*]*\S)?)\*/g

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderTex(tex, displayMode) {
  try {
    return katex.renderToString(tex.trim(), { throwOnError: false, displayMode })
  } catch {
    // Never let a malformed equation take the whole block down with it —
    // fall back to the literal source, escaped like any other text.
    return escapeHtml(displayMode ? `$$${tex}$$` : `$${tex}$`)
  }
}

/** Bold/italic only — applied to the plain-text segments between math spans,
 * never to what's inside one (LaTeX has its own meaning for "*"). */
function renderEmphasis(text) {
  return escapeHtml(text)
    .replace(BOLD_PATTERN, '<strong>$1</strong>')
    .replace(ITALIC_PATTERN, '<em>$1</em>')
}

/** Renders the light markdown the content model actually uses — $...$ /
 * $$...$$ math (via KaTeX) and bold/italic emphasis — leaving
 * everything else as plain escaped text. Used anywhere prose can carry
 * AI-generated notation or emphasis: lesson prose, question prompts and
 * options, and AI panel messages. Renders inline (a <span>) so it drops
 * into an existing <p> or button label; `block` centers a standalone
 * display equation on its own line instead of leaving it inline. */
export default function RichText({ text, className = '', block = false }) {
  const html = useMemo(() => {
    const source = text ?? ''
    let out = ''
    let last = 0
    MATH_PATTERN.lastIndex = 0
    let match
    while ((match = MATH_PATTERN.exec(source)) !== null) {
      out += renderEmphasis(source.slice(last, match.index))
      out += match[1] !== undefined ? renderTex(match[1], true) : renderTex(match[2], false)
      last = MATH_PATTERN.lastIndex
    }
    out += renderEmphasis(source.slice(last))
    return out
  }, [text])

  const Tag = block ? 'div' : 'span'
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />
}
