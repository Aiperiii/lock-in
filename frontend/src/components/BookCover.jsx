import { useId, useMemo } from 'react'

// docs/SCHEMA.md: "cover_seed drives generated cover pattern + palette" — both
// the palette AND the geometric motif (plus its scale/rotation) come from the
// same integer, so covers stay visually varied without any images.
const PALETTES = [
  { name: 'sage', bg: '#E6EEE3', motif: '#8FAE87' },
  { name: 'lavender', bg: '#EAE6F4', motif: '#A79BCE' },
  { name: 'powder-blue', bg: '#E3EDF5', motif: '#87ADCB' },
  { name: 'warm-sand', bg: '#F5EEE0', motif: '#CBA97B' },
]

const MOTIFS = ['dots', 'stripes', 'plus', 'arcs']

/** Deterministic PRNG (mulberry32) so a given cover_seed always produces the
 * same sequence of derived values — same book, same cover, every reload. */
function mulberry32(seed) {
  let t = seed >>> 0
  return function next() {
    t = (t + 0x6d2b79f5) | 0
    let x = t
    x = Math.imul(x ^ (x >>> 15), x | 1)
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61)
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296
  }
}

function deriveCover(coverSeed) {
  const rng = mulberry32(coverSeed)
  const palette = PALETTES[Math.floor(rng() * PALETTES.length)]
  const motif = MOTIFS[Math.floor(rng() * MOTIFS.length)]
  const scale = 20 + Math.floor(rng() * 16) // tile size, 20-36px
  const rotation = Math.floor(rng() * 60) - 30 // -30..30 degrees
  return { palette, motif, scale, rotation }
}

function MotifShape({ motif, scale, color }) {
  const stroke = scale * 0.08
  switch (motif) {
    case 'dots':
      return <circle cx={scale / 2} cy={scale / 2} r={scale * 0.12} fill={color} />
    case 'stripes':
      return <rect x={0} y={scale * 0.42} width={scale} height={scale * 0.16} fill={color} />
    case 'plus':
      return (
        <g stroke={color} strokeWidth={stroke} strokeLinecap="round">
          <line x1={scale / 2} y1={scale * 0.2} x2={scale / 2} y2={scale * 0.8} />
          <line x1={scale * 0.2} y1={scale / 2} x2={scale * 0.8} y2={scale / 2} />
        </g>
      )
    case 'arcs':
      return (
        <path
          d={`M 0 ${scale} A ${scale} ${scale} 0 0 1 ${scale} 0`}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
        />
      )
    default:
      return null
  }
}

/** A generated book cover: a pastel tint plus a repeating geometric motif,
 * both deterministic from `coverSeed`, with title/author overlaid in serif.
 * No images — the motif is an inline SVG pattern. */
export default function BookCover({ coverSeed, title, author, className = '' }) {
  const { palette, motif, scale, rotation } = useMemo(() => deriveCover(coverSeed), [coverSeed])
  const patternId = `cover-motif-${useId().replace(/[^a-zA-Z0-9]/g, '')}`

  return (
    <div
      className={`relative aspect-[3/4] w-full overflow-hidden rounded-lg border border-border @container ${className}`}
      style={{ backgroundColor: palette.bg }}
    >
      <svg className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <pattern
            id={patternId}
            width={scale}
            height={scale}
            patternUnits="userSpaceOnUse"
            patternTransform={`rotate(${rotation})`}
          >
            <MotifShape motif={motif} scale={scale} color={palette.motif} />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#${patternId})`} opacity="0.55" />
      </svg>

      {/* Font sizes are container-query units (cqw), not fixed, so a title
          scales down on a small grid thumbnail and doesn't blow up on a
          large one — BookCover renders at very different widths depending
          on where it's used. overflow-hidden (above) plus line-clamp is the
          backstop for anything still too long to fit even shrunk. */}
      <div className="relative flex h-full flex-col justify-end gap-1 overflow-hidden p-4">
        <p className="line-clamp-2 font-serif leading-snug text-ink text-[clamp(0.7rem,8cqw,1.125rem)]">
          {title}
        </p>
        {author && (
          <p className="line-clamp-1 font-serif text-ink-muted text-[clamp(0.55rem,5cqw,0.8rem)]">
            {author}
          </p>
        )}
      </div>
    </div>
  )
}
