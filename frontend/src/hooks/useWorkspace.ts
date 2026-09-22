/**
 * Hooks for the workspace-wide sections: Highlights, Action Items, Calendar.
 *
 * These read across every meeting the caller can see, which is a different
 * question from the per-meeting hooks in useMeetings.ts - hence separate
 * endpoints and separate cache keys.
 */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseQueryResult } from '@tanstack/react-query'

import {
  ApiError,
  errorMessage,
  listActionItems,
  listHighlights,
  listMeetingsInRange,
  queryKeys,
  updateActionItem,
} from '../lib/api'
import type {
  ActionItemWithMeeting,
  CalendarParams,
  HighlightWithMeeting,
  ListActionItemsParams,
  MeetingListItem,
  PageParams,
  Paginated,
  UpdateActionItemInput,
} from '../lib/api'

type Result<T> = UseQueryResult<T, ApiError> & { message: string }

function withMessage<T>(result: UseQueryResult<T, ApiError>): Result<T> {
  return Object.assign(result, { message: errorMessage(result.error) })
}

/**
 * Workspace lists page at 25 with no page-size parameter, so a list of any
 * size has to be paged in. An infinite query keeps the pages in one cache
 * entry and lets the page append rather than replace - without this, an
 * account with more than 25 follow-ups would silently never see the rest.
 */
function paged<T>(query: ReturnType<typeof useInfiniteQuery<Paginated<T>, ApiError>>) {
  return Object.assign(query, {
    items: query.data?.pages.flatMap((page) => page.results) ?? [],
    total: query.data?.pages[0]?.count ?? 0,
    message: errorMessage(query.error),
  })
}

export function useAllHighlights(params: PageParams = {}) {
  return paged(
    useInfiniteQuery<Paginated<HighlightWithMeeting>, ApiError>({
      queryKey: queryKeys.workspace.highlights(params),
      queryFn: ({ pageParam, signal }) =>
        listHighlights({ ...params, page: pageParam as number }, signal),
      initialPageParam: 1,
      getNextPageParam: (lastPage, allPages) => (lastPage.next ? allPages.length + 1 : undefined),
    }),
  )
}

export function useAllActionItems(params: ListActionItemsParams = {}) {
  return paged(
    useInfiniteQuery<Paginated<ActionItemWithMeeting>, ApiError>({
      queryKey: queryKeys.workspace.actionItems(params),
      queryFn: ({ pageParam, signal }) =>
        listActionItems({ ...params, page: pageParam as number }, signal),
      initialPageParam: 1,
      getNextPageParam: (lastPage, allPages) => (lastPage.next ? allPages.length + 1 : undefined),
    }),
  )
}

/** Meetings inside a date window, for the calendar grid. */
export function useCalendarMeetings(params: CalendarParams): Result<Paginated<MeetingListItem>> {
  return withMessage(
    useQuery({
      queryKey: queryKeys.workspace.calendar(params),
      queryFn: ({ signal }) => listMeetingsInRange(params, signal),
    }),
  )
}

/**
 * Complete or reopen an item from the workspace list.
 *
 * Separate from the per-meeting mutation because the caches to refresh are
 * different: this one invalidates the workspace lists and the dashboard
 * statistics, which both count open items.
 */
export function useToggleActionItem() {
  const queryClient = useQueryClient()

  const result = useMutation<
    ActionItemWithMeeting,
    ApiError,
    { id: string; patch: UpdateActionItemInput }
  >({
    mutationFn: ({ id, patch }) =>
      updateActionItem(id, patch) as Promise<ActionItemWithMeeting>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspace.all })
      // The dashboard's "open action items" figure is now stale.
      queryClient.invalidateQueries({ queryKey: queryKeys.meetings.stats })
    },
  })

  return Object.assign(result, { message: errorMessage(result.error) })
}
