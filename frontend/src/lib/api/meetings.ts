/**
 * Every call the app makes against the meetings API.
 *
 * Components and hooks call these; nothing outside this folder imports axios.
 * Each function takes plain arguments, returns a typed response, and throws an
 * ApiError - the client interceptor guarantees the error shape.
 */
import { api } from './client'
import type {
  ActionItem,
  AddParticipantInput,
  AppendSegmentInput,
  ActionItemWithMeeting,
  CalendarParams,
  CreateHighlightInput,
  GenerateSummaryInput,
  Highlight,
  HighlightWithMeeting,
  ListActionItemsParams,
  ListMeetingsParams,
  Meeting,
  MeetingListItem,
  MeetingStats,
  MeetingSummary,
  PageParams,
  Paginated,
  Participant,
  StartLiveMeetingInput,
  TranscriptSegment,
  UpdateActionItemInput,
} from './types'

/**
 * Meetings are namespaced under /v1; auth and health are not, so the axios
 * base stays at /api and versioned paths are built here.
 */
const V1 = '/v1'

/** GET /api/v1/meetings/ */
export async function listMeetings(
  params: ListMeetingsParams = {},
  signal?: AbortSignal,
): Promise<Paginated<MeetingListItem>> {
  const { data } = await api.get(`${V1}/meetings/`, { params, signal })
  return data
}

/** GET /api/v1/meetings/ within a date window, for the calendar. Kept
 *  separate from `listMeetings` so the calendar's intent reads at the call
 *  site rather than being buried in params. */
export async function listMeetingsInRange(
  params: CalendarParams,
  signal?: AbortSignal,
): Promise<Paginated<MeetingListItem>> {
  const { data } = await api.get(`${V1}/meetings/`, { params, signal })
  return data
}

/** GET /api/v1/highlights/ - every highlight across the workspace. */
export async function listHighlights(
  params: PageParams = {},
  signal?: AbortSignal,
): Promise<Paginated<HighlightWithMeeting>> {
  const { data } = await api.get(`${V1}/highlights/`, { params, signal })
  return data
}

/** GET /api/v1/action-items/ - every follow-up across the workspace. */
export async function listActionItems(
  params: ListActionItemsParams = {},
  signal?: AbortSignal,
): Promise<Paginated<ActionItemWithMeeting>> {
  const { data } = await api.get(`${V1}/action-items/`, { params, signal })
  return data
}

// ------------------------------------------------------------------ live

/** POST /api/v1/meetings/live/ - opens a recording and returns the meeting
 *  already in `recording` state, cast included. */
export async function startLiveMeeting(input: StartLiveMeetingInput): Promise<Meeting> {
  const { data } = await api.post(`${V1}/meetings/live/`, input)
  return data
}

/** POST /api/v1/meetings/{id}/transcript/ - append one utterance. */
export async function appendSegment(
  meetingId: string,
  input: AppendSegmentInput,
): Promise<TranscriptSegment> {
  const { data } = await api.post(`${V1}/meetings/${meetingId}/transcript/`, input)
  return data
}

/** POST /api/v1/meetings/{id}/participants/ - someone joined late. */
export async function addParticipant(
  meetingId: string,
  input: AddParticipantInput,
): Promise<Participant> {
  const { data } = await api.post(`${V1}/meetings/${meetingId}/participants/`, input)
  return data
}

/** POST /api/v1/meetings/{id}/start/ - connect the notetaker to a meeting that
 *  already exists (typically a calendar-synced one), moving it into recording
 *  and returning the full detail shape. */
export async function startMeetingRecording(meetingId: string): Promise<Meeting> {
  const { data } = await api.post(`${V1}/meetings/${meetingId}/start/`, {})
  return data
}

/** POST /api/v1/meetings/{id}/finish/ - close the recording and derive the
 *  summary, decisions, action items and highlights from the transcript. */
export async function finishLiveMeeting(meetingId: string): Promise<Meeting> {
  const { data } = await api.post(`${V1}/meetings/${meetingId}/finish/`, {})
  return data
}

