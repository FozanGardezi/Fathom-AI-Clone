import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import type { Meeting } from '../../../lib/api'
import { PLATFORM_LABELS, formatDateTime, formatDuration, pluralize } from '../../../lib/format'
import Button from '../../ui/Button'
import Icon from '../../ui/Icon'
import { Spinner } from '../../ui/LoadingState'
import StatusPill from '../StatusPill'
import ParticipantAvatars from './ParticipantAvatars'
import { useStartMeetingRecording } from '../../../hooks/useLiveMeeting'
import { cx, focusRing } from '../../../lib/cx'

export default function MeetingHeader({ meeting }: { meeting: Meeting }) {
  const [copied, setCopied] = useState(false)
  const navigate = useNavigate()
  const start = useStartMeetingRecording()

  // A Google Meet call that has not been recorded yet can be joined: the
  // notetaker connects to it and the live page takes over. A call already
  // recording is resumed straight to the live page.
  const canJoin = meeting.platform === 'google_meet' && meeting.status !== 'ready'

  function join() {
    if (meeting.status === 'recording') {
      navigate(`/meetings/${meeting.id}/live`)
      return
    }
    if (meeting.meeting_url) {
      window.open(meeting.meeting_url, '_blank', 'noopener,noreferrer')
    }
    start.mutate(meeting.id, {
      onSuccess: () => navigate(`/meetings/${meeting.id}/live`),
    })
  }

  /**
   * There is no sharing endpoint yet, so Share does the one useful thing it
   * can do honestly: puts this page's address on the clipboard. When real
   * share links land, only this handler changes.
   */
  async function share() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard access can be refused; saying nothing is better than an alert.
    }
  }

  return (
    <header className="mb-5">
      <Link
        to="/meetings"
        className={cx(
          'mb-3 inline-flex items-center gap-1 rounded-md py-0.5 pr-1.5 text-[13px]',
          'text-text-tertiary transition-colors duration-120 hover:text-ink',
          focusRing,
        )}
      >
        <Icon name="chevron-right" className="size-3.5 rotate-180" />
        Back to meetings
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-ink">
              {meeting.title}
            </h1>
            <StatusPill status={meeting.status} />
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px] text-text-secondary">
            <span className="tabular">{formatDateTime(meeting.started_at ?? meeting.scheduled_start)}</span>
            <span aria-hidden="true" className="text-text-tertiary">·</span>
            <span className="tabular">{formatDuration(meeting.duration_seconds)}</span>
            <span aria-hidden="true" className="text-text-tertiary">·</span>
            <span>{PLATFORM_LABELS[meeting.platform]}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div
            className="flex items-center gap-2"
            title={meeting.participants.map((p) => p.display_name).join(', ')}
          >
            <ParticipantAvatars participants={meeting.participants} />
            <span className="hidden text-[13px] text-text-tertiary sm:inline">
              {pluralize(meeting.participants.length, 'participant')}
            </span>
          </div>

          {canJoin && (
            <Button
              variant="primary"
              size="sm"
              onClick={join}
              disabled={start.isPending}
              className="bg-red-600 hover:bg-red-700"
            >
              {start.isPending ? (
                <>
                  <Spinner className="size-4" />
                  Connecting…
                </>
              ) : (
                <>
                  <Icon name="meetings" className="size-4" />
                  {meeting.status === 'recording' ? 'Resume notes' : 'Join & take notes'}
                </>
              )}
            </Button>
          )}

          <Button size="sm" onClick={share}>
            <Icon name={copied ? 'action-items' : 'plus'} className="size-4" />
            {copied ? 'Link copied' : 'Share'}
          </Button>
        </div>
      </div>
    </header>
  )
}
