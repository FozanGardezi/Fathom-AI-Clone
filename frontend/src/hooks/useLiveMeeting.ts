/** Hooks for the live-call lifecycle: start, append, finish. */
import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  ApiError,
  addParticipant,
  appendSegment,
  errorMessage,
  finishLiveMeeting,
  generateSummary,
  queryKeys,
  startLiveMeeting,
  startMeetingRecording,
} from '../lib/api'
import type {
  AddParticipantInput,
  AppendSegmentInput,
  GenerateSummaryInput,
  Meeting,
  MeetingSummary,
  Participant,
  StartLiveMeetingInput,
  TranscriptSegment,
} from '../lib/api'

export function useStartLiveMeeting() {
  const queryClient = useQueryClient()
  const result = useMutation<Meeting, ApiError, StartLiveMeetingInput>({
    mutationFn: startLiveMeeting,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.workspace.all })
    },
  })
  return Object.assign(result, { message: errorMessage(result.error) })
}

/**
 * Connect the notetaker to a meeting that already exists - a calendar-synced
 * call being joined. Moves it into recording and returns the detail shape, so
 * the caller can navigate straight to the live page.
 */
export function useStartMeetingRecording() {
  const queryClient = useQueryClient()
  const result = useMutation<Meeting, ApiError, string>({
    mutationFn: (meetingId) => startMeetingRecording(meetingId),
    onSuccess: (meeting) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.workspace.all })
      queryClient.setQueryData(queryKeys.meetings.detail(meeting.id), meeting)
    },
  })
  return Object.assign(result, { message: errorMessage(result.error) })
}

/**
 * Append one utterance.
 *
 * Deliberately does not invalidate anything: this fires every few seconds
 * while someone is talking, and refetching the meeting on each one would
 * fight the live view for the network. The live page keeps its own list of
 * what it has sent; the caches are refreshed once, when the call ends.
 */
export function useAppendSegment(meetingId: string | undefined) {
  const result = useMutation<TranscriptSegment, ApiError, AppendSegmentInput>({
    mutationFn: (input) => appendSegment(meetingId as string, input),
  })
  return Object.assign(result, { message: errorMessage(result.error) })
}

export function useAddParticipant(meetingId: string | undefined) {
  const queryClient = useQueryClient()
  const result = useMutation<Participant, ApiError, AddParticipantInput>({
    mutationFn: (input) => addParticipant(meetingId as string, input),
    onSuccess: () => {
      if (meetingId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.meetings.detail(meetingId) })
      }
    },
  })
  return Object.assign(result, { message: errorMessage(result.error) })
}

export function useFinishLiveMeeting(meetingId: string | undefined) {
  const queryClient = useQueryClient()
  const result = useMutation<Meeting, ApiError, void>({
    mutationFn: () => finishLiveMeeting(meetingId as string),
    onSuccess: () => {
      // Everything downstream of the transcript has just been written.
      queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.workspace.all })
    },
  })
  return Object.assign(result, { message: errorMessage(result.error) })
}

/**
 * Generate (or regenerate) the summary under one template. Switching template
 * on a finished meeting runs here; on success the meeting detail is refetched
 * so the new summary appears alongside the others already generated.
 */
export function useGenerateSummary(meetingId: string | undefined) {
  const queryClient = useQueryClient()
  const result = useMutation<MeetingSummary, ApiError, GenerateSummaryInput>({
    mutationFn: (input) => generateSummary(meetingId as string, input),
    onSuccess: () => {
      if (meetingId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.meetings.detail(meetingId) })
      }
    },
  })
  return Object.assign(result, { message: errorMessage(result.error) })
}
