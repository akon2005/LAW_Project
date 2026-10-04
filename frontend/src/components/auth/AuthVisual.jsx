/**
 * Editorial visual for the sign-in screen: a reading room rendered as inline
 * SVG line art (colonnade, book stacks, an open judgment on the desk).
 *
 * Why line art instead of a photograph: the project's own convention (see
 * public/assets/README.txt) is to stay self-contained and avoid external image
 * dependencies, and a restrained architectural drawing reads as institutional
 * research rather than stock photography.
 *
 * Prefer a real photograph? Point VITE_LOGIN_VISUAL at an image path or URL and
 * it replaces the drawing without touching any other file.
 */
import { useId } from 'react'

const SHELVES = [
  { top: 186, bottom: 279 },
  { top: 279, bottom: 372 },
  { top: 372, bottom: 465 },
]

const ARCHES = [58, 208, 358, 508]
const ARCH_WIDTH = 130
const ARCH_SPRING = 566
const ARCH_BASE = 792

/** Deterministic book spines — stable between renders, no randomness. */
function spinesFor(shelf, shelfIndex) {
  const spines = []
  let x = 44
  let index = 0
  while (x < 668) {
    const width = 7 + ((index * 5 + shelfIndex * 3) % 10)
    const height = shelf.bottom - shelf.top - 16 - ((index * 7 + shelfIndex * 5) % 22)
    spines.push({
      x,
      width,
      top: shelf.bottom - 9 - height,
      height,
      accent: (index + shelfIndex) % 19 === 0,
      filled: (index * 3 + shelfIndex) % 5 === 0,
    })
    x += width + 3
    index += 1
  }
  return spines
}

function PageLines({ x, y, width, rows }) {
  return Array.from({ length: rows }, (_, row) => (
    <line
      key={row}
      x1={x + 6}
      x2={x + width - (row % 4 === 3 ? 26 : 8)}
      y1={y + row * 6}
      y2={y + row * 6}
      stroke="#e8f0f6"
      strokeOpacity="0.3"
      strokeWidth="1.1"
    />
  ))
}

