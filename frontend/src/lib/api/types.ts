/**
 * Response shapes, mirroring the DRF serializers in apps/meetings/serializers.py.
 *
 * These are hand-written rather than generated: the API has a published
 * OpenAPI schema at /api/schema/, so if this drifts, generating from that is
 * the fix rather than guessing here.
 */

export type MeetingPlatform = 'zoom' | 'google_meet' | 'microsoft_teams' | 'upload' | 'other'
export type MeetingStatus = 'scheduled' | 'recording' | 'processing' | 'ready' | 'failed'
export type ParticipantRole = 'host' | 'cohost' | 'attendee'
export type SummaryTemplate =
  | 'general'
  | 'action_items'
  | 'sales_call'
  | 'one_on_one'
  | 'standup'
  | 'interview'
  | 'custom'
export type SummaryStatus = 'pending' | 'generating' | 'ready' | 'failed'

/** DRF's PageNumberPagination envelope. */
export type Paginated<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type User = {
  id: string
  email: string
  full_name: string
  avatar_url: string
  timezone: string
  created_at: string
}

export type Participant = {
  id: string
  display_name: string
  email: string
  role: ParticipantRole
  is_host: boolean
  joined_at: string | null
  left_at: string | null
  talk_time_seconds: number
}

export type MeetingSummary = {
  id: string
  template: SummaryTemplate
  status: SummaryStatus
  summary: string
  generated_at: string | null
}

export type ActionItem = {
  id: string
  owner: Participant | null
  title: string
  description: string
  due_date: string | null
  completed: boolean
  completed_at: string | null
  is_overdue: boolean
  created_at: string
}

export type Highlight = {
  id: string
  title: string
  description: string
  start_ms: number
  end_ms: number
  timestamp: string
  duration_ms: number
  created_by: User | null
  created_at: string
}

/** Enough of a meeting to label and link to it, as carried by the
 *  workspace-wide highlight and action-item lists. */
export type MeetingRef = {
  id: string
  title: string
  platform: MeetingPlatform
  status: MeetingStatus
  started_at: string | null
  scheduled_start: string | null
}

export type HighlightWithMeeting = Highlight & { meeting: MeetingRef }
export type ActionItemWithMeeting = ActionItem & { meeting: MeetingRef }

export type TranscriptSegment = {
  /** Segments use an auto id, not a UUID - there are millions of them. */
  id: number
  speaker: Participant | null
  /** Raw diarisation label, kept when the voice is not matched to a person. */
  speaker_label: string
  start_seconds: number
  end_seconds: number
  /** Pre-formatted mm:ss (or h:mm:ss) offset. */
  timestamp: string
  text: string
  confidence: number | null
}

/** Row shape from GET /meetings/ - metadata and counts, no related objects. */
export type MeetingListItem = {
  id: string
  title: string
  platform: MeetingPlatform
  status: MeetingStatus
  language: string
  owner: User
  scheduled_start: string | null
  started_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  is_live: boolean
  participant_count: number
  action_item_count: number
  /** First ~180 characters of the ready summary; "" when there is not one. */
  summary_excerpt: string
  created_at: string
  updated_at: string
}

/** Totals across every meeting the caller can see. */
export type MeetingStats = {
  total_meetings: number
  total_duration_seconds: number
  open_action_items: number
  highlights: number
}

/** Full shape from GET /meetings/{id}/. */
export type Meeting = {
  id: string
  title: string
  platform: MeetingPlatform
  status: MeetingStatus
  language: string
  external_id: string
  meeting_url: string
  owner: User
  scheduled_start: string | null
  started_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  is_live: boolean
  participants: Participant[]
  summary: MeetingSummary | null
  topics: string[]
  decisions: string[]
  action_items: ActionItem[]
  highlights: Highlight[]
  created_at: string
  updated_at: string
}

// ----------------------------------------------------------------- requests

export type ListMeetingsParams = {
  page?: number
  /** Any of started_at, scheduled_start, created_at, updated_at, title; prefix
   *  with `-` to reverse. */
  ordering?: string
  status?: MeetingStatus
  /** Server-side alias for `platform`. */
  type?: MeetingPlatform
}

export type PageParams = {
  page?: number
}

export type ListActionItemsParams = PageParams & {
  completed?: boolean
}

/** Window for the calendar. Both bounds compare against the meeting's
 *  occurrence - when it happened, or when it is due to. */
export type CalendarParams = ListMeetingsParams & {
  occurs_after?: string
  occurs_before?: string
}

export type UpdateActionItemInput = {
  title?: string
  description?: string
  due_date?: string | null
  /** Toggling this writes `completed_at` on the server - do not send it. */
  completed?: boolean
  /** A participant id from the same meeting, or null to unassign. */
  owner?: string | null
}

export type CreateHighlightInput = {
  title: string
  description?: string
  start_ms: number
  end_ms: number
}
