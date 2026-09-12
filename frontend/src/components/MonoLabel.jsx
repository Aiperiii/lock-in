const TONE_CLASSES = {
  faint: 'text-ink-faint',
  ink: 'text-ink',
  green: 'text-green',
  indigo: 'text-indigo',
  orange: 'text-orange',
}

/** Plain mono-font text for metadata lines, subject tags, and the MCQ/OPEN
 * RESPONSE question-type signals. Indigo and orange are reserved for that
 * question-type use only (CLAUDE.md) — never for buttons, links, or
 * decoration. Text is rendered as given; no forced casing, since sentence
 * case applies everywhere except book titles and callers own their copy. */
export default function MonoLabel({ tone = 'faint', className = '', children, ...props }) {
  const toneClasses = TONE_CLASSES[tone] ?? TONE_CLASSES.faint
  return (
    <span className={`font-mono text-xs tracking-wide ${toneClasses} ${className}`} {...props}>
      {children}
    </span>
  )
}
