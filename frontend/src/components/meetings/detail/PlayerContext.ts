import { createContext, useContext } from 'react'

/**
 * Playback state for a meeting, shared by the player, the transcript and the
 * highlight editor.
 *
 * There is no media file behind this. The backend stores transcripts and
 * timings, not recordings, so playback is a clock: a rAF loop advancing a
 * millisecond counter at the current rate. Everything downstream - the seek
 * bar, the active transcript line, the clip in/out points - reads that counter
 * and behaves exactly as it would against a real `<audio>` element. Swapping in
 * a real element later means replacing the provider, not its consumers.
 */
export type PlayerValue = {
  currentMs: number
  durationMs: number
  isPlaying: boolean
  rate: number
  play: () => void
  pause: () => void
  toggle: () => void
  seekTo: (ms: number) => void
  setRate: (rate: number) => void
}

export const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 2]

export const PlayerContext = createContext<PlayerValue | null>(null)

export function usePlayer() {
  const value = useContext(PlayerContext)
  if (!value) throw new Error('usePlayer must be used inside a PlayerProvider')
  return value
}
