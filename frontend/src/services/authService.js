/**
 * Authentication service.
 *
 * The UI never calls the network directly — it goes through this module, so
 * connecting VIDHIVEDA to a real FastAPI auth endpoint later is a config
 * change rather than a rewrite.
 *
 * Two modes, and the UI is told which one is active:
 *
 *   live — `VITE_AUTH_ENDPOINT` (or `VITE_API_BASE` + `/auth/login`) resolves.
 *          Credentials are POSTed there and the response is expected to look
 *          like { access_token, user: { email, name?, role? } }.
 *
 *   demo — no endpoint is configured, or it answers 404/501. The sign-in is
 *          validated locally and the session is flagged `mode: 'demo'`. It is
 *          never presented as a real credential check.
 *
 * No backend auth system is created by this file, and passwords are never
 * stored or logged.
 */

export const SESSION_KEY = 'vidhiveda.session';

/** Roles offered at sign-in. Kept in one place so the UI and the API agree. */
export const ROLES = [
  {
    id: 'judicial-officer',
    label: 'Judge / Judicial Officer',
    short: 'Judicial Officer',
    description: 'Bench-side research and precedent review',
  },
  {
    id: 'lawyer',
    label: 'Lawyer',
    short: 'Lawyer',
    description: 'Case preparation and authority tracing',
  },
  {
    id: 'researcher',
    label: 'Legal Researcher',
    short: 'Legal Researcher',
    description: 'Statutory and academic legal research',
  },
];

export const DEFAULT_ROLE = ROLES[1].id;

export function roleLabel(roleId) {
  return ROLES.find((role) => role.id === roleId)?.short || 'Legal Researcher';
}

/** Machine-readable error codes plus the copy each one maps to. */
export const AUTH_ERRORS = {
  invalid_email: 'Please enter a valid email address.',
  missing_email: 'Please enter your email address.',
  missing_password: 'Please enter your password.',
  short_password: 'Your password must be at least 6 characters.',
  invalid_credentials: 'Unable to sign in. Please check your credentials.',
  network_error:
    'Unable to reach the authentication service. Check your connection and try again.',
  rate_limited: 'Too many attempts. Please wait a moment and try again.',
  server_error:
    'The authentication service is temporarily unavailable. Please try again.',
};

export class AuthError extends Error {
  /**
   * @param {keyof AUTH_ERRORS} code
   * @param {{ field?: 'email'|'password', message?: string }} [options]
   */
  constructor(code, options = {}) {
    super(options.message || AUTH_ERRORS[code] || AUTH_ERRORS.server_error);
    this.name = 'AuthError';
    this.code = code;
    this.field = options.field;
  }
}

// ── Configuration ──────────────────────────────────────────────────────
const ENV = import.meta.env || {};

function resolveEndpoint() {
  const explicit = ENV.VITE_AUTH_ENDPOINT;
  if (explicit) return explicit;
  const base = ENV.VITE_API_BASE;
  return base ? `${String(base).replace(/\/$/, '')}/auth/login` : '';
}

const ENDPOINT = resolveEndpoint();
const REQUEST_TIMEOUT_MS = Number(ENV.VITE_AUTH_TIMEOUT_MS || 12000);

// ── Validation ─────────────────────────────────────────────────────────
// Deliberately permissive: enough to catch typos, not so strict that it
// rejects unusual but valid institutional addresses.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function isValidEmail(value) {
  return EMAIL_PATTERN.test(String(value || '').trim());
}

/** Field-level validation shared by the form and the service. */
export function validateCredentials({ email, password }) {
  const errors = {};
  const trimmed = String(email || '').trim();

  if (!trimmed) errors.email = AUTH_ERRORS.missing_email;
  else if (!isValidEmail(trimmed)) errors.email = AUTH_ERRORS.invalid_email;

  if (!password) errors.password = AUTH_ERRORS.missing_password;
  else if (String(password).length < 6) errors.password = AUTH_ERRORS.short_password;

  return errors;
}

// ── Session storage ────────────────────────────────────────────────────
// "Remember me" keeps the session across browser restarts (localStorage);
// otherwise it lives only for the tab (sessionStorage).
function safeStorage(kind) {
  try {
    const store = kind === 'local' ? window.localStorage : window.sessionStorage;
    const probe = '__vidhiveda_probe__';
    store.setItem(probe, '1');
    store.removeItem(probe);
    return store;
  } catch {
    return null;
  }
}

function writeSession(session, remember) {
  const payload = JSON.stringify(session);
  const primary = remember ? safeStorage('local') : safeStorage('session');
  const secondary = remember ? safeStorage('session') : safeStorage('local');
  try {
    secondary?.removeItem(SESSION_KEY);
    primary?.setItem(SESSION_KEY, payload);
  } catch {
    /* storage unavailable (private mode) — session stays in memory only */
  }
}

