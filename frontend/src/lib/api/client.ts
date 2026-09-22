import axios from 'axios'

import { toApiError } from './errors'

const ACCESS_KEY = 'fathom.access'
const REFRESH_KEY = 'fathom.refresh'

/**
 * Where the API lives.
 *
 * `VITE_API_URL` is the configured value; `VITE_API_BASE` is the name this
 * used to have and is still honoured so existing .env files and build args
 * keep working. The default is the relative `/api`, which Vite proxies in dev
 * and nginx proxies in the container - so nothing has to be configured to run
 * the app locally.
 */
export const API_URL =
  import.meta.env.VITE_API_URL ?? import.meta.env.VITE_API_BASE ?? '/api'

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY)
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
  // A request that has not answered in 20s is not going to.
  timeout: 20_000,
})

api.interceptors.request.use((config) => {
  const token = tokens.access
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/**
 * One refresh at a time.
 *
 * A page that fires five queries on mount gets five 401s when the access token
 * expires. Without this they would each spend the refresh token, and since the
 * backend rotates refresh tokens, four of those five would fail and sign the
 * user out. Instead the first 401 starts a refresh and the rest wait on it.
 */
let refreshInFlight: Promise<string> | null = null

function refreshAccessToken() {
  refreshInFlight ??= axios
    .post(`${API_URL}/auth/refresh/`, { refresh: tokens.refresh })
    .then(({ data }) => {
      tokens.set(data.access, data.refresh)
      return data.access as string
    })
    .finally(() => {
      refreshInFlight = null
    })
  return refreshInFlight
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config

    const canRetry =
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      tokens.refresh &&
      // The refresh call itself must never trigger another refresh.
      !String(original.url ?? '').includes('/auth/refresh/')

    if (!canRetry) {
      // Every rejection leaving this client is an ApiError, so callers never
      // see an axios shape.
      return Promise.reject(toApiError(error))
    }

    original._retried = true
    try {
      const access = await refreshAccessToken()
      original.headers.Authorization = `Bearer ${access}`
      return await api(original)
    } catch (refreshError) {
      // The session is genuinely over. Clearing here means RequireAuth sends
      // the user to /login on the next render.
      tokens.clear()
      return Promise.reject(toApiError(refreshError))
    }
  },
)
