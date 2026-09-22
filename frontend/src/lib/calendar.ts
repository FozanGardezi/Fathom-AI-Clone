import type { MeetingListItem } from './api'

/** When a meeting sits on the calendar: when it happened, or when it is due to.
 *  Mirrors the backend's `occurs_at` annotation. */
export function occursAt(meeting: MeetingListItem) {
  return meeting.started_at ?? meeting.scheduled_start
}

export function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

export function dayKey(date: Date) {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}

/**
 * The six-week grid for a month.
 *
 * Always six rows: some months need them, and a fixed height means the page
 * does not jump as you page between months.
 */
export function buildWeeks(month: Date) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1)
  // Monday-first, so getDay()'s Sunday-as-0 has to be rotated.
  const lead = (first.getDay() + 6) % 7
  const start = new Date(first)
  start.setDate(first.getDate() - lead)

  return Array.from({ length: 6 }, (_, week) =>
    Array.from({ length: 7 }, (_, day) => {
      const date = new Date(start)
      date.setDate(start.getDate() + week * 7 + day)
      return date
    }),
  )
}
