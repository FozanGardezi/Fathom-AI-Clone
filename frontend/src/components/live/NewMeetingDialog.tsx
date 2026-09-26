import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import Button from '../ui/Button'
import Icon from '../ui/Icon'
import { InlineError } from '../ui/ErrorState'
import { PLATFORM_LABELS } from '../../lib/format'
import { cx, focusRing } from '../../lib/cx'
import { useStartLiveMeeting } from '../../hooks/useLiveMeeting'
import type { MeetingPlatform } from '../../lib/api'

const FIELD = cx(
  'h-9 w-full rounded-lg border border-line-strong bg-surface px-3 text-[13px] text-ink',
  'placeholder:text-text-tertiary transition-colors duration-120 hover:border-muted/40',
  focusRing,
)

type Guest = { display_name: string; email: string }

/**
 * Starts a recording.
 *
 * Only a title is required - a call you are already late for should not need a
 * form filled in first. Everyone else can be added while it runs.
 */
export default function NewMeetingDialog({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const start = useStartLiveMeeting()

  const [title, setTitle] = useState('')
  const [platform, setPlatform] = useState<MeetingPlatform>('other')
  const [guests, setGuests] = useState<Guest[]>([{ display_name: '', email: '' }])

  function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    start.mutate(
      {
        title: title.trim(),
        platform,
        participants: guests
          .filter((g) => g.display_name.trim())
          .map((g) => ({ display_name: g.display_name.trim(), email: g.email.trim() })),
      },
      { onSuccess: (meeting) => navigate(`/meetings/${meeting.id}/live`) },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-ink/25"
      />
      <form
        onSubmit={submit}
        className="relative w-full max-w-md rounded-xl border border-line bg-surface p-5 shadow-xl"
      >
        <h2 className="text-[15px] font-semibold text-ink">Start a meeting</h2>
        <p className="mt-0.5 text-[13px] text-text-tertiary">
          Recording begins straight away. Everything else can wait.
        </p>

        <label className="mt-4 block text-[12px] font-medium text-text-secondary">
          Title
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Weekly sync"
            className={cx(FIELD, 'mt-1')}
          />
        </label>

        <label className="mt-3 block text-[12px] font-medium text-text-secondary">
          Platform
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value as MeetingPlatform)}
            className={cx(FIELD, 'mt-1')}
          >
            {Object.entries(PLATFORM_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="mt-4">
          <legend className="text-[12px] font-medium text-text-secondary">
            Who else is here? <span className="text-text-tertiary">(optional)</span>
          </legend>
          <div className="mt-1 space-y-2">
            {guests.map((guest, index) => (
              <div key={index} className="flex gap-2">
                <input
                  value={guest.display_name}
                  onChange={(e) =>
                    setGuests((g) =>
                      g.map((row, i) =>
                        i === index ? { ...row, display_name: e.target.value } : row,
                      ),
                    )
                  }
                  placeholder="Name"
                  className={FIELD}
                />
                <input
                  value={guest.email}
                  onChange={(e) =>
                    setGuests((g) =>
                      g.map((row, i) => (i === index ? { ...row, email: e.target.value } : row)),
                    )
                  }
                  placeholder="Email"
                  className={FIELD}
                />
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setGuests((g) => [...g, { display_name: '', email: '' }])}
            className={cx(
              'mt-2 inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[12px]',
              'font-medium text-brand transition-colors duration-120 hover:bg-brand-soft',
              focusRing,
            )}
          >
            <Icon name="plus" className="size-3.5" />
            Add another
          </button>
        </fieldset>

        {start.isError && (
          <div className="mt-3">
            <InlineError error={start.error} />
          </div>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={start.isPending || !title.trim()}
          >
            {start.isPending ? 'Starting…' : 'Start recording'}
          </Button>
        </div>
      </form>
    </div>
  )
}
