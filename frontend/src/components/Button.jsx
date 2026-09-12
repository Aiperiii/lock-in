const VARIANT_CLASSES = {
  primary: 'bg-green text-white hover:bg-green/90',
  secondary: 'border border-border bg-card text-ink hover:bg-cream',
}

/** Sans, sentence case (per CLAUDE.md — callers own the label text). No
 * shadows, no gradients; `type="button"` by default so it's safe to drop
 * inside a form without triggering an accidental submit. */
export default function Button({ variant = 'primary', className = '', children, ...props }) {
  const variantClasses = VARIANT_CLASSES[variant] ?? VARIANT_CLASSES.primary
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center rounded-lg px-4 py-2 font-sans text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 ${variantClasses} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
