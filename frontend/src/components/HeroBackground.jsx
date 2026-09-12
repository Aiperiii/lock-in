// A soft, near-white backdrop suggesting light falling diagonally across an
// open book's pages: a few large, gently-curved, heavily-blurred bands in
// pale warm gray on a near-white ground — generated as an inline SVG data
// URI rather than a photo, so there's no external image or licensing to
// track, and the contrast stays reliably readable-behind-text by
// construction. (Since this only ever exists inside a CSS background-image,
// the filter id has no risk of colliding with anything else on the page.)
const SVG = `
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1400 600'>
  <rect width='1400' height='600' fill='#FBFAF7'/>
  <g filter='url(#soft-blur)' transform='rotate(-9 700 300)'>
    <path d='M -300 520 Q 250 380 700 460 T 1700 400 L 1700 900 L -300 900 Z' fill='#DFDACE' opacity='0.7'/>
    <path d='M -300 320 Q 300 160 780 300 T 1700 220 L 1700 -200 L -300 -200 Z' fill='#E9E4D8' opacity='0.6'/>
    <path d='M -300 100 Q 350 -60 820 90 T 1700 20 L 1700 -200 L -300 -200 Z' fill='#F0ECE1' opacity='0.55'/>
    <path d='M -300 700 Q 250 600 700 660 T 1700 620 L 1700 900 L -300 900 Z' fill='#D4CEC0' opacity='0.45'/>
  </g>
  <defs>
    <filter id='soft-blur'><feGaussianBlur stdDeviation='24'/></filter>
  </defs>
</svg>
`.trim()

const HERO_BACKGROUND_URL = `url("data:image/svg+xml,${encodeURIComponent(SVG)}")`

/** Fills its positioned parent with the backdrop above via a plain CSS
 * background-image — meant to sit behind a hero section's content, ending
 * cleanly at that section's own boundary. */
export default function HeroBackground({ className = '' }) {
  return (
    <div
      aria-hidden="true"
      className={`absolute inset-0 ${className}`}
      style={{
        backgroundImage: HERO_BACKGROUND_URL,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    />
  )
}
