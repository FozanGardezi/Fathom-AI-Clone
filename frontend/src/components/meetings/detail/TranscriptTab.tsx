import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { TranscriptSegment } from '../../../lib/api'
import { Card } from '../../ui/Card'
import Button from '../../ui/Button'
import EmptyState from '../../ui/EmptyState'
import ErrorState from '../../ui/ErrorState'
import Icon from '../../ui/Icon'
import Skeleton from '../../ui/Skeleton'
import { Spinner } from '../../ui/LoadingState'
import { cx, focusRing } from '../../../lib/cx'
import { usePlayer } from './PlayerContext'
import TranscriptLine, { type LineState } from './TranscriptLine'
import ClipBar from './ClipBar'

/**
 * Index of the segment covering `currentMs`, or the last one before it.
 *
 * Binary search rather than a scan: this runs on every animation frame while
 * the player is moving, and a long transcript makes a linear pass expensive
 * enough to notice.
 */
function findActiveIndex(segments: TranscriptSegment[], currentMs: number) {
  let low = 0
  let high = segments.length - 1
  let found = -1
  while (low <= high) {
    const mid = (low + high) >> 1
    if (segments[mid].start_seconds * 1000 <= currentMs) {
      found = mid
      low = mid + 1
    } else {
      high = mid - 1
    }
  }
  return found
}

/** How close to the end of the loaded transcript to get before fetching more. */
const LOAD_AHEAD_PX = 400

/** Keys that move the viewport rather than activate something. */
const SCROLL_KEYS = new Set([
  'PageUp',
  'PageDown',
  'Home',
  'End',
  'ArrowUp',
  'ArrowDown',
])

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

