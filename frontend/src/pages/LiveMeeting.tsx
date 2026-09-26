import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Card, CardBody, CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import ErrorState, { InlineError } from '../components/ui/ErrorState'
import Icon from '../components/ui/Icon'
import Skeleton from '../components/ui/Skeleton'
import { Spinner } from '../components/ui/LoadingState'
import { formatClock, initials } from '../lib/format'
import { cx, focusRing } from '../lib/cx'
import { useCreateHighlight, useMeeting } from '../hooks/useMeetings'
import { useAppendSegment, useFinishLiveMeeting } from '../hooks/useLiveMeeting'
import { useSpeechTranscription } from '../hooks/useSpeechTranscription'
import type { Participant } from '../lib/api'

/** A line the page has captured. Held locally rather than refetched: the
 *  transcript grows every few seconds and re-reading it would fight the
 *  microphone for the network. */
type CapturedLine = {
  key: string
  speaker: Participant | null
  startMs: number
  endMs: number
  text: string
  pending: boolean
  failed?: boolean
}

/** A moment someone flagged mid-call, held locally with its save state so a
 *  failed save shows rather than vanishing. */
type Moment = {
  key: string
  atMs: number
  pending: boolean
  failed?: boolean
}

/** How far back a flagged moment reaches, so the clip carries the lead-up to
 *  what was just said rather than starting on the reaction to it. */
const HIGHLIGHT_LOOKBACK_MS = 15_000

