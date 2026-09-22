import { useState } from 'react'

import { ApiError } from '../../../lib/api'
import { formatClock, parseClock } from '../../../lib/format'
import Button from '../../ui/Button'
import { InlineError } from '../../ui/ErrorState'
import { cx, focusRing } from '../../../lib/cx'
import { usePlayer } from './PlayerContext'

const FIELD = cx(
  'h-8 rounded-lg border border-line-strong bg-surface px-2.5 text-[13px] text-ink',
  'placeholder:text-text-tertiary transition-colors duration-120 hover:border-muted/40',
  focusRing,
)

/**
 * Clip a moment out of the meeting.
 *
 * In and out points default to the player's position and open pre-filled, so
 * the common case - "clip what I am listening to" - is one click plus a title.
 * "Use current time" re-reads the player, which is how a range gets marked by
 * scrubbing rather than by typing.
 */
export default function NewHighlightForm({
  onSubmit,
  onCancel,
  isSubmitting,
  error,
}: {
  onSubmit: (input: { title: string; description: string; start_ms: number; end_ms: number }) => void
  onCancel: () => void
  isSubmitting: boolean
  error: unknown
}) {
  const { currentMs, durationMs } = usePlayer()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [start, setStart] = useState(() => formatClock(currentMs))
  const [end, setEnd] = useState(() => formatClock(Math.min(currentMs + 30_000, durationMs)))
  const [localError, setLocalError] = useState<string | null>(null)

  const apiError = error instanceof ApiError ? error : null

  function submit(event: React.FormEvent) {
    event.preventDefault()
    setLocalError(null)

    const startMs = parseClock(start)
    const endMs = parseClock(end)
    if (startMs === null || endMs === null) {
      setLocalError('Times must look like 4:12 or 1:02:03.')
      return
    }
    if (endMs < startMs) {
      setLocalError('The end must come after the start.')
      return
    }
    if (!title.trim()) {
      setLocalError('Give the highlight a title.')
      return
    }

    onSubmit({ title: title.trim(), description: description.trim(), start_ms: startMs, end_ms: endMs })
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-line bg-canvas p-3.5">
      <input
        autoFocus
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="What makes this worth keeping?"
        className={cx(FIELD, 'w-full')}
      />
      {apiError?.fieldError('title') && (
        <p className="mt-1 text-[12px] text-red-600">{apiError.fieldError('title')}</p>
      )}

      <input
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        placeholder="Add a note (optional)"
        className={cx(FIELD, 'mt-2 w-full')}
      />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {(
          [
            ['Start', start, setStart],
            ['End', end, setEnd],
          ] as const
        ).map(([label, value, set]) => (
          <div key={label} className="flex items-center gap-1.5">
            <span className="text-[12px] font-medium text-text-tertiary">{label}</span>
            <input
              value={value}
              onChange={(event) => set(event.target.value)}
              aria-label={`${label} time`}
              className={cx(FIELD, 'tabular w-20')}
            />
            <button
              type="button"
              onClick={() => set(formatClock(currentMs))}
              className={cx(
                'rounded-md px-1.5 py-1 text-[11px] font-medium text-brand',
                'transition-colors duration-120 hover:bg-brand-soft',
                focusRing,
              )}
            >
              Use current
            </button>
          </div>
        ))}
      </div>

      {(localError || (apiError && !apiError.fieldError('title'))) && (
        <div className="mt-2.5">
          {localError ? (
            <p role="alert" className="text-[13px] text-red-600">
              {localError}
            </p>
          ) : (
            <InlineError error={error} />
          )}
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <Button type="submit" variant="primary" size="sm" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : 'Save highlight'}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
