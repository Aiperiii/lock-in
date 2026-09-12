/** A circular progress ring showing a mastery percent. Uses the same
 * --color-green/--color-border tokens as ProgressBar (referenced directly as
 * CSS variables, since Tailwind v4 exposes theme colors that way), just in
 * ring form for the book-page hero. */
export default function MasteryRing({ percent, size = 76, strokeWidth = 6, className = '' }) {
  const clamped = Math.min(100, Math.max(0, percent))
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - clamped / 100)
  const center = size / 2

  return (
    <div
      className={`relative inline-flex shrink-0 items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={center} cy={center} r={radius} fill="none" stroke="var(--color-border)" strokeWidth={strokeWidth} />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--color-green)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="absolute font-sans text-sm font-semibold text-ink">{clamped}%</span>
    </div>
  )
}
