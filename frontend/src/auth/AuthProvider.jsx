/**
 * Session context.
 *
 * Holds the signed-in session for the whole app. The workspace reads
 * `session`; the login screen calls `login` and then `commit`.
 *
 * `login` and `commit` are deliberately separate. Sign-in verifies the
 * credentials and persists the session, but does not publish it to React state
 * — that lets the login screen play its exit transition before the workspace
 * takes over, without faking a delay inside the form.
 */
import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import authService from '../services/authService.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => authService.getSession())
  const [status, setStatus] = useState('idle') // idle | authenticating

  /** Verify credentials and persist the session. Returns it without committing. */
  const login = useCallback(async (credentials) => {
    setStatus('authenticating')
    try {
      return await authService.login(credentials)
    } finally {
      setStatus('idle')
    }
  }, [])

  /** Publish a session obtained from `login` to the rest of the app. */
  const commit = useCallback((next) => {
    setSession(next)
  }, [])

  const logout = useCallback(() => {
    authService.logout()
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({
      session,
      status,
      login,
      commit,
      logout,
      isLive: authService.isLive,
      mode: authService.mode,
    }),
    [session, status, login, commit, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return context
}

export default AuthProvider
