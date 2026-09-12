/** White surface, 12px radius, 1px hairline border. No shadow — per
 * CLAUDE.md's design rules, this app never uses drop shadows. */
export default function Card({ className = '', children, ...props }) {
  return (
    <div className={`rounded-xl border border-border bg-card p-6 ${className}`} {...props}>
      {children}
    </div>
  )
}
