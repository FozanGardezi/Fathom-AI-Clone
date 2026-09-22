import { memo } from 'react'

import type { TranscriptSegment } from '../../../lib/api'
import Icon from '../../ui/Icon'
import { initials } from '../../../lib/format'
import { cx, focusRing } from '../../../lib/cx'

export type LineState = 'idle' | 'active' | 'selected'

/**
 * One line of transcript.
 *
 * Memoised on purpose. The player's clock ticks at animation-frame rate, and
 * without this every line in the transcript would re-render sixty times a
 * second - fine for the forty-seven lines of a one-hour call, ruinous for a
 * long one. With it, a tick re-renders only the two lines whose state
 * actually changed.
 *
 * `content-visibility: auto` was tried here to skip painting offscreen lines
 * and removed again: lines re-laid out at their true height as they scrolled
 * in, which shifted the scroll position and left auto-scroll landing a few
 * hundred pixels off the line it was aiming for. Memoisation is what actually
 * costs, and it does not move the page under anyone.
 */
function TranscriptLine({
  segment,
  state,
  showSpeaker,
  onSeek,
  onClip,
}: {
  segment: TranscriptSegment
  state: LineState
  /** False when the previous line had the same speaker, so a run of turns from
   *  one person reads as a block instead of repeating their name. */
  showSpeaker: boolean
  onSeek: () => void
  onClip: () => void
}) {
  const name = segment.speaker?.display_name || segment.speaker_label || 'Unknown speaker'

  return (
    <div
      onClick={(event) => {
        // A click that ends a text selection is someone copying a quote, not
        // asking to jump. Seeking there would be maddening.
        if (window.getSelection()?.toString()) return
        // The clip button is inside this row and handles its own click.
        if ((event.target as HTMLElement).closest('[data-clip]')) return
        onSeek()
      }}
      className={cx(
        'group relative cursor-pointer rounded-lg py-2 pr-2 pl-3 transition-colors duration-120',
        state === 'active' && 'bg-brand-soft/60',
        state === 'selected' && 'bg-amber-50',
        state === 'idle' && 'hover:bg-ink/[0.025]',
      )}
    >
      {/* Accent bar rather than colour alone, so the active line is findable
          at a glance while scanning. */}
      <span
        aria-hidden="true"
        className={cx(
          'absolute inset-y-1 left-0 w-0.5 rounded-full transition-colors duration-120',
          state === 'active' && 'bg-brand',
          state === 'selected' && 'bg-amber-400',
          state === 'idle' && 'bg-transparent',
        )}
      />

      <div className="flex gap-3">
        <div className="w-7 shrink-0">
          {showSpeaker && (
            <span
              title={name}
              className={cx(
                'flex size-7 items-center justify-center rounded-full text-[10px] font-semibold',
                segment.speaker?.is_host
                  ? 'bg-brand text-white'
                  : 'bg-ink/[0.06] text-text-secondary',
              )}
            >
              {initials(name)}
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          {showSpeaker && (
            <span className="mr-2 text-[13px] font-semibold text-ink">{name}</span>
          )}
          {/* Stays a real button so the transcript is navigable by keyboard,
              even though the whole row is clickable by mouse. */}
          <button
            type="button"
            onClick={onSeek}
            aria-label={`Jump to ${segment.timestamp}`}
            className={cx(
              'tabular rounded px-1 py-0.5 text-[12px] transition-colors duration-120',
              focusRing,
              state === 'active'
                ? 'font-semibold text-brand'
                : 'text-text-tertiary hover:bg-brand-soft hover:text-brand',
            )}
          >
            {segment.timestamp}
          </button>

          <p
            className={cx(
              'mt-0.5 text-[14px] leading-6',
              state === 'active' ? 'text-ink' : 'text-text-secondary',
            )}
          >
            {segment.text}
          </p>
        </div>

        {/* The clip affordance. Hidden until the row is hovered or the button
            is focused, so a page of transcript is not a wall of buttons. */}
        <button
          type="button"
          data-clip
          onClick={onClip}
          aria-label={`Add ${segment.timestamp} to a highlight`}
          className={cx(
            'mt-0.5 flex size-7 shrink-0 items-center justify-center self-start rounded-md',
            'opacity-0 transition-all duration-120 group-hover:opacity-100 focus-visible:opacity-100',
            focusRing,
            state === 'selected'
              ? 'bg-amber-100 text-amber-700 opacity-100'
              : 'text-text-tertiary hover:bg-amber-50 hover:text-amber-600',
          )}
        >
          <Icon name="highlights" className="size-3.5" />
        </button>
      </div>
    </div>
  )
}

export default memo(TranscriptLine)
