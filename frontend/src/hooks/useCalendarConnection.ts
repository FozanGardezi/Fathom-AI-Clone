import { useCallback, useState } from 'react'

/**
 * The calendar connection, stubbed.
 *
 * There is no OAuth flow behind this and no field on the backend to hold the
 * result, so the state lives in localStorage. That is honest about what it is:
 * a per-browser flag, not an account-level fact. When a real integration
 * lands, the shape of this hook is what the UI already consumes - only the
 * bodies change, to a POST that starts the flow and a field on the user.
 */
const STORAGE_KEY = 'fathom.calendar.provider'

export type CalendarStatus = 'disconnected' | 'connecting' | 'connected'
export const PROVIDER_NAME = 'Google Calendar'

function read(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'google'
  } catch {
    // Private browsing and blocked storage both throw rather than return null.
    return false
  }
}

export function useCalendarConnection() {
  // Read once, lazily. `read` swallows the throw that blocked storage raises,
  // so this is safe as an initial value and saves a second render.
  const [status, setStatus] = useState<CalendarStatus>(() =>
    read() ? 'connected' : 'disconnected',
  )

  const connect = useCallback(() => {
    setStatus('connecting')
    // Stands in for the round trip to the provider's consent screen. Real
    // enough that the UI has to handle a pending state, which it would.
    const timer = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, 'google')
      } catch {
        // Nothing to do: the session still shows as connected, it just will
        // not survive a reload.
      }
      setStatus('connected')
    }, 1200)
    return () => clearTimeout(timer)
  }, [])

  const disconnect = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Ignored for the same reason as above.
    }
    setStatus('disconnected')
  }, [])

  return { status, connect, disconnect, provider: PROVIDER_NAME }
}
