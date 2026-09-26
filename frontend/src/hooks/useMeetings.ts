/**
 * Data hooks for the meetings API.
 *
 * Each one wraps a function from `lib/api` in react-query and returns the
 * standard result plus a `message` string that is ready to render. Components
 * read `isLoading` / `isError` / `message` and never touch axios, status codes
 * or error shapes.
 */
import { useEffect, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query'

import {
  ApiError,
  createHighlight,
  errorMessage,
  getActionItems,
  getHighlights,
  getMeeting,
  getMeetingStats,
  getTranscript,
  listMeetings,
  queryKeys,
  searchMeetings,
  updateActionItem,
} from '../lib/api'
import type {
  ActionItem,
  CreateHighlightInput,
  Highlight,
  ListMeetingsParams,
  Meeting,
  MeetingListItem,
  MeetingStats,
  PageParams,
  Paginated,
  TranscriptSegment,
  UpdateActionItemInput,
} from '../lib/api'

/** What every query hook here returns: the react-query result, narrowed to
 *  ApiError, plus the sentence to show if it failed. */
export type ApiQueryResult<T> = UseQueryResult<T, ApiError> & { message: string }

function withMessage<T>(result: UseQueryResult<T, ApiError>): ApiQueryResult<T> {
  return Object.assign(result, { message: errorMessage(result.error) })
}

export function useMeetings(params: ListMeetingsParams = {}): ApiQueryResult<Paginated<MeetingListItem>> {
  return withMessage(
    useQuery({
      queryKey: queryKeys.meetings.list(params),
      // `signal` comes from react-query and aborts the request when the
      // component unmounts or the key changes.
      queryFn: ({ signal }) => listMeetings(params, signal),
    }),
  )
}

/** How early a scheduled call shows a join prompt, and how long past its start
 *  it keeps showing one - a meeting nobody joined on time is still joinable. */
const JOIN_LEAD_MINUTES = 15
const JOIN_GRACE_MINUTES = 60

/** Whether a Google Meet call is one the notetaker can join right now: either
 *  already recording, or scheduled to start within the window around now. */
function isJoinableNow(meeting: MeetingListItem, now: number): boolean {
  if (meeting.platform !== 'google_meet') return false
  if (meeting.status === 'recording') return true
  if (meeting.status !== 'scheduled' || !meeting.scheduled_start) return false
  const minutes = (new Date(meeting.scheduled_start).getTime() - now) / 60_000
  return minutes <= JOIN_LEAD_MINUTES && minutes >= -JOIN_GRACE_MINUTES
}

/**
 * Google Meet calls the notetaker can join at this moment.
 *
 * Two queries - the scheduled calls that are about to start, and the ones
 * already recording - merged and filtered to the join window. The result
 * drives the "live now" prompt; it is empty far more often than not, so the
 * banner renders nothing rather than reserving space.
 */
export function useLiveNow(): { meetings: MeetingListItem[]; isPending: boolean } {
  const scheduled = useMeetings({ status: 'scheduled', ordering: 'scheduled_start' })
  const recording = useMeetings({ status: 'recording', ordering: 'scheduled_start' })

  // A ticking clock rather than Date.now() in render: it keeps the check pure
  // and, as a bonus, flips a scheduled call into the prompt when its start time
  // arrives without waiting for a refetch.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(timer)
  }, [])

  const seen = new Set<string>()
  const meetings = [
    ...(recording.data?.results ?? []),
    ...(scheduled.data?.results ?? []),
  ].filter((meeting) => {
    if (seen.has(meeting.id) || !isJoinableNow(meeting, now)) return false
    seen.add(meeting.id)
    return true
  })

  return { meetings, isPending: scheduled.isPending || recording.isPending }
}

export function useMeetingStats(): ApiQueryResult<MeetingStats> {
  return withMessage(
    useQuery({
      queryKey: queryKeys.meetings.stats,
      queryFn: ({ signal }) => getMeetingStats(signal),
    }),
  )
}

export function useMeeting(id: string | undefined): ApiQueryResult<Meeting> {
  return withMessage(
    useQuery({
      queryKey: queryKeys.meetings.detail(id ?? ''),
      queryFn: ({ signal }) => getMeeting(id as string, signal),
      // Route params are `string | undefined` until the route matches.
      enabled: Boolean(id),
    }),
  )
}

