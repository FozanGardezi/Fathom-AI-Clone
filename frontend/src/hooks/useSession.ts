import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { errorMessage, fetchHealth, fetchMe, logout, queryKeys } from '../lib/api'
import type { ApiError, User } from '../lib/api'

/** The signed-in user, plus a sign-out that clears tokens and leaves. */
export function useSession() {
  const navigate = useNavigate()
  const query = useQuery<User, ApiError>({ queryKey: queryKeys.me, queryFn: fetchMe })

  return {
    user: query.data,
    // Stays true through retry backoff, unlike isLoading.
    isPending: query.isPending,
    isError: query.isError,
    message: errorMessage(query.error),
    signOut() {
      logout()
      navigate('/login', { replace: true })
    },
  }
}

/** API and database status, for the Overview page. */
export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: fetchHealth })
}