/** POST /api/v1/meetings/{id}/summaries/ - (re)generate the summary under one
 *  template. Returns just that summary; the caller refetches the meeting to
 *  pick up the new row alongside the others. */
export async function generateSummary(
  meetingId: string,
  input: GenerateSummaryInput,
): Promise<MeetingSummary> {
  const { data } = await api.post(`${V1}/meetings/${meetingId}/summaries/`, input)
  return data
}

/** GET /api/v1/meetings/stats/ - workspace totals, aggregated server-side so
 *  they describe every meeting rather than the page we happened to fetch. */
export async function getMeetingStats(signal?: AbortSignal): Promise<MeetingStats> {
  const { data } = await api.get(`${V1}/meetings/stats/`, { signal })
  return data
}

/** GET /api/v1/meetings/{id}/ - includes participants, summary, topics,
 *  decisions, action items and highlights in one response. */
export async function getMeeting(id: string, signal?: AbortSignal): Promise<Meeting> {
  const { data } = await api.get(`${V1}/meetings/${id}/`, { signal })
  return data
}

/** GET /api/v1/meetings/{id}/transcript/ - segments in chronological order. */
export async function getTranscript(
  meetingId: string,
  params: PageParams = {},
  signal?: AbortSignal,
): Promise<Paginated<TranscriptSegment>> {
  const { data } = await api.get(`${V1}/meetings/${meetingId}/transcript/`, { params, signal })
  return data
}

/** GET /api/v1/meetings/{id}/action-items/ */
export async function getActionItems(
  meetingId: string,
  params: PageParams = {},
  signal?: AbortSignal,
): Promise<Paginated<ActionItem>> {
  const { data } = await api.get(`${V1}/meetings/${meetingId}/action-items/`, { params, signal })
  return data
}

/** PATCH /api/v1/action-items/{id}/ - completing, reopening, retitling,
 *  reassigning and re-dating all go through here. */
export async function updateActionItem(
  actionItemId: string,
  patch: UpdateActionItemInput,
): Promise<ActionItem> {
  const { data } = await api.patch(`${V1}/action-items/${actionItemId}/`, patch)
  return data
}

/** GET /api/v1/meetings/{id}/highlights/ */
export async function getHighlights(
  meetingId: string,
  params: PageParams = {},
  signal?: AbortSignal,
): Promise<Paginated<Highlight>> {
  const { data } = await api.get(`${V1}/meetings/${meetingId}/highlights/`, { params, signal })
  return data
}

/** POST /api/v1/meetings/{id}/highlights/ - the author comes from the token. */
export async function createHighlight(
  meetingId: string,
  input: CreateHighlightInput,
): Promise<Highlight> {
  const { data } = await api.post(`${V1}/meetings/${meetingId}/highlights/`, input)
  return data
}

/**
 * Search meetings by title.
 *
 * NOTE: the backend has no search endpoint yet - the meetings list accepts
 * `status` and `type` but not a text query, and DRF ignores parameters it does
 * not know, so sending `?search=` would quietly return everything. Until the
 * server side lands this filters the page it fetched, client-side.
 *
 * That has a real limitation worth knowing: it only sees the page it asked
 * for, so a match on page three of an unfiltered list will not be found. It is
 * a stopgap so the UI can be built against the final signature, not a search
 * implementation.
 *
 * To switch over: delete the filter block below and pass `search: query`
 * through to `params`. The signature does not change.
 */
export async function searchMeetings(
  query: string,
  params: ListMeetingsParams = {},
  signal?: AbortSignal,
): Promise<Paginated<MeetingListItem>> {
  const page = await listMeetings(params, signal)

  const needle = query.trim().toLowerCase()
  if (!needle) return page

  // --- remove once the API filters server-side -----------------------------
  const results = page.results.filter((meeting) =>
    meeting.title.toLowerCase().includes(needle),
  )
  return {
    ...page,
    results,
    // `count` must describe what the caller actually received, otherwise
    // pagination controls would offer pages that do not exist.
    count: results.length,
    next: null,
    previous: null,
  }
  // -------------------------------------------------------------------------
}