export default function AuthVisual({ imageSrc = null, className = '', compact = false }) {
  const uid = useId().replace(/:/g, '')
  const gridId = `grid-${uid}`
  const shaftId = `shaft-${uid}`
  const vignetteId = `vignette-${uid}`

  return (
    <div className={`login-visual ${compact ? 'is-compact' : ''} ${className}`.trim()} aria-hidden="true">
      {imageSrc ? (
        <img className="login-visual__photo" src={imageSrc} alt="" />
      ) : (
        <svg
          className="login-visual__art"
          viewBox="0 0 720 1000"
          preserveAspectRatio="xMidYMid slice"
          focusable="false"
        >
          <defs>
            <pattern id={gridId} width="36" height="36" patternUnits="userSpaceOnUse">
              <path d="M36 0H0v36" fill="none" stroke="#cfe0ea" strokeOpacity="0.05" strokeWidth="1" />
            </pattern>
            <linearGradient id={shaftId} x1="0.5" y1="0" x2="0.5" y2="1">
              <stop offset="0%" stopColor="#f4dfac" stopOpacity="0.16" />
              <stop offset="70%" stopColor="#f4dfac" stopOpacity="0.03" />
              <stop offset="100%" stopColor="#f4dfac" stopOpacity="0" />
            </linearGradient>
            <radialGradient id={vignetteId} cx="0.5" cy="0.42" r="0.78">
              <stop offset="55%" stopColor="#0b1a26" stopOpacity="0" />
              <stop offset="100%" stopColor="#08131d" stopOpacity="0.55" />
            </radialGradient>
          </defs>

          <rect width="720" height="1000" fill={`url(#${gridId})`} />

          {/* Slow, almost imperceptible drift of the light. */}
          <g className="login-visual__drift">
            <polygon points="250,0 470,0 610,1000 110,1000" fill={`url(#${shaftId})`} />
          </g>

          {/* Frieze */}
          <g stroke="#dbe7ef" strokeOpacity="0.14" strokeWidth="1.2">
            <line x1="34" y1="150" x2="686" y2="150" />
            <line x1="34" y1="160" x2="686" y2="160" strokeOpacity="0.08" />
          </g>

          {/* Book stacks */}
          {SHELVES.map((shelf, shelfIndex) => (
            <g key={shelf.top}>
              {spinesFor(shelf, shelfIndex).map((spine) => (
                <rect
                  key={`${spine.x}-${spine.top}`}
                  x={spine.x}
                  y={spine.top}
                  width={spine.width}
                  height={spine.height}
                  fill={spine.filled ? '#dbe7ef' : 'none'}
                  fillOpacity={spine.filled ? 0.05 : 0}
                  stroke={spine.accent ? '#f4dfac' : '#dbe7ef'}
                  strokeOpacity={spine.accent ? 0.3 : 0.13}
                  strokeWidth="1"
                />
              ))}
              <line
                x1="34"
                y1={shelf.bottom}
                x2="686"
                y2={shelf.bottom}
                stroke="#dbe7ef"
                strokeOpacity="0.16"
                strokeWidth="1.6"
              />
            </g>
          ))}

          {/* Colonnade */}
          <g fill="none" stroke="#dbe7ef" strokeOpacity="0.2" strokeWidth="1.6">
            {ARCHES.map((x) => (
              <path
                key={x}
                d={`M${x},${ARCH_BASE} V${ARCH_SPRING} A65,65 0 0 1 ${x + ARCH_WIDTH},${ARCH_SPRING} V${ARCH_BASE}`}
              />
            ))}
            {ARCHES.map((x) => (
              <path
                key={`inner-${x}`}
                d={`M${x + 11},${ARCH_BASE} V${ARCH_SPRING} A54,54 0 0 1 ${x + ARCH_WIDTH - 11},${ARCH_SPRING} V${ARCH_BASE}`}
                strokeOpacity="0.09"
              />
            ))}
          </g>

          {/* Plinth and floor */}
          <g stroke="#dbe7ef" strokeOpacity="0.14" strokeWidth="1.2">
            <line x1="20" y1={ARCH_BASE} x2="700" y2={ARCH_BASE} />
            <line x1="20" y1={ARCH_BASE + 9} x2="700" y2={ARCH_BASE + 9} strokeOpacity="0.07" />
          </g>

          {/* Reading desk */}
          <g fill="none" stroke="#dbe7ef" strokeOpacity="0.22" strokeWidth="1.6">
            <path d="M64,866 H656" />
            <path d="M64,866 L104,836 H616 L656,866" strokeOpacity="0.16" />
            <path d="M120,866 V972" />
            <path d="M600,866 V972" />
            <path d="M112,972 H128 M592,972 H608" strokeOpacity="0.14" />
          </g>

          {/* Closed volumes on the desk */}
          <g stroke="#dbe7ef" strokeOpacity="0.2" strokeWidth="1.3" fill="none">
            <rect x="152" y="812" width="104" height="14" rx="2" />
            <rect x="160" y="800" width="96" height="12" rx="2" strokeOpacity="0.14" />
            <line x1="162" y1="812" x2="162" y2="826" strokeOpacity="0.26" />
            <line x1="170" y1="800" x2="170" y2="812" strokeOpacity="0.2" />
          </g>

          {/* Open judgment */}
          <g>
            <path
              d="M286,836 L432,836 L418,742 L300,752 Z"
              fill="#eef4f9"
              fillOpacity="0.045"
              stroke="#e8f0f6"
              strokeOpacity="0.34"
              strokeWidth="1.4"
            />
            <path
              d="M432,836 L578,836 L556,752 L418,742 Z"
              fill="#eef4f9"
              fillOpacity="0.03"
              stroke="#e8f0f6"
              strokeOpacity="0.28"
              strokeWidth="1.4"
            />
            <line x1="432" y1="836" x2="418" y2="742" stroke="#e8f0f6" strokeOpacity="0.18" />

            <g transform="rotate(-3 300 752)">
              <PageLines x={300} y={766} width={104} rows={9} />
            </g>
            <g transform="rotate(3 556 752)">
              <PageLines x={434} y={766} width={106} rows={9} />
            </g>

            {/* Page numbers and a citation marker */}
            <text x="306" y="830" fill="#e8f0f6" fillOpacity="0.4" fontSize="9" fontFamily="Georgia, serif">
              12
            </text>
            <text x="544" y="830" fill="#e8f0f6" fillOpacity="0.4" fontSize="9" fontFamily="Georgia, serif">
              13
            </text>
            <text x="470" y="790" fill="#f4dfac" fillOpacity="0.5" fontSize="10" fontFamily="Georgia, serif">
              [23]
            </text>
          </g>

          <rect width="720" height="1000" fill={`url(#${vignetteId})`} className="login-visual__vignette" />
        </svg>
      )}

      <div className="login-visual__scrim" />
    </div>
  )
}
