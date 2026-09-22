import type { MeetingListItem } from '../../lib/api'
import { Card } from '../ui/Card'
import EmptyState from '../ui/EmptyState'
import ErrorState from '../ui/ErrorState'
import type { IconName } from '../ui/Icon'
import MeetingCard, { MeetingCardSkeleton } from './MeetingCard'

/**
 * A titled list of meeting cards that knows all four of its own states:
 * loading, failed, empty, and loaded.
 *
 * It takes `isPending` rather than `isLoading` deliberately. React Query's
 * `isLoading` is `isPending && isFetching`, which drops to false in the gap
 * between a failed attempt and its retry - long enough, with backoff, to flash
 * an empty state at the user before the error arrives. `isPending` stays true
 * until the query actually resolves.
 *
 * Keeping that decision here rather than in the page means every section
 * behaves identically, and the page reads as a description of what it shows
 * instead of a chain of conditionals.
 */
export default function MeetingSection({
  title,
  count,
  meetings,
  variant = 'recent',
  isPending,
  isError,
  error,
  onRetry,
  emptyIcon,
  emptyTitle,
  emptyDescription,
  skeletonCount = 3,
  action,
}: {
  title: string
  count?: number
  meetings: MeetingListItem[]
  variant?: 'recent' | 'upcoming'
  isPending: boolean
  isError: boolean
  error: unknown
  onRetry: () => void
  emptyIcon: IconName
  emptyTitle: string
  emptyDescription: string
  skeletonCount?: number
  action?: React.ReactNode
}) {
  return (
    <section className="mt-8 first:mt-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          {title}
          {!isPending && !isError && count !== undefined && (
            <span className="tabular rounded-md bg-ink/[0.05] px-1.5 py-0.5 text-[11px] font-medium text-text-tertiary">
              {count}
            </span>
          )}
        </h2>
        {action}
      </div>

      {isPending ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: skeletonCount }, (_, i) => (
            <MeetingCardSkeleton key={i} />
          ))}
        </div>
      ) : isError ? (
        <Card>
          <ErrorState error={error} onRetry={onRetry} title={`Couldn't load ${title.toLowerCase()}`} />
        </Card>
      ) : meetings.length === 0 ? (
        <Card>
          <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDescription} />
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {meetings.map((meeting) => (
            <MeetingCard key={meeting.id} meeting={meeting} variant={variant} />
          ))}
        </div>
      )}
    </section>
  )
}
