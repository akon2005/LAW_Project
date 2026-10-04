/**
 * Inline SVG icons for the authentication screens.
 *
 * Same visual language as the icon set inside App.jsx (1.8 stroke, round
 * caps/joins, currentColor) so the login page belongs to the existing
 * interface rather than importing a second icon library.
 */
const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
  focusable: 'false',
}

function Svg({ size = 18, children, ...rest }) {
  return (
    <svg {...base} width={size} height={size} {...rest}>
      {children}
    </svg>
  )
}

export function MailIcon(props) {
  return (
    <Svg {...props}>
      <rect x="2.5" y="4.8" width="19" height="14.4" rx="2.4" />
      <path d="m3.4 7 8.6 6 8.6-6" />
    </Svg>
  )
}

export function LockIcon(props) {
  return (
    <Svg {...props}>
      <rect x="4.5" y="10.5" width="15" height="10" rx="2.2" />
      <path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7" />
      <path d="M12 14.4v2.4" />
    </Svg>
  )
}

export function EyeIcon(props) {
  return (
    <Svg {...props}>
      <path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3.1" />
    </Svg>
  )
}

export function EyeOffIcon(props) {
  return (
    <Svg {...props}>
      <path d="M4 4.5 20 19.5" />
      <path d="M9.6 6.2A9.7 9.7 0 0 1 12 5.9c6 0 9.5 6.1 9.5 6.1a17 17 0 0 1-3.3 3.9" />
      <path d="M6.4 8.2A17 17 0 0 0 2.5 12s3.5 6.2 9.5 6.2a9.8 9.8 0 0 0 3.3-.6" />
      <path d="M9.9 10a3 3 0 0 0 4.2 4.2" />
    </Svg>
  )
}

export function ShieldCheckIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 3.2 19 6v5.7c0 4-2.9 7.3-7 9.1-4.1-1.8-7-5.1-7-9.1V6Z" />
      <path d="m9.1 12.1 2 2 3.8-4" />
    </Svg>
  )
}

export function ArrowRightIcon(props) {
  return (
    <Svg {...props}>
      <path d="M4.8 12h14.4" />
      <path d="m13.6 6.4 6 5.6-6 5.6" />
    </Svg>
  )
}

export function CheckIcon(props) {
  return (
    <Svg {...props}>
      <path d="m5 12.4 4.2 4.2L19 7" />
    </Svg>
  )
}

export function AlertIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.8v5" />
      <path d="M12 16.1h.01" />
    </Svg>
  )
}

export function InfoIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5.2" />
      <path d="M12 7.9h.01" />
    </Svg>
  )
}

export function ScaleIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 4v16M7 8h10M5 8l-3 6a3 3 0 0 0 6 0zM19 8l-3 6a3 3 0 0 0 6 0zM8 20h8" />
    </Svg>
  )
}

export function SpinnerIcon({ size = 16, className = '' }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={`auth-spinner ${className}`}
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.4" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  )
}
