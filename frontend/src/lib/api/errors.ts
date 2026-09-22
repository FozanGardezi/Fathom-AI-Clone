import axios from 'axios'

/**
 * Every failure the app can show a user, reduced to a handful of kinds.
 *
 * Components should never branch on a raw status code or an axios error shape.
 * They get an `ApiError` with a `kind` to branch on and a `message` that is
 * already fit to render.
 */
export type ApiErrorKind =
  | 'network' // the request never reached the server
  | 'timeout'
  | 'canceled' // the caller aborted it; not worth showing
  | 'auth' // 401 - not signed in, or the session expired
  | 'permission' // 403
  | 'notFound' // 404
  | 'validation' // 400/422 - the request was understood and rejected
  | 'conflict' // 409
  | 'rateLimit' // 429
  | 'server' // 5xx
  | 'unknown'

/** Field-keyed messages, exactly as DRF returns them. */
export type FieldErrors = Record<string, string[]>

const MESSAGES: Record<ApiErrorKind, string> = {
  network: "Can't reach the server. Check your connection and try again.",
  timeout: 'The server took too long to respond. Try again.',
  canceled: 'Request canceled.',
  auth: 'Your session has expired. Sign in again to continue.',
  permission: "You don't have access to this.",
  notFound: "We couldn't find what you were looking for.",
  validation: 'Some of the details you entered need fixing.',
  conflict: 'That conflicts with something that already exists.',
  rateLimit: 'Too many requests. Wait a moment and try again.',
  server: 'Something went wrong on our end. Try again in a moment.',
  unknown: 'Something went wrong. Try again.',
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | undefined
  /** Per-field messages from a validation failure, for forms to render inline. */
  readonly fieldErrors: FieldErrors | undefined
  /** The untouched response body, for logging - never render this directly. */
  readonly body: unknown

  constructor(
    kind: ApiErrorKind,
    message: string,
    options: { status?: number; fieldErrors?: FieldErrors; body?: unknown; cause?: unknown } = {},
  ) {
    super(message, { cause: options.cause })
    this.name = 'ApiError'
    this.kind = kind
    this.status = options.status
    this.fieldErrors = options.fieldErrors
    this.body = options.body
  }

  /** Worth another attempt on its own - a bad password never is. */
  get isRetryable() {
    return this.kind === 'network' || this.kind === 'timeout' || this.kind === 'server'
  }

  /** First message for a field, for inline form errors. */
  fieldError(field: string) {
    return this.fieldErrors?.[field]?.[0]
  }
}

/**
 * Phrases DRF produces that are written for developers, not users.
 *
 * "No Meeting matches the given query." and "Invalid pk ... object does not
 * exist." describe the lookup that failed rather than what went wrong from
 * where the user is sitting. When the server says something specific and
 * human - the nested endpoints answer "Meeting not found." - we keep it; when
 * it falls back to boilerplate, so do we.
 */
const INTERNAL_PHRASING = [
  /^no \S+ matches the given query\.?$/i,
  /^invalid pk /i,
  /^expected a .* but got /i,
  /^incorrect type/i,
]

function isInternalPhrasing(message: string) {
  return INTERNAL_PHRASING.some((pattern) => pattern.test(message.trim()))
}

function kindForStatus(status: number): ApiErrorKind {
  if (status === 401) return 'auth'
  if (status === 403) return 'permission'
  if (status === 404) return 'notFound'
  if (status === 409) return 'conflict'
  if (status === 429) return 'rateLimit'
  if (status === 400 || status === 422) return 'validation'
  if (status >= 500) return 'server'
  return 'unknown'
}

/**
 * Pull the most useful sentence out of a DRF error body.
 *
 * DRF answers in three shapes: `{detail: "..."}` for most errors,
 * `{field: ["..."]}` for validation, and `{non_field_errors: [...]}` for
 * whole-object validation. Anything else falls back to the generic message for
 * the kind, because showing a user a raw JSON fragment is worse than showing
 * them nothing specific.
 */
function readBody(body: unknown): { message?: string; fieldErrors?: FieldErrors } {
  if (typeof body === 'string' && body.trim() && !body.trimStart().startsWith('<')) {
    return { message: body }
  }
  if (!body || typeof body !== 'object') return {}

  const record = body as Record<string, unknown>

  if (typeof record.detail === 'string') return { message: record.detail }

  const fieldErrors: FieldErrors = {}
  for (const [key, value] of Object.entries(record)) {
    if (Array.isArray(value) && value.every((entry) => typeof entry === 'string')) {
      fieldErrors[key] = value as string[]
    } else if (typeof value === 'string') {
      fieldErrors[key] = [value]
    }
  }
  if (Object.keys(fieldErrors).length === 0) return {}

  // Whole-object errors read as a sentence; a single field error is clearer
  // with its field named than shown bare.
  const message = fieldErrors.non_field_errors?.[0] ?? Object.values(fieldErrors)[0]?.[0]
  return { message, fieldErrors }
}

/** Turn anything thrown by axios - or by us - into an ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (axios.isAxiosError(error)) {
    if (error.code === 'ERR_CANCELED') {
      return new ApiError('canceled', MESSAGES.canceled, { cause: error })
    }
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return new ApiError('timeout', MESSAGES.timeout, { cause: error })
    }
    // No response at all: DNS failure, offline, CORS, server down.
    if (!error.response) {
      return new ApiError('network', MESSAGES.network, { cause: error })
    }

    const status = error.response.status
    const kind = kindForStatus(status)
    const { message, fieldErrors } = readBody(error.response.data)
    // Field errors are still carried through for inline display; only the
    // headline sentence is swapped.
    const headline = message && !isInternalPhrasing(message) ? message : MESSAGES[kind]
    return new ApiError(kind, headline, {
      status,
      fieldErrors,
      body: error.response.data,
      cause: error,
    })
  }

  return new ApiError('unknown', MESSAGES.unknown, { cause: error })
}

/**
 * The sentence to show a user for any thrown value.
 *
 * Safe to call with `unknown` - which is what react-query hands back - so
 * components never have to narrow the type themselves.
 */
export function errorMessage(error: unknown): string {
  if (!error) return ''
  return toApiError(error).message
}
