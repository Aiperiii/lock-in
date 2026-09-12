/** Thin green fill on a hairline-colored track — the app's one progress
 * indicator, used for book/lesson mastery. `value` is a 0-100 percent. */
export default function ProgressBar({ value = 0, className = '', ...props }) {
  const clamped = Math.min(100, Math.max(0, value))
  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={`h-1.5 w-full overflow-hidden rounded-full bg-border ${className}`}
      {...props}
    >
      <div className="h-full rounded-full bg-green transition-[width]" style={{ width: `${clamped}%` }} />
    </div>
  )
}
