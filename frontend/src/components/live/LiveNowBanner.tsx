import { useNavigate } from 'react-router-dom'

import Button from '../ui/Button'
import Icon from '../ui/Icon'
import { InlineError } from '../ui/ErrorState'
import { cx } from '../../lib/cx'
import { pluralize, relativeToNow } from '../../lib/format'
import { useLiveNow } from '../../hooks/useMeetings'
import { useStartMeetingRecording } from '../../hooks/useLiveMeeting'
import type { MeetingListItem } from '../../lib/api'

/**
 * The "live now" prompt.
 *
 * When a Google Meet call from the connected calendar is starting - or already
 * running - this surfaces it with one action: join the call and connect the
 * notetaker. Connecting means opening the real Meet link and starting a
 * recording session bound to that meeting, which is where the live transcript,
 * mid-call highlights and, on finish, the summary all come from.
 *
 * Renders nothing when there is nothing to join, so it never holds empty space
 * at the top of a page.
 */
export default function LiveNowBanner() {
  const navigate = useNavigate()
  const { meetings } = useLiveNow()
  const start = useStartMeetingRecording()

  if (meetings.length === 0) return null

  function join(meeting: MeetingListItem) {
    // Open the actual Meet in a new tab so the person is in the call, then bind
    // a notetaker session to it. The window.open runs inside this click so the
    // browser treats it as user-initiated rather than a blocked popup.
    if (meeting.meeting_url) {
      window.open(meeting.meeting_url, '_blank', 'noopener,noreferrer')
    }
    start.mutate(meeting.id, {
      onSuccess: () => navigate(`/meetings/${meeting.id}/live`),
    })
  }

  return (
    <section className="mb-6 space-y-2" aria-label="Meetings you can join now">
      {meetings.map((meeting) => {
        const isStarting = start.isPending && start.variables === meeting.id
        const live = meeting.status === 'recording'
        return (
          <div
            key={meeting.id}
            className={cx(
              'flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border p-4',
              'border-red-200 bg-red-50/60',
            )}
          >
            <span className="flex items-center gap-2 text-[11px] font-semibold text-red-600">
              <span className="size-2 animate-pulse rounded-full bg-red-500" />
              {live ? 'LIVE NOW' : 'STARTING'}
            </span>

            <div className="min-w-0 flex-1">
              <p className="truncate text-[14px] font-semibold text-ink">{meeting.title}</p>
              <p className="mt-0.5 text-[12px] text-text-secondary">
                Google Meet
                <span className="mx-1.5 text-text-tertiary" aria-hidden="true">·</span>
                {live ? 'in progress' : relativeToNow(meeting.scheduled_start) || 'now'}
                {meeting.participant_count > 0 && (
                  <>
                    <span className="mx-1.5 text-text-tertiary" aria-hidden="true">·</span>
                    {pluralize(meeting.participant_count, 'invitee')}
                  </>
                )}
              </p>
            </div>

            <Button
              variant="primary"
              size="sm"
              onClick={() => join(meeting)}
              disabled={isStarting}
              className="bg-red-600 hover:bg-red-700"
            >
              <Icon name="meetings" className="size-4" />
              {isStarting ? 'Connecting…' : 'Join & take notes'}
            </Button>
          </div>
        )
      })}

      {start.isError && <InlineError error={start.error} />}
    </section>
  )
}
