import { Card } from '../ui/Card'
import ErrorState from '../ui/ErrorState'
import { formatTotalTime } from '../../lib/format'
import { useMeetingStats } from '../../hooks/useMeetings'
import { StatCard, StatCardSkeleton } from './StatCard'

/**
 * The four headline numbers.
 *
 * They come from /meetings/stats/, which aggregates in SQL - summing a page of
 * the meetings list would silently describe only the first 25 meetings.
 */
export default function MeetingStats() {
  const stats = useMeetingStats()

  // isPending, not isLoading: see the note in MeetingSection.
  if (stats.isPending) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (stats.isError) {
    return (
      <Card>
        <ErrorState
          error={stats.error}
          onRetry={() => stats.refetch()}
          title="Couldn't load statistics"
        />
      </Card>
    )
  }

  const data = stats.data
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Total meetings" value={String(data?.total_meetings ?? 0)} icon="meetings" />
      <StatCard
        label="Meeting time"
        value={formatTotalTime(data?.total_duration_seconds ?? 0)}
        icon="calendar"
      />
      <StatCard
        label="Open action items"
        value={String(data?.open_action_items ?? 0)}
        icon="action-items"
      />
      <StatCard label="Highlights" value={String(data?.highlights ?? 0)} icon="highlights" />
    </div>
  )
}
