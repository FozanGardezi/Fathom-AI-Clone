/** The Google Calendar connection. */
import { api } from './client'
import type { CalendarConnection, CalendarSyncResult } from './types'

const V1 = '/v1'

export async function getCalendarConnection(signal?: AbortSignal): Promise<CalendarConnection> {
  const { data } = await api.get(`${V1}/calendar/connection/`, { signal })
  return data
}

/**
 * Ask for the Google consent URL.
 *
 * The browser is then sent there; Google redirects back to the API, which
 * does the code exchange server-side and returns the browser to /calendar.
 * The client secret never enters a browser.
 */
export async function beginCalendarConnect(): Promise<{ authorization_url: string }> {
  const { data } = await api.post(`${V1}/calendar/connect/`, {})
  return data
}

export async function syncCalendar(): Promise<CalendarSyncResult> {
  const { data } = await api.post(`${V1}/calendar/sync/`, {})
  return data
}

export async function disconnectCalendar(): Promise<CalendarConnection> {
  const { data } = await api.delete(`${V1}/calendar/connection/`)
  return data
}
