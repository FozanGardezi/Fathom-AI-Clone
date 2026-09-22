import { QueryClient } from '@tanstack/react-query'

import { toApiError } from './api'

/**
 * One QueryClient for the app.
 *
 * The retry policy is the part that matters: a dropped connection or a 500
 * deserves another go, but retrying a 404 or a validation error just delays
 * the message the user needs to see. `ApiError.isRetryable` draws that line,
 * so it is drawn once rather than per-hook.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => failureCount < 2 && toApiError(error).isRetryable,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 5000),
      refetchOnWindowFocus: false,
      // Meeting data changes on the order of minutes, not seconds.
      staleTime: 30_000,
    },
    mutations: {
      // A write that may have been applied must not be replayed blindly.
      retry: false,
    },
  },
})
