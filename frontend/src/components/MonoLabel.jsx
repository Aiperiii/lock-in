const TONE_CLASSES = {
  faint: 'text-ink-faint',
  ink: 'text-ink',
  green: 'text-green',
  indigo: 'text-indigo',
  orange: 'text-orange',
}

const SIZE_CLASSES = {
  xs: 'text-xs',
  sm: 'text-sm',
}

/** Plain mono-font text for metadata lines, subject tags, and the MCQ/OPEN
 * RESPONSE question-type signals. Indigo and orange are reserved for that
 * question-type use only (CLAUDE.md) — never for buttons, links, or
 * decoration. Text is rendered as given; no forced casing, since sentence
 * case applies everywhere except book titles and callers own their copy.
 * `size` defaults to the usual tiny metadata size; 'sm' is for the rarer
 * case a mono label needs to actually be legible as a standalone heading. */
export default function MonoLabel({ tone = 'faint', size = 'xs', className = '', children, ...props }) {
  const toneClasses = TONE_CLASSES[tone] ?? TONE_CLASSES.faint
  const sizeClasses = SIZE_CLASSES[size] ?? SIZE_CLASSES.xs
  return (
    <span className={`font-mono tracking-wide ${sizeClasses} ${toneClasses} ${className}`} {...props}>
      {children}
    </span>
  )
}
