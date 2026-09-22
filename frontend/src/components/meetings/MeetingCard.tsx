import { Link } from 'react-router-dom'

import type { MeetingListItem } from '../../lib/api'
import {
  PLATFORM_LABELS,
  formatDateTime,
  formatDuration,
  pluralize,
  relativeToNow,
} from '../../lib/format'
import { Card } from '../ui/Card'
import Icon from '../ui/Icon'
import Skeleton from '../ui/Skeleton'
import { cx, focusRing } from '../../lib/cx'
import StatusPill from './StatusPill'

/**
 * One meeting, as a card linking to its detail page.
 *
 * The whole card is the link rather than a title anchor inside it - a bigger
 * target, and one hover state instead of two competing ones.
 *
 * `variant="upcoming"` swaps the metadata for what matters before a call: how
 * soon it starts and how long it is booked for, instead of a summary that does
 * not exist yet.
 */
export default function MeetingCard({
  meeting,
  variant = 'recent',
}: {
  meeting: MeetingListItem
  variant?: 'recent' | 'upcoming'
}) {
  const isUpcoming = variant === 'upcoming'
  const when = isUpcoming ? meeting.scheduled_start : meeting.started_at

  return (
    <Link to={`/meetings/${meeting.id}`} className={cx('group block rounded-xl', focusRing)}>
      <Card className="h-full p-4 transition-colors duration-120 group-hover:border-line-strong">
        <div className="flex items-start justify-between gap-3">
          <h3 className="truncate text-[14px] font-semibold text-ink group-hover:text-brand">
            {meeting.title}
          </h3>
          <StatusPill status={meeting.status} />
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-text-tertiary">
          <span className="tabular">{formatDateTime(when)}</span>
          <span aria-hidden="true">·</span>
          {/* A meeting that has not happened has no measured duration - the
              model stores scheduled_start but no scheduled end - so the useful
              number before a call is how soon it starts. */}
          <span className="tabular">
            {isUpcoming
              ? relativeToNow(meeting.scheduled_start)
              : formatDuration(meeting.duration_seconds)}
          </span>
          <span aria-hidden="true">·</span>
          <span>{pluralize(meeting.participant_count, 'participant')}</span>
          <span aria-hidden="true">·</span>
          <span>{PLATFORM_LABELS[meeting.platform]}</span>
        </div>

        {meeting.summary_excerpt ? (
          <p className="mt-2.5 line-clamp-2 text-[13px] leading-5 text-text-secondary">
            {meeting.summary_excerpt}
          </p>
        ) : (
          <p className="mt-2.5 text-[13px] leading-5 text-text-tertiary italic">
            {isUpcoming ? 'Not started yet.' : 'No summary generated yet.'}
          </p>
        )}

        {meeting.action_item_count > 0 && (
          <div className="mt-3 flex items-center gap-1.5 border-t border-line pt-3 text-[12px] text-text-tertiary">
            <Icon name="action-items" className="size-3.5" />
            {pluralize(meeting.action_item_count, 'action item')}
          </div>
        )}
      </Card>
    </Link>
  )
}

export function MeetingCardSkeleton() {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-3.5 w-16" />
      </div>
      <Skeleton className="mt-3 h-3 w-64" />
      <Skeleton className="mt-3 h-3 w-full" />
      <Skeleton className="mt-1.5 h-3 w-3/4" />
    </Card>
  )
}