export function useTranscript(
  meetingId: string | undefined,
  params: PageParams = {},
): ApiQueryResult<Paginated<TranscriptSegment>> {
  return withMessage(
    useQuery({
      queryKey: queryKeys.meetings.transcript(meetingId ?? '', params),
      queryFn: ({ signal }) => getTranscript(meetingId as string, params, signal),
      enabled: Boolean(meetingId),
    }),
  )
}

/**
 * The whole transcript, one page at a time.
 *
 * The API paginates at 25 segments and does not accept a page size, so a
 * 40-minute call is several pages. An infinite query keeps them in one cache
 * entry and lets the UI append rather than replace, which is what a transcript
 * reader needs - the earlier lines must stay put while more arrive.
 */
export function useTranscriptPages(meetingId: string | undefined) {
  const query = useInfiniteQuery({
    queryKey: queryKeys.meetings.transcriptAll(meetingId ?? ''),
    queryFn: ({ pageParam, signal }) =>
      getTranscript(meetingId as string, { page: pageParam }, signal),
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.next ? allPages.length + 1 : undefined,
    enabled: Boolean(meetingId),
  })

  return Object.assign(query, {
    segments: query.data?.pages.flatMap((page) => page.results) ?? [],
    total: query.data?.pages[0]?.count ?? 0,
    message: errorMessage(query.error),
  })
}

export function useActionItems(
  meetingId: string | undefined,
  params: PageParams = {},
): ApiQueryResult<Paginated<ActionItem>> {
  return withMessage(
    useQuery({
      queryKey: queryKeys.meetings.actionItems(meetingId ?? '', params),
      queryFn: ({ signal }) => getActionItems(meetingId as string, params, signal),
      enabled: Boolean(meetingId),
    }),
  )
}

export function useHighlights(
  meetingId: string | undefined,
  params: PageParams = {},
): ApiQueryResult<Paginated<Highlight>> {
  return withMessage(
    useQuery({
      queryKey: queryKeys.meetings.highlights(meetingId ?? '', params),
      queryFn: ({ signal }) => getHighlights(meetingId as string, params, signal),
      enabled: Boolean(meetingId),
    }),
  )
}

/**
 * Title search.
 *
 * Idle below two characters: one letter matches most things and the request
 * would be wasted. Debouncing the input belongs to the component that owns the
 * text field, not here.
 */
export function useSearchMeetings(
  query: string,
  params: ListMeetingsParams = {},
): ApiQueryResult<Paginated<MeetingListItem>> {
  const trimmed = query.trim()
  return withMessage(
    useQuery({
      queryKey: queryKeys.meetings.search(trimmed, params),
      queryFn: ({ signal }) => searchMeetings(trimmed, params, signal),
      enabled: trimmed.length >= 2,
    }),
  )
}

// ---------------------------------------------------------------- mutations

export type ApiMutationResult<TData, TVars> = UseMutationResult<TData, ApiError, TVars> & {
  message: string
}

/**
 * Update an action item - complete, reopen, retitle, reassign or re-date.
 *
 * On success it patches the item into every cached list it appears in, then
 * invalidates the meeting so derived values the server owns (`is_overdue`,
 * `completed_at`, the detail response's copy) come back authoritative rather
 * than being guessed at here.
 */
export function useUpdateActionItem(
  meetingId?: string,
): ApiMutationResult<ActionItem, { id: string; patch: UpdateActionItemInput }> {
  const queryClient = useQueryClient()

  const result = useMutation<ActionItem, ApiError, { id: string; patch: UpdateActionItemInput }>({
    mutationFn: ({ id, patch }) => updateActionItem(id, patch),
    onSuccess: (updated) => {
      queryClient.setQueriesData<Paginated<ActionItem>>(
        { queryKey: queryKeys.meetings.all },
        (page) =>
          page?.results?.some((item) => item.id === updated.id)
            ? {
                ...page,
                results: page.results.map((item) =>
                  item.id === updated.id ? updated : item,
                ),
              }
            : page,
      )
      if (meetingId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.meetings.detail(meetingId) })
      }
    },
  })

  return Object.assign(result, { message: errorMessage(result.error) })
}

/** Create a highlight on a meeting. */
export function useCreateHighlight(
  meetingId: string | undefined,
): ApiMutationResult<Highlight, CreateHighlightInput> {
  const queryClient = useQueryClient()

  const result = useMutation<Highlight, ApiError, CreateHighlightInput>({
    mutationFn: (input) => createHighlight(meetingId as string, input),
    onSuccess: () => {
      // A new row shifts pagination, so refetch rather than splice.
      if (meetingId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.meetings.detail(meetingId) })
      }
    },
  })

  return Object.assign(result, { message: errorMessage(result.error) })
}
