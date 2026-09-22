import { useMemo } from 'react'

import type { TranscriptSegment } from '../../../lib/api'
import { cx } from '../../../lib/cx'

const BAR_COUNT = 140

/**
 * A stand-in for a recording's waveform.
 *
 * No audio is stored, so there is nothing to analyse - but the transcript
 * already says who was talking and when. Each bar covers a slice of the
 * meeting and is sized by how much of that slice was speech, nudged by the
 * transcriber's confidence. The result tracks the real shape of the
 * conversation: pauses read as troughs, dense exchanges as peaks. It is
 * simulated, not fabricated - every bar is derived from data the API returned.
 */
function buildBars(segments: TranscriptSegment[], durationMs: number) {
  const bars = new Array<number>(BAR_COUNT).fill(0)
  if (!durationMs) return bars

  const sliceMs = durationMs / BAR_COUNT
  for (const segment of segments) {
    const startMs = segment.start_seconds * 1000
    const endMs = segment.end_seconds * 1000
    const first = Math.max(0, Math.floor(startMs / sliceMs))
    const last = Math.min(BAR_COUNT - 1, Math.floor(endMs / sliceMs))

    for (let i = first; i <= last; i++) {
      const sliceStart = i * sliceMs
      const covered =
        Math.min(endMs, sliceStart + sliceMs) - Math.max(startMs, sliceStart)
      const share = Math.max(0, covered) / sliceMs
      bars[i] = Math.min(1, bars[i] + share * (segment.confidence ?? 0.9))
    }
  }

  // A silent slice still gets a sliver so the track reads as a track rather
  // than as gaps in a broken chart.
  return bars.map((value) => 0.12 + value * 0.88)
}

export default function Waveform({
  segments,
  durationMs,
  currentMs,
  isLoading,
}: {
  segments: TranscriptSegment[]
  durationMs: number
  currentMs: number
  isLoading: boolean
}) {
  const bars = useMemo(() => buildBars(segments, durationMs), [segments, durationMs])
  const playedIndex = durationMs ? (currentMs / durationMs) * BAR_COUNT : 0

  return (
    <div aria-hidden="true" className="flex h-10 items-center gap-px">
      {bars.map((height, index) => (
        <span
          key={index}
          style={{ height: `${Math.round(height * 100)}%` }}
          className={cx(
            'flex-1 rounded-full transition-colors duration-75',
            isLoading
              ? 'animate-pulse bg-ink/[0.06]'
              : index < playedIndex
                ? 'bg-brand/70'
                : 'bg-ink/[0.12]',
          )}
        />
      ))}
    </div>
  )
}
