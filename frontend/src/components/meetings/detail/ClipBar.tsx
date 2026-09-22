import { useState } from 'react'

import Button from '../../ui/Button'
import Icon from '../../ui/Icon'
import { InlineError } from '../../ui/ErrorState'
import { formatClock } from '../../../lib/format'
import { cx, focusRing } from '../../../lib/cx'
import { useCreateHighlight } from '../../../hooks/useMeetings'

/**
 * The bar that appears once lines are marked in the transcript.
 *
 * Turning a passage into a highlight is the main thing anyone does while
 * reading a transcript, so it happens in place - mark the lines, name it, save
 * - rather than sending the reader to another tab to retype timestamps they
 * were already looking at. The range comes from the marked segments, so it
 * always lines up with something that was actually said.
 */
export default function ClipBar({
  meetingId,
  startMs,
  endMs,
  segmentCount,
  onDone,
}: {
  meetingId: string
  startMs: number
  endMs: number
  segmentCount: number
  onDone: () => void
}) {
  const [title, setTitle] = useState('')
  const create = useCreateHighlight(meetingId)

  function save(event: React.FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    create.mutate(
      { title: title.trim(), start_ms: startMs, end_ms: endMs },
      { onSuccess: onDone },
    )
  }

  return (
    <form
      onSubmit={save}
      className={cx(
        'sticky bottom-4 z-10 mt-3 rounded-xl border border-amber-200 bg-amber-50/90 p-3',
        'shadow-sm backdrop-blur-sm',
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 text-[12px] font-medium text-amber-800">
          <Icon name="highlights" className="size-3.5" />
          {segmentCount === 1 ? '1 line' : `${segmentCount} lines`}
          <span className="tabular font-normal text-amber-700">
            {formatClock(startMs)} – {formatClock(endMs)}
          </span>
        </span>

        <input
          autoFocus
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Name this highlight"
          className={cx(
            'h-8 min-w-0 flex-1 rounded-lg border border-amber-200 bg-surface px-2.5',
            'text-[13px] text-ink placeholder:text-text-tertiary',
            focusRing,
          )}
        />

        <Button type="submit" variant="primary" size="sm" disabled={create.isPending || !title.trim()}>
          {create.isPending ? 'Saving…' : 'Save highlight'}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
          Cancel
        </Button>
      </div>

      {create.isError && (
        <div className="mt-2">
          <InlineError error={create.error} />
        </div>
      )}

      <p className="mt-1.5 text-[11px] text-amber-700">
        Mark another line to extend the range.
      </p>
    </form>
  )
}
