const TONE_CLASSES = {
  mastered: 'bg-green-bg text-green',
  partial: 'bg-amber-bg text-amber-text',
  neutral: 'border border-border bg-cream text-ink-faint',
}

/** Small status fill — mastered (green), partial progress (amber), or a
 * plain neutral chip. Mono type, per CLAUDE.md's type rules. A quiet chip,
 * not a bright gamified badge: muted fills, small radius, no border glow. */
export default function Badge({ tone = 'neutral', className = '', children, ...props }) {
  const toneClasses = TONE_CLASSES[tone] ?? TONE_CLASSES.neutral
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 font-mono text-sm ${toneClasses} ${className}`}
      {...props}
    >
      {children}
    </span>
  )
}
