import { Link } from 'react-router-dom'

import Button from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import ErrorState from '../components/ui/ErrorState'
import Icon from '../components/ui/Icon'
import PageHeader from '../components/ui/PageHeader'
import Skeleton from '../components/ui/Skeleton'
import { PLATFORM_LABELS, formatClock, formatDateTime, pluralize } from '../lib/format'
import { cx, focusRing } from '../lib/cx'
import { useAllHighlights } from '../hooks/useWorkspace'
import type { HighlightWithMeeting } from '../lib/api'

function Row({ highlight }: { highlight: HighlightWithMeeting }) {
  const meeting = highlight.meeting
  return (
    <li>
      {/* Deep-links straight to the clip's meeting, on the Highlights tab. */}
      <Link
        to={`/meetings/${meeting.id}?tab=highlights`}
        className={cx('group flex gap-3 rounded-lg p-3 transition-colors duration-120',
          'hover:bg-ink/[0.02]', focusRing)}
      >
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
          <Icon name="highlights" className="size-3.5" />
        </span>

        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-ink group-hover:text-brand">
            {highlight.title}
          </p>
          {highlight.description && (
            <p className="mt-0.5 line-clamp-2 text-[13px] leading-5 text-text-tertiary">
              {highlight.description}
            </p>
          )}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-text-tertiary">
            <span className="truncate font-medium text-text-secondary">{meeting.title}</span>
            <span aria-hidden="true">·</span>
            <span className="tabular">
              {formatClock(highlight.start_ms)} – {formatClock(highlight.end_ms)}
            </span>
            <span aria-hidden="true">·</span>
            <span className="tabular">{Math.round(highlight.duration_ms / 1000)}s</span>
            <span aria-hidden="true">·</span>
            <span>{PLATFORM_LABELS[meeting.platform]}</span>
          </div>
        </div>

        <span className="tabular shrink-0 text-[12px] text-text-tertiary">
          {formatDateTime(meeting.started_at ?? meeting.scheduled_start)}
        </span>
      </Link>
    </li>
  )
}

export default function Highlights() {
  const highlights = useAllHighlights()
  const rows = highlights.items

  return (
    <>
      <PageHeader
        title="Highlights"
        description="Every moment clipped across your meetings."
      />

      {highlights.isPending ? (
        <Card className="p-2">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="flex gap-3 p-3">
              <Skeleton className="size-7 rounded-lg" />
              <div className="flex-1">
                <Skeleton className="h-3.5 w-56" />
                <Skeleton className="mt-2 h-3 w-72" />
              </div>
            </div>
          ))}
        </Card>
      ) : highlights.isError ? (
        <Card>
          <ErrorState
            error={highlights.error}
            onRetry={() => highlights.refetch()}
            title="Couldn't load highlights"
          />
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon="highlights"
            title="No highlights yet"
            description="Open a meeting, find something worth keeping, and clip it from the transcript."
          />
        </Card>
      ) : (
        <>
          <p className="mb-3 text-[13px] text-text-tertiary">
            {pluralize(highlights.total, 'highlight')}
          </p>
          <Card className="p-2">
            <ul className="divide-y divide-line">
              {rows.map((highlight) => (
                <Row key={highlight.id} highlight={highlight} />
              ))}
            </ul>
            {highlights.hasNextPage && (
              <div className="flex justify-center py-3">
                <Button
                  size="sm"
                  onClick={() => highlights.fetchNextPage()}
                  disabled={highlights.isFetchingNextPage}
                >
                  {highlights.isFetchingNextPage
                    ? 'Loading…'
                    : `Show more (${rows.length} of ${highlights.total})`}
                </Button>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  )
}