export default function LiveMeeting() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const meeting = useMeeting(id)

  const append = useAppendSegment(id)
  const finish = useFinishLiveMeeting(id)
  const highlight = useCreateHighlight(id)

  const [elapsedMs, setElapsedMs] = useState(0)
  const [lines, setLines] = useState<CapturedLine[]>([])
  const [moments, setMoments] = useState<Moment[]>([])
  const [speakerId, setSpeakerId] = useState<string | null>(null)
  const [manual, setManual] = useState('')

  // The recording clock runs from when the meeting actually started, so a
  // reload mid-call continues the timeline rather than restarting it.
  const startedAt = meeting.data?.started_at
  const baseMs = startedAt ? new Date(startedAt).getTime() : null

  // Mirrored into a ref so the speech callbacks read the current value without
  // being rebuilt whenever it changes. Written in an effect, never in render.
  const baseRef = useRef<number | null>(null)
  useEffect(() => {
    baseRef.current = baseMs
  }, [baseMs])

  useEffect(() => {
    if (baseMs === null) return
    const tick = () => setElapsedMs(Date.now() - baseMs)
    tick()
    // A second is enough for a clock and costs nothing; the transcript takes
    // its own timestamps from `readClock`, not from this.
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [baseMs])

  const readClock = useCallback(
    () => (baseRef.current === null ? 0 : Date.now() - baseRef.current),
    [],
  )

  const participants = meeting.data?.participants ?? []
  const activeSpeaker = participants.find((p) => p.id === speakerId) ?? participants[0] ?? null

  /** Commit one utterance: show it immediately, then persist it. */
  const capture = useCallback(
    (text: string, startMs: number, endMs: number, confidence: number | null) => {
      const key = `${startMs}-${text.slice(0, 24)}-${Math.random().toString(36).slice(2, 7)}`
      const speaker = activeSpeaker
      setLines((current) => [
        ...current,
        { key, speaker, startMs, endMs, text, pending: true },
      ])

      append.mutate(
        {
          speaker: speaker?.id ?? null,
          start_ms: Math.max(0, Math.round(startMs)),
          end_ms: Math.max(Math.round(startMs), Math.round(endMs)),
          text,
          confidence,
        },
        {
          onSuccess: () =>
            setLines((current) =>
              current.map((l) => (l.key === key ? { ...l, pending: false } : l)),
            ),
          // Kept on screen and flagged rather than dropped: losing something
          // that was said is worse than showing it did not save.
          onError: () =>
            setLines((current) =>
              current.map((l) =>
                l.key === key ? { ...l, pending: false, failed: true } : l,
              ),
            ),
        },
      )
    },
    [activeSpeaker, append],
  )

  const speech = useSpeechTranscription({
    lang: meeting.data?.language === 'en' ? 'en-US' : meeting.data?.language ?? 'en-US',
    elapsedMs: readClock,
    onFinal: (utterance) =>
      capture(utterance.text, utterance.startMs, utterance.endMs, utterance.confidence),
  })

  // Start listening as soon as the page opens. "Start recording" has to mean
  // recording - the badge said RECORDING while the microphone sat paused,
  // which produced meetings with nothing in them and no sign anything was
  // wrong. Attempted once; if the browser refuses or the mic is blocked, the
  // hook surfaces that as an error rather than failing silently.
  const autoStarted = useRef(false)
  useEffect(() => {
    if (autoStarted.current) return
    if (!speech.isSupported || meeting.data?.status !== 'recording') return
    autoStarted.current = true
    speech.start()
  }, [speech, meeting.data?.status])

  const feedRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
  }, [lines.length, speech.interim])

  /** Flag the current moment as a highlight. Saved immediately at the live
   *  clock, so it lands in the finished meeting's Highlights and on the player
   *  timeline exactly where it was pressed. */
  function flagMoment() {
    const at = readClock()
    const key = `m-${at}-${Math.random().toString(36).slice(2, 7)}`
    setMoments((current) => [...current, { key, atMs: at, pending: true }])
    highlight.mutate(
      {
        title: `Highlighted moment · ${formatClock(at)}`,
        start_ms: Math.max(0, Math.round(at - HIGHLIGHT_LOOKBACK_MS)),
        end_ms: Math.round(at),
      },
      {
        onSuccess: () =>
          setMoments((current) =>
            current.map((m) => (m.key === key ? { ...m, pending: false } : m)),
          ),
        onError: () =>
          setMoments((current) =>
            current.map((m) => (m.key === key ? { ...m, pending: false, failed: true } : m)),
          ),
      },
    )
  }

  function submitManual(event: React.FormEvent) {
    event.preventDefault()
    const text = manual.trim()
    if (!text) return
    const now = readClock()
    capture(text, Math.max(0, now - 3000), now, null)
    setManual('')
  }

  function end() {
    // Ending with an empty transcript produces an empty meeting. That is a
    // legitimate thing to do, but never an intentional one by accident.
    if (lines.length === 0) {
      const proceed = window.confirm(
        'Nothing was captured in this meeting.\n\n' +
          'The microphone may be blocked, or this browser may not support ' +
          'transcription. Ending now saves the meeting with an empty ' +
          'transcript and no summary.\n\nEnd anyway?',
      )
      if (!proceed) return
    }
    speech.stop()
    finish.mutate(undefined, {
      onSuccess: () => navigate(`/meetings/${id}`),
    })
  }

  if (meeting.isPending) {
    return (
      <>
        <Skeleton className="h-7 w-72" />
        <Skeleton className="mt-4 h-24 w-full rounded-xl" />
        <Skeleton className="mt-4 h-96 w-full rounded-xl" />
      </>
    )
  }

  if (meeting.isError) {
    return (
      <Card>
        <ErrorState
          error={meeting.error}
          onRetry={() => meeting.refetch()}
          title="Couldn't load this meeting"
        />
      </Card>
    )
  }

  const isLive = meeting.data.status === 'recording'

  return (
    <>
      <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {/* The badge reports what is actually happening. A meeting can be
                open without capturing anything - blocked microphone, paused,
                unsupported browser - and saying RECORDING then is a lie that
                costs someone their meeting. */}
            {isLive && speech.isListening && (
              <span className="flex items-center gap-1.5 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-600">
                <span className="size-1.5 animate-pulse rounded-full bg-red-500" />
                RECORDING
              </span>
            )}
            {isLive && !speech.isListening && (
              <span className="flex items-center gap-1.5 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                <span className="size-1.5 rounded-full bg-amber-500" />
                NOT CAPTURING
              </span>
            )}
            <h1 className="truncate text-[22px] font-semibold tracking-[-0.02em] text-ink">
              {meeting.data.title}
            </h1>
          </div>
          <p className="tabular mt-1 text-sm text-text-secondary">
            {formatClock(elapsedMs)} elapsed
            <span className="mx-1.5 text-text-tertiary" aria-hidden="true">·</span>
            {lines.length} {lines.length === 1 ? 'line' : 'lines'} captured
          </p>
        </div>

        <div className="flex items-center gap-2">
          {meeting.data.meeting_url && (
            <a
              href={meeting.data.meeting_url}
              target="_blank"
              rel="noopener noreferrer"
              className={cx(
                'inline-flex h-9 items-center gap-1.5 rounded-lg border border-line-strong px-3',
                'text-[13px] font-medium text-text-secondary transition-colors duration-120',
                'hover:border-muted/40 hover:text-ink', focusRing,
              )}
            >
              <Icon name="meetings" className="size-4" />
              Open Meet
            </a>
          )}
          <Button
            variant="primary"
            size="md"
            onClick={end}
            disabled={finish.isPending}
            className="bg-red-600 hover:bg-red-700"
          >
            {finish.isPending ? (
              <>
                <Spinner className="size-4" />
                Wrapping up…
              </>
            ) : (
              'End meeting'
            )}
          </Button>
        </div>
      </header>

      {finish.isError && (
        <div className="mb-4">
          <InlineError error={finish.error} />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={speech.isListening ? speech.stop : speech.start}
                disabled={!speech.isSupported || !isLive}
                aria-label={speech.isListening ? 'Pause transcription' : 'Start transcription'}
                className={cx(
                  'flex size-11 shrink-0 items-center justify-center rounded-full',
                  'transition-colors duration-120 disabled:opacity-40',
                  focusRing,
                  speech.isListening
                    ? 'bg-red-600 text-white hover:bg-red-700'
                    : 'bg-brand text-white hover:bg-brand-hover',
                )}
              >
                {speech.isListening ? (
                  <span className="size-3 rounded-[2px] bg-white" />
                ) : (
                  <Icon name="meetings" className="size-5" />
                )}
              </button>

              <div className="min-w-0 flex-1">
                <p
                  className={cx(
                    'text-[13px] font-medium',
                    speech.isListening ? 'text-ink' : 'text-amber-700',
                  )}
                >
                  {!speech.isSupported
                    ? 'Speech recognition is unavailable in this browser'
                    : speech.isListening
                      ? 'Listening…'
                      : 'Microphone off — nothing is being captured'}
                </p>
                <p className="mt-0.5 text-[12px] leading-5 text-text-tertiary">
                  {speech.isSupported
                    ? 'Speech is transcribed in this browser and each finished sentence is saved.'
                    : 'Chrome or Edge can transcribe live. You can still type lines in below.'}
                </p>
              </div>

              {/* Who is talking. The browser cannot tell voices apart, so this
                  is set by hand and applied to whatever is captured next. */}
              {participants.length > 0 && (
                <label className="text-[12px] text-text-tertiary">
                  <span className="sr-only">Current speaker</span>
                  <select
                    value={activeSpeaker?.id ?? ''}
                    onChange={(e) => setSpeakerId(e.target.value)}
                    className={cx(
                      'h-8 rounded-lg border border-line-strong bg-surface px-2 text-[12px]',
                      'font-medium text-text-secondary', focusRing,
                    )}
                  >
                    {participants.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.display_name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>

            {speech.error && (
              <p role="alert" className="mt-3 text-[13px] text-red-600">
                {speech.error}
              </p>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={flagMoment}
                disabled={!isLive}
              >
                <Icon name="highlights" className="size-4" />
                Highlight this moment
              </Button>
              <span className="text-[12px] text-text-tertiary">
                Marks the last {HIGHLIGHT_LOOKBACK_MS / 1000}s — find it in Highlights after the call.
              </span>

              {moments.length > 0 && (
                <ul className="flex w-full flex-wrap gap-1.5">
                  {moments.map((moment) => (
                    <li
                      key={moment.key}
                      className={cx(
                        'tabular inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium',
                        moment.failed
                          ? 'bg-red-50 text-red-600'
                          : 'bg-amber-50 text-amber-700',
                      )}
                    >
                      <Icon name="highlights" className="size-3" />
                      {formatClock(moment.atMs)}
                      {moment.pending && <Spinner className="size-2.5" />}
                      {moment.failed && <span>not saved</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Live transcript" description="Saved as each sentence lands." />
            <div ref={feedRef} className="max-h-[440px] overflow-y-auto p-2">
              {lines.length === 0 && !speech.interim && (
                <p className="px-3 py-10 text-center text-[13px] text-text-tertiary">
                  Nothing captured yet. Start the microphone, or type a line below.
                </p>
              )}

              {lines.map((line) => (
                <div key={line.key} className="flex gap-3 rounded-lg px-3 py-2">
                  <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-ink/[0.06] text-[10px] font-semibold text-text-secondary">
                    {initials(line.speaker?.display_name ?? '?')}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="text-[13px] font-semibold text-ink">
                        {line.speaker?.display_name ?? 'Unknown speaker'}
                      </span>
                      <span className="tabular text-[12px] text-text-tertiary">
                        {formatClock(line.startMs)}
                      </span>
                      {line.pending && <Spinner className="size-3 text-text-tertiary" />}
                      {line.failed && (
                        <span className="text-[11px] font-medium text-red-600">not saved</span>
                      )}
                    </div>
                    <p className="mt-0.5 text-[14px] leading-6 text-text-secondary">
                      {line.text}
                    </p>
                  </div>
                </div>
              ))}

              {/* Interim words, shown greyed so it is obvious they are not
                  committed yet. */}
              {speech.interim && (
                <div className="flex gap-3 rounded-lg px-3 py-2 opacity-60">
                  <span className="mt-0.5 size-7 shrink-0 rounded-full bg-ink/[0.04]" />
                  <p className="text-[14px] leading-6 text-text-tertiary italic">
                    {speech.interim}
                  </p>
                </div>
              )}
            </div>

            <CardBody className="border-t border-line">
              <form onSubmit={submitManual} className="flex gap-2">
                <input
                  value={manual}
                  onChange={(e) => setManual(e.target.value)}
                  placeholder="Type a line — useful without a microphone"
                  className={cx(
                    'h-9 min-w-0 flex-1 rounded-lg border border-line-strong bg-surface px-3',
                    'text-[13px] text-ink placeholder:text-text-tertiary', focusRing,
                  )}
                />
                <Button type="submit" size="sm" disabled={!manual.trim()}>
                  Add
                </Button>
              </form>
              {append.isError && (
                <div className="mt-2">
                  <InlineError error={append.error} />
                </div>
              )}
            </CardBody>
          </Card>
        </div>

        <Card>
          <CardHeader title="In the room" />
          <CardBody className="p-0">
            <ul className="divide-y divide-line">
              {participants.map((p) => (
                <li key={p.id} className="flex items-center gap-2.5 px-4 py-2.5">
                  <span
                    className={cx(
                      'flex size-7 items-center justify-center rounded-full text-[10px] font-semibold',
                      p.is_host ? 'bg-brand text-white' : 'bg-ink/[0.06] text-text-secondary',
                    )}
                  >
                    {initials(p.display_name)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium text-ink">
                      {p.display_name}
                    </span>
                    {p.is_host && (
                      <span className="text-[11px] text-text-tertiary">Host</span>
                    )}
                  </span>
                  {activeSpeaker?.id === p.id && speech.isListening && (
                    <span className="size-1.5 animate-pulse rounded-full bg-red-500" />
                  )}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      </div>

      <p className="mt-4 text-[12px] leading-5 text-text-tertiary">
        Ending the meeting derives a summary, decisions, action items and highlights from
        what was said. That extraction is rule-based, not a language model — it quotes the
        transcript rather than paraphrasing it.
      </p>
    </>
  )
}
