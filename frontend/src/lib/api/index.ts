/**
 * The app's single entry point to the API.
 *
 * Import from `lib/api` - never from `lib/api/client` - so that axios, the
 * token store and the interceptors stay an implementation detail of this
 * folder.
 */
export { API_URL, api, tokens } from './client'
export { ApiError, errorMessage, toApiError } from './errors'
export type { ApiErrorKind, FieldErrors } from './errors'
export { queryKeys } from './queryKeys'

export { fetchHealth, fetchMe, login, logout, register } from './auth'
export {
  beginCalendarConnect,
  disconnectCalendar,
  getCalendarConnection,
  syncCalendar,
} from './calendar'
export {
  addParticipant,
  appendSegment,
  createHighlight,
  finishLiveMeeting,
  generateSummary,
  getActionItems,
  getHighlights,
  getMeeting,
  getMeetingStats,
  getTranscript,
  listActionItems,
  listHighlights,
  listMeetings,
  listMeetingsInRange,
  searchMeetings,
  startLiveMeeting,
  startMeetingRecording,
  updateActionItem,
} from './meetings'

export type * from './types'
