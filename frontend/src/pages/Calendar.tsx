import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Card } from '../components/ui/Card'
import Button from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import ErrorState from '../components/ui/ErrorState'
import Icon from '../components/ui/Icon'
import PageHeader from '../components/ui/PageHeader'
import Skeleton from '../components/ui/Skeleton'
import ConnectCalendar from '../components/calendar/ConnectCalendar'
import MonthGrid from '../components/calendar/MonthGrid'
import StatusPill from '../components/meetings/StatusPill'
import {
  PLATFORM_LABELS,
  formatDateTime,
  formatDuration,
  pluralize,
  relativeToNow,
} from '../lib/format'
import { buildWeeks, occursAt, startOfMonth } from '../lib/calendar'
import { cx, focusRing } from '../lib/cx'
import { useCalendarMeetings } from '../hooks/useWorkspace'
import type { MeetingListItem } from '../lib/api'

const MONTH_LABEL = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' })

function UpcomingRow({ meeting }: { meeting: MeetingListItem }) {
  return (
    <li>
      <Link
        to={`/meetings/${meeting.id}`}
        className={cx('group block rounded-lg p-3 transition-colors duration-120',
          'hover:bg-ink/[0.02]', focusRing)}
      >
        <div className="flex items-start justify-between gap-2">
          <p className="truncate text-[13px] font-semibold text-ink group-hover:text-brand">
            {meeting.title}
          </p>
          <StatusPill status={meeting.status} />
        </div>
        <p className="tabular mt-1 text-[12px] text-text-secondary">
          {formatDateTime(occursAt(meeting))}
          <span className="mx-1.5 text-text-tertiary" aria-hidden="true">·</span>
          {relativeToNow(meeting.scheduled_start)}
        </p>
        <p className="mt-0.5 text-[12px] text-text-tertiary">
          {meeting.duration_seconds ? `${formatDuration(meeting.duration_seconds)} · ` : ''}
          {pluralize(meeting.participant_count, 'participant')}
          <span className="mx-1.5" aria-hidden="true">·</span>
          {PLATFORM_LABELS[meeting.platform]}
        </p>
      </Link>
    </li>
  )
}

export default function Calendar() {
  const [month, setMonth] = useState(() => startOfMonth(new Date()))

  // The grid always draws six weeks, so the window has to cover the leading and
  // trailing days of neighbouring months that it shows.
  const range = useMemo(() => {
    const weeks = buildWeeks(month)
    const first = weeks[0][0]
    const last = weeks[5][6]
    return {
      occurs_after: new Date(first.getFullYear(), first.getMonth(), first.getDate()).toISOString(),
      occurs_before: new Date(
        last.getFullYear(), last.getMonth(), last.getDate(), 23, 59, 59,
      ).toISOString(),
      ordering: 'occurs_at',
    }
  }, [month])

  const monthMeetings = useCalendarMeetings(range)
  // Fetched separately from the grid: "what is next" should not change just
  // because someone paged back to look at last month.
  const upcoming = useCalendarMeetings({ status: 'scheduled', ordering: 'scheduled_start' })

  const meetings = monthMeetings.data?.results ?? []
  const isThisMonth = month.getTime() === startOfMonth(new Date()).getTime()

  function shiftMonth(by: number) {
    setMonth((current) => new Date(current.getFullYear(), current.getMonth() + by, 1))
  }

  return (
    <>
      <PageHeader
        title="Calendar"
        description="Your meetings by date, past and scheduled."
      />

      <ConnectCalendar />

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-[13px] font-semibold text-ink">{MONTH_LABEL.format(month)}</h2>
            <div className="flex items-center gap-1">
              <Button size="sm" variant="ghost" aria-label="Previous month"
                className="px-1.5" onClick={() => shiftMonth(-1)}>
                <Icon name="chevron-right" className="size-4 rotate-180" />
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setMonth(startOfMonth(new Date()))}
                disabled={isThisMonth}>
                Today
              </Button>
              <Button size="sm" variant="ghost" aria-label="Next month"
                className="px-1.5" onClick={() => shiftMonth(1)}>
                <Icon name="chevron-right" className="size-4" />
              </Button>
            </div>
          </div>

          {monthMeetings.isPending ? (
            <Skeleton className="h-[580px] w-full rounded-xl" />
          ) : monthMeetings.isError ? (
            <Card>
              <ErrorState
                error={monthMeetings.error}
                onRetry={() => monthMeetings.refetch()}
                title="Couldn't load the calendar"
              />
            </Card>
          ) : (
            <>
              <MonthGrid month={month} meetings={meetings} />
              <p className="mt-2 text-[12px] text-text-tertiary">
                {meetings.length === 0
                  ? 'Nothing this month.'
                  : `${pluralize(meetings.length, 'meeting')} this month.`}
              </p>
            </>
          )}
        </div>

        <div>
          <h2 className="mb-3 text-[13px] font-semibold text-ink">Upcoming</h2>
          {upcoming.isPending ? (
            <Card className="p-2">
              {Array.from({ length: 3 }, (_, i) => (
                <div key={i} className="p-3">
                  <Skeleton className="h-3.5 w-40" />
                  <Skeleton className="mt-2 h-3 w-32" />
                </div>
              ))}
            </Card>
          ) : upcoming.isError ? (
            <Card>
              <ErrorState
                error={upcoming.error}
                onRetry={() => upcoming.refetch()}
                title="Couldn't load upcoming"
              />
            </Card>
          ) : (upcoming.data?.results.length ?? 0) === 0 ? (
            <Card>
              <EmptyState
                icon="calendar"
                title="Nothing scheduled"
                description="Meetings you have coming up will be listed here."
              />
            </Card>
          ) : (
            <Card className="p-2">
              <ul className="divide-y divide-line">
                {upcoming.data?.results.map((meeting) => (
                  <UpcomingRow key={meeting.id} meeting={meeting} />
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
