import type { CalendarParams, ListActionItemsParams, ListMeetingsParams, PageParams } from './types'

/**
 * Cache keys, in one place.
 *
 * Nesting them under a shared prefix is what makes coarse invalidation work:
 * invalidating `queryKeys.meetings.all` after a mutation clears every list,
 * detail, transcript and highlight query in one call, without each hook having
 * to know what else might be stale.
 */
export const queryKeys = {
  me: ['me'] as const,
  health: ['health'] as const,

  /** Everything across the workspace, as opposed to within one meeting. */
  workspace: {
    all: ['workspace'] as const,
    highlights: (params: PageParams = {}) => ['workspace', 'highlights', params] as const,
    actionItems: (params: ListActionItemsParams = {}) =>
      ['workspace', 'action-items', params] as const,
    calendar: (params: CalendarParams) => ['workspace', 'calendar', params] as const,
  },

  meetings: {
    all: ['meetings'] as const,
    stats: ['meetings', 'stats'] as const,
    list: (params: ListMeetingsParams = {}) => ['meetings', 'list', params] as const,
    search: (query: string, params: ListMeetingsParams = {}) =>
      ['meetings', 'search', query, params] as const,
    detail: (id: string) => ['meetings', 'detail', id] as const,
    transcript: (id: string, params: PageParams = {}) =>
      ['meetings', 'detail', id, 'transcript', params] as const,
    /** The whole transcript, paged in. Separate from `transcript` so the two
     *  do not share a cache entry with different shapes. */
    transcriptAll: (id: string) => ['meetings', 'detail', id, 'transcript', 'all'] as const,
    actionItems: (id: string, params: PageParams = {}) =>
      ['meetings', 'detail', id, 'action-items', params] as const,
    highlights: (id: string, params: PageParams = {}) =>
      ['meetings', 'detail', id, 'highlights', params] as const,
  },
}
