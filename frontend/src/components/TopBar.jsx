function HamburgerIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="4" y1="7" x2="20" y2="7" strokeLinecap="round" />
      <line x1="4" y1="12" x2="20" y2="12" strokeLinecap="round" />
      <line x1="4" y1="17" x2="20" y2="17" strokeLinecap="round" />
    </svg>
  )
}

/** Persistent app chrome, full-bleed edge to edge: hamburger + wordmark at
 * the far left, avatar at the far right, each just a small padding in from
 * the viewport edge. `initial` is optional so the bar can render before user
 * data has loaded — the avatar just doesn't show until there's one to put in it. */
export default function TopBar({ initial }) {
  return (
    <header className="flex w-full items-center justify-between px-6 py-5">
      <div className="flex items-center gap-4">
        <button
          type="button"
          aria-label="Menu"
          className="text-green transition-opacity hover:opacity-70"
        >
          <HamburgerIcon />
        </button>
        <span className="font-serif text-lg font-semibold text-ink">LockedIn</span>
      </div>
      {initial && (
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-green-bg font-sans text-sm font-semibold text-[#2F5A44]">
          {initial}
        </div>
      )}
    </header>
  )
}
