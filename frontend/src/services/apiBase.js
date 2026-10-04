/**
 * Single source for the backend origin the frontend talks to.
 * Override with VITE_API_BASE (e.g. in a deployment environment).
 */
export const API_BASE = String(import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(
  /\/$/,
  '',
)

export default API_BASE