export default function TranscriptTab({
  meetingId,
  segments,
  total,
  isPending,
  isError,
  error,
  onRetry,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
}: {
  meetingId: string
  segments: TranscriptSegment[]
  total: number
  isPending: boolean
  isError: boolean
  error: unknown
  onRetry: () => void
  hasNextPage: boolean
  isFetchingNextPage: boolean
  onLoadMore: () => void
}) {
  const { currentMs, isPlaying, seekTo } = usePlayer()

  const scrollerRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)

  /** Whether the transcript should chase playback. Turned off the moment the
   *  reader scrolls for themselves. */
  const [isFollowing, setIsFollowing] = useState(true)
  const [selection, setSelection] = useState<{ from: number; to: number } | null>(null)

  const activeIndex = findActiveIndex(segments, currentMs)
  const activeId = activeIndex >= 0 ? segments[activeIndex].id : null

  // --- following ---------------------------------------------------------

  // The scroller only exists once the transcript itself renders - this
  // component returns a skeleton first - so the listeners below have to wait
  // for it. Binding them on mount would bind them to nothing.
  const listReady = !isPending && !isError && segments.length > 0

  // Only real input turns following off. Listening for wheel and touch rather
  // than the scroll event is what makes that distinction reliable: programmatic
  // scrolling fires `scroll`, but never these.
  useEffect(() => {
    if (!listReady) return
    const scroller = scrollerRef.current
    if (!scroller) return
    const stopFollowing = () => setIsFollowing(false)

    // Dragging the scrollbar counts too, but a plain pointerdown does not -
    // that fires when someone clicks a line to seek, which is them jumping
    // somewhere deliberately, not taking the wheel.
    const onPointerDown = (event: PointerEvent) => {
      if (event.offsetX > scroller.clientWidth) stopFollowing()
    }
    // Likewise, only keys that actually scroll. Enter on a timestamp is a
    // seek, not a scroll.
    const onKeyDown = (event: KeyboardEvent) => {
      if (SCROLL_KEYS.has(event.key)) stopFollowing()
    }

    scroller.addEventListener('wheel', stopFollowing, { passive: true })
    scroller.addEventListener('touchmove', stopFollowing, { passive: true })
    scroller.addEventListener('pointerdown', onPointerDown)
    scroller.addEventListener('keydown', onKeyDown)
    return () => {
      scroller.removeEventListener('wheel', stopFollowing)
      scroller.removeEventListener('touchmove', stopFollowing)
      scroller.removeEventListener('pointerdown', onPointerDown)
      scroller.removeEventListener('keydown', onKeyDown)
    }
  }, [listReady])

  useEffect(() => {
    if (!isFollowing || !activeRef.current) return
    // Paused means someone is reading, not watching - moving the page under
    // them would be the opposite of unobtrusive.
    if (!isPlaying) return
    activeRef.current.scrollIntoView({
      block: 'center',
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    })
  }, [activeId, isFollowing, isPlaying])

  const resumeFollowing = useCallback(() => {
    setIsFollowing(true)
    activeRef.current?.scrollIntoView({
      block: 'center',
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    })
  }, [])

  // --- paging ------------------------------------------------------------

  // Pull the next page as the reader nears the end of what is loaded, so a long
  // meeting reads continuously instead of stopping at a button.
  //
  // A scroll listener rather than an IntersectionObserver: the observer only
  // delivers callbacks while the page is actually rendering, which makes it
  // both untestable in a background tab and silently inert in one. Scroll
  // events fire whenever the element scrolls, full stop.
  useEffect(() => {
    if (!listReady || !hasNextPage) return
    const scroller = scrollerRef.current
    if (!scroller) return

    const maybeLoadMore = () => {
      if (isFetchingNextPage) return
      const remaining = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight
      if (remaining < LOAD_AHEAD_PX) onLoadMore()
    }

    scroller.addEventListener('scroll', maybeLoadMore, { passive: true })
    // Also check once on attach: a short transcript can already be at its end
    // without anyone having scrolled at all.
    maybeLoadMore()
    return () => scroller.removeEventListener('scroll', maybeLoadMore)
  }, [listReady, hasNextPage, isFetchingNextPage, onLoadMore])

  // --- selection ---------------------------------------------------------

  /** Clicking a clip marker starts a range; clicking another extends it. */
  const toggleClip = useCallback((index: number) => {
    setSelection((current) => {
      if (!current) return { from: index, to: index }
      if (index === current.from && index === current.to) return null
      return { from: Math.min(current.from, index), to: Math.max(current.from, index) }
    })
  }, [])

  const selectionRange = useMemo(() => {
    if (!selection) return null
    const first = segments[selection.from]
    const last = segments[selection.to]
    if (!first || !last) return null
    return {
      startMs: Math.round(first.start_seconds * 1000),
      endMs: Math.round(last.end_seconds * 1000),
      count: selection.to - selection.from + 1,
    }
  }, [selection, segments])

  // --- states ------------------------------------------------------------

  if (isPending) {
    return (
      <Card className="p-3">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="flex gap-3 px-3 py-2.5">
            <Skeleton className="size-7 rounded-full" />
            <div className="flex-1">
              <Skeleton className="h-3.5 w-40" />
              <Skeleton className="mt-2 h-3 w-full" />
              <Skeleton className="mt-1.5 h-3 w-2/3" />
            </div>
          </div>
        ))}
      </Card>
    )
  }

  if (isError) {
    return (
      <Card>
        <ErrorState error={error} onRetry={onRetry} title="Couldn't load the transcript" />
      </Card>
    )
  }

  if (segments.length === 0) {
    return (
      <Card>
        <EmptyState
          icon="meetings"
          title="No transcript"
          description="This meeting has no transcribed speech yet."
        />
      </Card>
    )
  }

  const showResume = !isFollowing && isPlaying && activeId !== null

  return (
    <div className="relative">
      <Card className="p-2">
        <div ref={scrollerRef} className="max-h-[600px] overflow-y-auto scroll-smooth">
          {segments.map((segment, index) => {
            const isSelected =
              selection !== null && index >= selection.from && index <= selection.to
            const state: LineState = isSelected
              ? 'selected'
              : segment.id === activeId
                ? 'active'
                : 'idle'

            return (
              <div key={segment.id} ref={segment.id === activeId ? activeRef : undefined}>
                <TranscriptLine
                  segment={segment}
                  state={state}
                  showSpeaker={
                    index === 0 ||
                    segments[index - 1].speaker?.id !== segment.speaker?.id ||
                    segments[index - 1].speaker_label !== segment.speaker_label
                  }
                  onSeek={() => seekTo(segment.start_seconds * 1000)}
                  onClip={() => toggleClip(index)}
                />
              </div>
            )
          })}

          {hasNextPage && (
            <div className="flex justify-center py-4">
              {isFetchingNextPage ? (
                <span className="flex items-center gap-2 text-[13px] text-text-tertiary">
                  <Spinner className="size-3.5" />
                  Loading more…
                </span>
              ) : (
                <Button size="sm" onClick={onLoadMore}>
                  Load the rest ({segments.length} of {total})
                </Button>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Offered, never forced: playback keeps moving and the reader decides
          whether to rejoin it. */}
      {showResume && (
        <button
          type="button"
          onClick={resumeFollowing}
          className={cx(
            'absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full',
            'border border-line-strong bg-surface py-1.5 pr-3 pl-2.5 text-[12px] font-medium',
            'text-text-secondary shadow-sm transition-colors duration-120 hover:text-ink',
            focusRing,
          )}
        >
          <Icon name="chevron-down" className="size-3.5" />
          Jump to current
        </button>
      )}

      {selectionRange && (
        <ClipBar
          meetingId={meetingId}
          startMs={selectionRange.startMs}
          endMs={selectionRange.endMs}
          segmentCount={selectionRange.count}
          onDone={() => setSelection(null)}
        />
      )}
    </div>
  )
}
