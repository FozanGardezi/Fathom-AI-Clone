import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { PlayerContext } from './PlayerContext'

/** Drives the shared playback clock. See PlayerContext for why it is a clock
 *  rather than a media element. */
export default function PlayerProvider({
  durationMs,
  children,
}: {
  durationMs: number
  children: React.ReactNode
}) {
  const [currentMs, setCurrentMs] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [rate, setRate] = useState(1)

  const frame = useRef<number | undefined>(undefined)
  const lastTick = useRef<number | undefined>(undefined)
  // Mirrored into a ref so the animation loop reads the current rate without
  // being torn down and restarted every time it changes. Written in an effect,
  // never during render.
  const rateRef = useRef(rate)
  useEffect(() => {
    rateRef.current = rate
  }, [rate])

  useEffect(() => {
    if (!isPlaying) return

    const step = (now: number) => {
      const previous = lastTick.current ?? now
      lastTick.current = now
      setCurrentMs((ms) => {
        const next = ms + (now - previous) * rateRef.current
        if (next >= durationMs) {
          setIsPlaying(false)
          return durationMs
        }
        return next
      })
      frame.current = requestAnimationFrame(step)
    }

    frame.current = requestAnimationFrame(step)
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current)
      lastTick.current = undefined
    }
  }, [isPlaying, durationMs])

  const seekTo = useCallback(
    (ms: number) => setCurrentMs(Math.min(Math.max(0, ms), durationMs)),
    [durationMs],
  )

  const play = useCallback(() => {
    // Pressing play at the end should replay rather than sit still.
    setCurrentMs((ms) => (ms >= durationMs ? 0 : ms))
    setIsPlaying(true)
  }, [durationMs])

  const pause = useCallback(() => setIsPlaying(false), [])
  const toggle = useCallback(() => (isPlaying ? pause() : play()), [isPlaying, pause, play])

  const value = useMemo(
    () => ({ currentMs, durationMs, isPlaying, rate, play, pause, toggle, seekTo, setRate }),
    [currentMs, durationMs, isPlaying, rate, play, pause, toggle, seekTo],
  )

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>
}
