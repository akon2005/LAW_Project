/**
 * Shared inline icon set. Stroke-based, inherits `currentColor`, so every icon
 * follows the active palette without any per-icon styling.
 */
export default function Icon({ name, size = 18 }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }
  const paths = {
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 5.5v16"/><path d="M8 7h8M8 11h8"/></>,
    file: <><path d="M6 2.8h8l4 4V21H6z"/><path d="M14 2.8V7h4"/><path d="M9 11h6M9 15h6"/></>,
    scale: <><path d="M12 4v16M7 8h10M5 8l-3 6a3 3 0 0 0 6 0zM19 8l-3 6a3 3 0 0 0 6 0zM8 20h8"/></>,
    chevron: <path d="m7 9 5 5 5-5"/>,
    arrow: <><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>,
    filter: <><path d="M4 5h16l-6.5 7.3V19l-3 1v-7.7z"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 10v6"/><path d="M12 7h.01"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    knowledge: <><circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="7" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M8.2 7.4 16 8.2M7.2 8.2l3.6 7.4M16.8 9.2l-3.4 6.6"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2 2 2 0 1 1-4 0 1.7 1.7 0 0 0-2.9-1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15a2 2 0 1 1 0-4 1.7 1.7 0 0 0 1.5-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 10 4.1a2 2 0 1 1 4 0 1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 21 11a2 2 0 1 1 0 4z"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></>,
    moon: <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>,
    monitor: <><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></>,
    palette: <><circle cx="12" cy="12" r="9"/><circle cx="8.5" cy="10" r="1.1" fill="currentColor" stroke="none"/><circle cx="12" cy="8" r="1.1" fill="currentColor" stroke="none"/><circle cx="15.5" cy="10" r="1.1" fill="currentColor" stroke="none"/><path d="M12 21a3 3 0 0 0 0-6 3 3 0 0 1 0-6"/></>,
    droplet: <path d="M12 3s6 6.2 6 10.4A6 6 0 0 1 6 13.4C6 9.2 12 3 12 3z"/>,
  }
  return <svg {...common}>{paths[name]}</svg>
}
