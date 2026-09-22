import { useRef } from 'react'

import type { TranscriptSegment } from '../../../lib/api'
import { formatClock } from '../../../lib/format'
import { Card } from '../../ui/Card'
import Icon from '../../ui/Icon'
import { cx, focusRing } from '../../../lib/cx'
import { PLAYBACK_RATES, usePlayer } from './PlayerContext'
import Waveform from './Waveform'

function PlayIcon({ isPlaying }: { isPlaying: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="size-4">
      {isPlaying ? (
        <path d="M8 5.5h2.6v13H8zM13.4 5.5H16v13h-2.6z" />
      ) : (
        <path d="M8.5 5.4v13.2a.7.7 0 0 0 1.07.6l10.2-6.6a.7.7 0 0 0 0-1.2L9.57 4.8a.7.7 0 0 0-1.07.6Z" />
      )}
    </svg>
  )
}

/**
 * The meeting player.
 *
 * Drives the shared clock in PlayerContext rather than owning time itself, so
 * the transcript and the highlight editor stay in step with it. Seeking is a
 * click or drag anywhere on the track, and the whole track is a slider for the
 * keyboard, which is what makes it usable without a mouse.
 */
export default function MeetingPlayer({
  segments,
  isLoadingTranscript,
}: {
  segments: TranscriptSegment[]
  isLoadingTranscript: boolean
}) {
  const { currentMs, durationMs, isPlaying, rate, toggle, seekTo, setRate } = usePlayer()
  const trackRef = useRef<HTMLDivElement>(null)

  const progress = durationMs ? (currentMs / durationMs) * 100 : 0

  function seekFromPointer(clientX: number) {
    const track = trackRef.current
    if (!track || !durationMs) return
    const { left, width } = track.getBoundingClientRect()
    seekTo(((clientX - left) / width) * durationMs)
  }

  function onKeyDown(event: React.KeyboardEvent) {
    const step = event.shiftKey ? 30_000 : 5_000
    if (event.key === 'ArrowRight') seekTo(currentMs + step)
    else if (event.key === 'ArrowLeft') seekTo(currentMs - step)
    else if (event.key === 'Home') seekTo(0)
    else if (event.key === 'End') seekTo(durationMs)
    else if (event.key === ' ' || event.key === 'Enter') toggle()
    else return
    event.preventDefault()
  }

  return (
    <Card className="mb-5 p-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={toggle}
          aria-label={isPlaying ? 'Pause' : 'Play'}
          className={cx(
            'flex size-10 shrink-0 items-center justify-center rounded-full bg-brand text-white',
            'transition-colors duration-120 hover:bg-brand-hover',
            focusRing,
          )}
        >
          <PlayIcon isPlaying={isPlaying} />
        </button>

        <div className="min-w-0 flex-1">
          <div
            ref={trackRef}
            role="slider"
            tabIndex={0}
            aria-label="Seek"
            aria-valuemin={0}
            aria-valuemax={Math.round(durationMs / 1000)}
            aria-valuenow={Math.round(currentMs / 1000)}
            aria-valuetext={`${formatClock(currentMs)} of ${formatClock(durationMs)}`}
            onKeyDown={onKeyDown}
            onPointerDown={(event) => {
              event.currentTarget.setPointerCapture(event.pointerId)
              seekFromPointer(event.clientX)
            }}
            onPointerMove={(event) => {
              // Only while dragging - buttons is a bitmask, 1 is the primary.
              if (event.buttons === 1) seekFromPointer(event.clientX)
            }}
            className={cx('relative cursor-pointer rounded-md py-1', focusRing)}
          >
            <Waveform
              segments={segments}
              durationMs={durationMs}
              currentMs={currentMs}
              isLoading={isLoadingTranscript}
            />
            <span
              aria-hidden="true"
              style={{ left: `${progress}%` }}
              className="pointer-events-none absolute inset-y-0 w-px -translate-x-1/2 bg-brand"
            >
              <span className="absolute -top-0.5 left-1/2 size-2 -translate-x-1/2 rounded-full bg-brand" />
            </span>
          </div>

          <div className="mt-1 flex items-center justify-between text-[12px] text-text-tertiary">
            <span className="tabular font-medium text-text-secondary">
              {formatClock(currentMs)}
            </span>
            <span className="tabular">{formatClock(durationMs)}</span>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <label className="sr-only" htmlFor="playback-rate">
            Playback speed
          </label>
          <select
            id="playback-rate"
            value={rate}
            onChange={(event) => setRate(Number(event.target.value))}
            className={cx(
              'tabular h-8 rounded-lg border border-line-strong bg-surface px-2 text-[12px]',
              'font-medium text-text-secondary transition-colors duration-120',
              'hover:border-muted/40 hover:text-ink',
              focusRing,
            )}
          >
            {PLAYBACK_RATES.map((option) => (
              <option key={option} value={option}>
                {option}×
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="mt-2 flex items-center gap-1.5 text-[11px] text-text-tertiary">
        <Icon name="meetings" className="size-3.5" />
        No recording stored for this meeting — playback is simulated from the transcript timeline.
      </p>
    </Card>
  )
}
