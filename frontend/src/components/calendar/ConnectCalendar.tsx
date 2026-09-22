import Button from '../ui/Button'
import Icon from '../ui/Icon'
import { Card } from '../ui/Card'
import { Spinner } from '../ui/LoadingState'
import { cx } from '../../lib/cx'
import { useCalendarConnection } from '../../hooks/useCalendarConnection'

/**
 * The connection banner: not connected → connecting → connected.
 *
 * Deliberately says what it is rather than implying a real integration, since
 * the OAuth flow behind it is a stub for this build.
 */
export default function ConnectCalendar() {
  const { status, connect, disconnect, provider } = useCalendarConnection()

  if (status === 'connected') {
    return (
      <Card className="mb-5 flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="flex size-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
          <Icon name="calendar" className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold text-ink">
            {provider} connected
            <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
          </p>
          <p className="mt-0.5 text-[12px] text-text-tertiary">
            Scheduled calls appear here automatically.
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={disconnect}>
          Disconnect
        </Button>
      </Card>
    )
  }

  const isConnecting = status === 'connecting'

  return (
    <Card
      className={cx(
        'mb-5 flex flex-wrap items-center gap-3 px-4 py-3',
        'border-dashed bg-canvas',
      )}
    >
      <span className="flex size-8 items-center justify-center rounded-lg border border-line bg-surface text-text-tertiary">
        <Icon name="calendar" className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-ink">Not connected</p>
        <p className="mt-0.5 text-[12px] text-text-tertiary">
          Connect a calendar to pull scheduled meetings in automatically.
        </p>
      </div>
      <Button variant="primary" size="sm" onClick={connect} disabled={isConnecting}>
        {isConnecting ? (
          <>
            <Spinner className="size-3.5" />
            Connecting…
          </>
        ) : (
          <>
            <Icon name="plus" className="size-4" />
            Connect Calendar
          </>
        )}
      </Button>
    </Card>
  )
}
