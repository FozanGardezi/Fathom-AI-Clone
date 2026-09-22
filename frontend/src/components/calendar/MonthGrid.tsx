import { Link } from 'react-router-dom'

import type { MeetingListItem } from '../../lib/api'
import { PLATFORM_LABELS, formatDuration, pluralize } from '../../lib/format'
import { buildWeeks, dayKey, occursAt } from '../../lib/calendar'
import { cx, focusRing } from '../../lib/cx'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const TIME = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })

function DayCell({
  date,
  month,
  meetings,
}: {
  date: Date
  month: Date
  meetings: MeetingListItem[]
}) {
  const inMonth = date.getMonth() === month.getMonth()
  const isToday = dayKey(date) === dayKey(new Date())

  return (
    <div
      className={cx(
        'min-h-[92px] border-t border-l border-line p-1.5',
        !inMonth && 'bg-canvas/60',
      )}
    >
      <span
        className={cx(
          'tabular mb-1 inline-flex size-5 items-center justify-center rounded-full text-[11px]',
          isToday && 'bg-brand font-semibold text-white',
          !isToday && inMonth && 'text-text-secondary',
          !isToday && !inMonth && 'text-text-tertiary',
        )}
      >
        {date.getDate()}
      </span>

      <div className="space-y-1">
        {meetings.slice(0, 3).map((meeting) => {
          const when = occursAt(meeting)
          const isScheduled = meeting.status === 'scheduled'
          // A day cell is about eighty pixels wide. The title is what tells
          // one meeting from another, so it gets the space; the time, length,
          // attendees and platform go in the tooltip rather than competing
          // for room and leaving every chip reading "12:00 PM…".
          const tooltip = [
            meeting.title,
            when ? TIME.format(new Date(when)) : null,
            meeting.duration_seconds ? formatDuration(meeting.duration_seconds) : null,
            pluralize(meeting.participant_count, 'participant'),
            PLATFORM_LABELS[meeting.platform],
          ]
            .filter(Boolean)
            .join(' · ')

          return (
            <Link
              key={meeting.id}
              to={`/meetings/${meeting.id}`}
              title={tooltip}
              className={cx(
                'flex items-center gap-1 rounded px-1 py-0.5 text-[11px] leading-4',
                'transition-colors duration-120',
                focusRing,
                isScheduled
                  ? 'bg-brand-soft text-brand hover:bg-brand/15'
                  : 'bg-ink/[0.05] text-text-secondary hover:bg-ink/[0.09] hover:text-ink',
              )}
            >
              <span
                aria-hidden="true"
                className={cx(
                  'size-1 shrink-0 rounded-full',
                  isScheduled ? 'bg-brand' : 'bg-text-tertiary',
                )}
              />
              <span className="truncate">{meeting.title}</span>
            </Link>
          )
        })}
        {meetings.length > 3 && (
          <p className="px-1 text-[11px] text-text-tertiary">+{meetings.length - 3} more</p>
        )}
      </div>
    </div>
  )
}

export default function MonthGrid({
  month,
  meetings,
}: {
  month: Date
  meetings: MeetingListItem[]
}) {
  const weeks = buildWeeks(month)

  // Bucket once rather than filtering the list inside every one of the 42 cells.
  const byDay = new Map<string, MeetingListItem[]>()
  for (const meeting of meetings) {
    const when = occursAt(meeting)
    if (!when) continue
    const key = dayKey(new Date(when))
    const bucket = byDay.get(key)
    if (bucket) bucket.push(meeting)
    else byDay.set(key, [meeting])
  }

  return (
    <div className="overflow-hidden rounded-xl border-r border-b border-line bg-surface">
      <div className="grid grid-cols-7">
        {WEEKDAYS.map((day) => (
          <div
            key={day}
            className="border-l border-line bg-canvas px-2 py-1.5 text-[11px] font-semibold text-text-tertiary"
          >
            {day}
          </div>
        ))}
        {weeks.flat().map((date) => (
          <DayCell
            key={date.toISOString()}
            date={date}
            month={month}
            meetings={byDay.get(dayKey(date)) ?? []}
          />
        ))}
      </div>
    </div>
  )
}
