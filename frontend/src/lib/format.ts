import type { MeetingPlatform, MeetingStatus } from './api'

/** Morning until noon, afternoon until 18:00, evening after. */
export function greeting(now = new Date()) {
  const hour = now.getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

/** "Fozan Gardezi" -> "Fozan". Falls back to the part of an email before the
 *  @ so the greeting is never addressed to nobody. */
export function firstName(fullName?: string, email?: string) {
  const name = fullName?.trim().split(/\s+/)[0]
  if (name) return name
  return email?.split('@')[0] ?? 'there'
}

const TIME = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })
const DAY = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' })

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

/**
 * "Today, 2:30 PM" / "Tomorrow, 9:00 AM" / "Mon 15 Sep, 2:30 PM".
 *
 * Relative wording only within a day either side - past that, a weekday and
 * date is easier to place than counting "4 days ago".
 */
export function formatDateTime(iso: string | null) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  const days = Math.round((startOfDay(date) - startOfDay(new Date())) / 86_400_000)
  const prefix = days === 0 ? 'Today' : days === 1 ? 'Tomorrow' : days === -1 ? 'Yesterday' : null

  return `${prefix ?? DAY.format(date)}, ${TIME.format(date)}`
}

/** 2_700 -> "45m"; 3_900 -> "1h 5m". */
export function formatDuration(seconds: number | null) {
  if (seconds == null) return '—'
  const total = Math.round(seconds / 60)
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  if (!hours) return `${minutes}m`
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`
}

/** Same idea, but for a headline total where hours are the unit that matters. */
export function formatTotalTime(seconds: number | null) {
  if (!seconds) return '0h'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  if (!hours) return `${minutes}m`
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`
}

/** How far away the meeting is, for an upcoming card. */
export function relativeToNow(iso: string | null) {
  if (!iso) return ''
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60_000)
  if (minutes < 0) return 'Started'
  if (minutes < 60) return `in ${minutes}m`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `in ${hours}h`
  const days = Math.round(hours / 24)
  return days === 1 ? 'in 1 day' : `in ${days} days`
}

export const PLATFORM_LABELS: Record<MeetingPlatform, string> = {
  zoom: 'Zoom',
  google_meet: 'Google Meet',
  microsoft_teams: 'Microsoft Teams',
  upload: 'Upload',
  other: 'Other',
}

export const STATUS_LABELS: Record<MeetingStatus, string> = {
  scheduled: 'Scheduled',
  recording: 'Recording',
  processing: 'Processing',
  ready: 'Ready',
  failed: 'Failed',
}

/** Milliseconds as a player clock: "04:12", or "1:02:03" past an hour. */
export function formatClock(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return hours ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${pad(minutes)}:${pad(seconds)}`
}

/** The inverse, for the highlight form. Accepts "4:12" or "1:02:03"; returns
 *  null for anything it cannot read, so the caller can reject it. */
export function parseClock(value: string): number | null {
  const parts = value.trim().split(':')
  if (parts.length < 2 || parts.length > 3) return null
  if (parts.some((part) => part === '' || !/^\d+$/.test(part))) return null
  const numbers = parts.map(Number)
  const [hours, minutes, seconds] =
    numbers.length === 3 ? numbers : [0, numbers[0], numbers[1]]
  if (minutes > 59 || seconds > 59) return null
  return ((hours * 60 + minutes) * 60 + seconds) * 1000
}

/** "Ada Lovelace" -> "AL"; "Bob" -> "B". */
export function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0][0].toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function pluralize(count: number, word: string, plural = `${word}s`) {
  return `${count} ${count === 1 ? word : plural}`
}
