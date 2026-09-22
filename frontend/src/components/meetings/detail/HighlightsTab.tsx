import { useState } from 'react'

import type { Highlight } from '../../../lib/api'
import { Card } from '../../ui/Card'
import Button from '../../ui/Button'
import EmptyState from '../../ui/EmptyState'
import ErrorState from '../../ui/ErrorState'
import Icon from '../../ui/Icon'
import Skeleton from '../../ui/Skeleton'
import { formatClock } from '../../../lib/format'
import { cx, focusRing } from '../../../lib/cx'
import { useCreateHighlight, useHighlights } from '../../../hooks/useMeetings'
import { usePlayer } from './PlayerContext'
import NewHighlightForm from './NewHighlightForm'

function HighlightRow({ highlight }: { highlight: Highlight }) {
  const { seekTo, play } = usePlayer()

  return (
    <li>
      <button
        type="button"
        onClick={() => {
          seekTo(highlight.start_ms)
          play()
        }}
        className={cx(
          'flex w-full gap-3 rounded-lg px-3 py-3 text-left',
          'transition-colors duration-120 hover:bg-ink/[0.02]',
          focusRing,
        )}
      >
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
          <Icon name="highlights" className="size-3.5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-semibold text-ink">
            {highlight.title}
          </span>
          {highlight.description && (
            <span className="mt-0.5 block text-[13px] leading-5 text-text-tertiary">
              {highlight.description}
            </span>
          )}
          <span className="tabular mt-1 block text-[12px] text-text-tertiary">
            {formatClock(highlight.start_ms)} – {formatClock(highlight.end_ms)}
            <span className="mx-1.5" aria-hidden="true">·</span>
            {Math.round(highlight.duration_ms / 1000)}s
          </span>
        </span>
      </button>
    </li>
  )
}

export default function HighlightsTab({ meetingId }: { meetingId: string }) {
  const [isCreating, setIsCreating] = useState(false)
  const highlights = useHighlights(meetingId)
  const create = useCreateHighlight(meetingId)

  const rows = highlights.data?.results ?? []

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[13px] text-text-tertiary">
          Clip a moment and it stays pinned to this point in the meeting.
        </p>
        {!isCreating && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              create.reset()
              setIsCreating(true)
            }}
          >
            <Icon name="plus" className="size-4" />
            New highlight
          </Button>
        )}
      </div>

      {isCreating && (
        <NewHighlightForm
          isSubmitting={create.isPending}
          error={create.error}
          onCancel={() => setIsCreating(false)}
          onSubmit={(input) =>
            create.mutate(input, {
              // Only close on success - a failed save must keep what was typed.
              onSuccess: () => setIsCreating(false),
            })
          }
        />
      )}

      {highlights.isPending ? (
        <Card className="p-3">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="flex gap-3 px-3 py-3">
              <Skeleton className="size-7 rounded-lg" />
              <div className="flex-1">
                <Skeleton className="h-3.5 w-48" />
                <Skeleton className="mt-2 h-3 w-24" />
              </div>
            </div>
          ))}
        </Card>
      ) : highlights.isError ? (
        <Card>
          <ErrorState
            error={highlights.error}
            onRetry={() => highlights.refetch()}
            title="Couldn't load highlights"
          />
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon="highlights"
            title="No highlights yet"
            description="Play the meeting, stop at something worth keeping, and clip it."
          />
        </Card>
      ) : (
        <Card className="p-2">
          <ul className="divide-y divide-line">
            {rows.map((highlight) => (
              <HighlightRow key={highlight.id} highlight={highlight} />
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
