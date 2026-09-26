import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  ApiError,
  beginCalendarConnect,
  disconnectCalendar,
  errorMessage,
  getCalendarConnection,
  queryKeys,
  syncCalendar,
} from '../lib/api'
import type { CalendarConnection, CalendarSyncResult } from '../lib/api'

/**
 * The Google Calendar link.
 *
 * Backed by the API rather than browser storage: whether an account has
 * granted Google access is a fact about the account, not about the browser
 * someone happens to be using.
 *
 * Connecting is a full-page redirect, not a popup. Google's consent screen
 * blocks popups in plenty of configurations, and a redirect is the flow their
 * own documentation assumes.
 */
export function useCalendarConnection() {
  const queryClient = useQueryClient()

  const connection = useQuery<CalendarConnection, ApiError>({
    queryKey: queryKeys.workspace.calendarConnection,
    queryFn: ({ signal }) => getCalendarConnection(signal),
  })

  const connect = useMutation<{ authorization_url: string }, ApiError, void>({
    mutationFn: beginCalendarConnect,
    onSuccess: ({ authorization_url }) => {
      // Leaves the app entirely; the API brings the browser back afterwards.
      window.location.assign(authorization_url)
    },
  })

  const sync = useMutation<CalendarSyncResult, ApiError, void>({
    mutationFn: syncCalendar,
    onSuccess: () => {
      // Synced events are meetings now, so everything that lists meetings is
      // stale - the dashboard, the calendar grid and the counts alike.
      queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.workspace.all })
    },
  })

  const disconnect = useMutation<CalendarConnection, ApiError, void>({
    mutationFn: disconnectCalendar,
    onSuccess: (state) => {
      queryClient.setQueryData(queryKeys.workspace.calendarConnection, state)
    },
  })

  return {
    connection: connection.data,
    isLoading: connection.isPending,
    isError: connection.isError,
    message: errorMessage(connection.error),
    refetch: connection.refetch,
    connect,
    sync,
    disconnect,
  }
}
