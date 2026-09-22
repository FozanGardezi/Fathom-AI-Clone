import { ApiError, errorMessage } from '../../lib/api'
import Button from './Button'
import Icon from './Icon'

/**
 * The failure body for a panel.
 *
 * Takes the thrown value rather than a string, so no caller has to work out
 * what to say - `errorMessage` already turned the failure into a sentence.
 * Retry is only offered when retrying could actually help: re-requesting a 404
 * gives the same 404 and makes the app feel broken.
 */
export default function ErrorState({
  error,
  onRetry,
  title,
}: {
  error: unknown
  onRetry?: () => void
  title?: string
}) {
  const apiError = error instanceof ApiError ? error : null
  const canRetry = Boolean(onRetry) && (apiError?.isRetryable ?? true)

  return (
    <div role="alert" className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-4 flex size-11 items-center justify-center rounded-xl border border-amber-200 bg-amber-50 text-amber-600">
        <Icon name="bell" className="size-5" />
      </div>
      <h3 className="text-sm font-semibold text-ink">{title ?? "That didn't work"}</h3>
      <p className="mt-1.5 max-w-sm text-[13px] leading-5 text-text-tertiary">
        {errorMessage(error)}
      </p>
      {canRetry && (
        <Button size="sm" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

/** Compact inline variant, for form and toolbar errors where a full panel
 *  would be too much. */
export function InlineError({ error }: { error: unknown }) {
  const message = errorMessage(error)
  if (!message) return null
  return (
    <p role="alert" className="text-[13px] leading-5 text-red-600">
      {message}
    </p>
  )
}