function readSession() {
  for (const kind of ['local', 'session']) {
    try {
      const raw = safeStorage(kind)?.getItem(SESSION_KEY);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      if (!parsed?.user?.email) continue;
      if (parsed.expiresAt && Date.now() > parsed.expiresAt) {
        safeStorage(kind)?.removeItem(SESSION_KEY);
        continue;
      }
      return parsed;
    } catch {
      /* ignore malformed payloads */
    }
  }
  return null;
}

function clearSession() {
  for (const kind of ['local', 'session']) {
    try {
      safeStorage(kind)?.removeItem(SESSION_KEY);
    } catch {
      /* nothing to clear */
    }
  }
}

// ── Service ────────────────────────────────────────────────────────────
class AuthService {
  constructor() {
    this.endpoint = ENDPOINT;
    this.isLive = Boolean(ENDPOINT);
    this.mode = ENDPOINT ? 'live' : 'demo';
  }

  getSession() {
    return readSession();
  }

  /**
   * Sign in. Resolves with a session object or rejects with an `AuthError`.
   *
   * @param {{ email: string, password: string, role?: string, remember?: boolean }} credentials
   */
  async login({ email, password, role = DEFAULT_ROLE, remember = false }) {
    const normalizedEmail = String(email || '').trim();

    const fieldErrors = validateCredentials({ email: normalizedEmail, password });
    const firstField = fieldErrors.email ? 'email' : fieldErrors.password ? 'password' : null;
    if (firstField) {
      throw new AuthError(
        firstField === 'email'
          ? fieldErrors.email === AUTH_ERRORS.missing_email
            ? 'missing_email'
            : 'invalid_email'
          : fieldErrors.password === AUTH_ERRORS.missing_password
            ? 'missing_password'
            : 'short_password',
        { field: firstField },
      );
    }

    if (this.isLive) {
      const live = await this._loginLive({ email: normalizedEmail, password, role });
      if (live) return this._commit(live, { remember, email: normalizedEmail, role });
      // Endpoint missing (404/501): fall through to demo, clearly flagged.
    }

    return this._commit(await this._loginDemo({ email: normalizedEmail, role }), {
      remember,
      email: normalizedEmail,
      role,
    });
  }

  logout() {
    clearSession();
  }

  // ── Internals ────────────────────────────────────────────────────────
  _commit(partial, { remember, email, role }) {
    const session = {
      user: {
        email,
        name: partial.name || this._nameFromEmail(email),
        role: partial.role || role,
      },
      token: partial.token || null,
      mode: partial.mode,
      issuedAt: new Date().toISOString(),
      expiresAt: Date.now() + 12 * 60 * 60 * 1000,
      notice: partial.notice || null,
    };
    writeSession(session, remember);
    return session;
  }

  /**
   * POST the credentials to the configured endpoint.
   * Returns null when the endpoint does not exist, so the caller can fall back.
   */
  async _loginLive({ email, password, role }) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    let response;
    try {
      response = await fetch(this.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, role }),
        signal: controller.signal,
      });
    } catch (error) {
      clearTimeout(timer);
      throw new AuthError(
        error?.name === 'AbortError' ? 'network_error' : 'network_error',
        { field: null },
      );
    }
    clearTimeout(timer);

    if (response.status === 404 || response.status === 501) return null;
    if (response.status === 401 || response.status === 403) {
      throw new AuthError('invalid_credentials');
    }
    if (response.status === 429) throw new AuthError('rate_limited');
    if (response.status >= 500) throw new AuthError('server_error');

    if (!response.ok) throw new AuthError('invalid_credentials');

    const data = await response.json().catch(() => ({}));
    return {
      token: data.access_token || data.token || null,
      name: data.user?.name || data.user?.full_name || null,
      role: data.user?.role || role,
      mode: 'live',
    };
  }

  /**
   * Demo sign-in: locally validated, explicitly labelled as demo. The short
   * delay exists only so the loading state is exercised honestly.
   */
  async _loginDemo({ email, role }) {
    await new Promise((resolve) => setTimeout(resolve, 550));
    return {
      token: null,
      role,
      mode: 'demo',
      notice:
        'Demo session: no authentication endpoint is configured, so these credentials were not verified against a server.',
      name: this._nameFromEmail(email),
    };
  }

  _nameFromEmail(email) {
    const local = String(email || '').split('@')[0] || '';
    return local
      .split(/[._-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }
}

export const authService = new AuthService();
export default authService;
