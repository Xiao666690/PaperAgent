export const sessionExpiredEvent = 'paperagent:session-expired'

export function clearSession() {
  for (const key of ['token', 'username', 'role', 'workspaceLid', 'tokenExpiresAt']) {
    localStorage.removeItem(key)
  }
}

export function invalidateSession(requestToken: string | null) {
  if (!requestToken || requestToken !== localStorage.getItem('token')) return
  clearSession()
  window.dispatchEvent(new Event(sessionExpiredEvent))
}
