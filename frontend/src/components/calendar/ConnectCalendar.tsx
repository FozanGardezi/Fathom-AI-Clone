import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

import Button from '../ui/Button'
import Icon from '../ui/Icon'
import { Card } from '../ui/Card'
import Skeleton from '../ui/Skeleton'
import { Spinner } from '../ui/LoadingState'
import { InlineError } from '../ui/ErrorState'
import { formatDateTime } from '../../lib/format'
import { cx } from '../../lib/cx'
import { useCalendarConnection } from '../../hooks/useCalendarConnection'

/** What the API redirected us back with, if anything. */
const RETURN_MESSAGES: Record<string, { tone: 'ok' | 'bad'; text: string }> = {
  connected: { tone: 'ok', text: 'Google Calendar connected.' },
  denied: { tone: 'bad', text: 'Access was declined, so nothing was connected.' },
  failed: { tone: 'bad', text: "That didn't complete." },
}

/** Why it did not complete. The callback cannot show Google's own message -
 *  it arrives as a redirect, not a response the page can read - so it passes
 *  a short code and logs the detail server-side. Saying which step broke is
 *  the difference between a fixable problem and a dead end. */
const FAILURE_REASONS: Record<string, string> = {
  missing_code: 'Google did not send an authorisation code back.',
  expired: 'The sign-in took too long and expired. Try again.',
  bad_state: 'The sign-in could not be matched to your session. Try again.',
  exchange:
    'The server could not exchange the code with Google. Check the API log for the reason — a redirect-URI mismatch and an outbound TLS failure both land here.',
}

/**
 * The calendar connection: not configured → not connected → connected.
 *
 * "Not configured" is a genuinely different state from "not connected" and
 * says so, because the fix belongs to whoever runs the server rather than to
 * the person looking at the screen.
 */
export default function ConnectCalendar() {
  const { connection, isLoading, connect, sync, disconnect } = useCalendarConnection()
  const [params, setParams] = useSearchParams()

  // The outcome the API redirected back with. Read during render rather than
  // copied into state by an effect, and stripped from the URL afterwards so a
  // reload does not keep announcing it.
  const outcome = params.get('calendar')
  const returned = outcome ? (RETURN_MESSAGES[outcome] ?? null) : null
  const reason = FAILURE_REASONS[params.get('reason') ?? ''] ?? null

  useEffect(() => {
    if (!outcome) return
    // Deferred so the message renders before the URL that produced it is
    // cleared; without the timeout the banner would never be seen.
    const timer = setTimeout(() => {
      const next = new URLSearchParams(params)
      next.delete('calendar')
      next.delete('reason')
      setParams(next, { replace: true })
    }, 6000)
    return () => clearTimeout(timer)
  }, [outcome, params, setParams])

  if (isLoading) return <Skeleton className="mb-5 h-[68px] w-full rounded-xl" />

  const synced = sync.data

  if (connection?.is_connected) {
    return (
      <Card className="mb-5 px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
            <Icon name="calendar" className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold text-ink">
              {connection.provider_label} connected
              <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
            </p>
            <p className="mt-0.5 truncate text-[12px] text-text-tertiary">
              {connection.account_email || 'Connected account'}
              {connection.last_synced_at && (
                <> · last synced {formatDateTime(connection.last_synced_at)}</>
              )}
            </p>
          </div>

          <Button size="sm" onClick={() => sync.mutate()} disabled={sync.isPending}>
            {sync.isPending ? (
              <>
                <Spinner className="size-3.5" />
                Syncing…
              </>
            ) : (
              'Sync now'
            )}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => disconnect.mutate()}
            disabled={disconnect.isPending}
          >
            Disconnect
          </Button>
        </div>

        {synced && !sync.isPending && (
          <p className="mt-2 text-[12px] text-text-secondary">
            {synced.total === 0
              ? 'No events in the sync window.'
              : `${synced.created} new, ${synced.updated} updated.`}{' '}
            <span className="text-text-tertiary">
              Past events arrive without a transcript — a calendar has no recording.
            </span>
          </p>
        )}
        {sync.isError && (
          <div className="mt-2">
            <InlineError error={sync.error} />
          </div>
        )}
        {connection.last_sync_error && !sync.isError && (
          <p className="mt-2 text-[12px] text-amber-700">
            Last sync failed: {connection.last_sync_error}
          </p>
        )}
      </Card>
    )
  }

  const notConfigured = connection && !connection.is_configured

  return (
    <Card className={cx('mb-5 px-4 py-3', 'border-dashed bg-canvas')}>
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex size-8 items-center justify-center rounded-lg border border-line bg-surface text-text-tertiary">
          <Icon name="calendar" className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold text-ink">
            {notConfigured ? 'Calendar sync is not set up on this server' : 'Not connected'}
          </p>
          <p className="mt-0.5 text-[12px] leading-5 text-text-tertiary">
            {notConfigured
              ? 'Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to the API environment to enable it.'
              : 'Connect Google Calendar to pull your meetings in automatically.'}
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={() => connect.mutate()}
          disabled={connect.isPending || Boolean(notConfigured)}
        >
          {connect.isPending ? (
            <>
              <Spinner className="size-3.5" />
              Redirecting…
            </>
          ) : (
            <>
              <Icon name="plus" className="size-4" />
              Connect Calendar
            </>
          )}
        </Button>
      </div>

      {returned && (
        <p
          className={cx(
            'mt-2 text-[12px]',
            returned.tone === 'ok' ? 'text-emerald-700' : 'text-amber-700',
          )}
        >
          {returned.text}
          {reason && <span className="text-text-tertiary"> {reason}</span>}
        </p>
      )}
      {connect.isError && (
        <div className="mt-2">
          <InlineError error={connect.error} />
        </div>
      )}
    </Card>
  )
}
