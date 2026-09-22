import type { MeetingStatus } from '../../lib/api'
import { STATUS_LABELS } from '../../lib/format'
import { cx } from '../../lib/cx'

/** Status as a dot plus a word.
 *
 *  The dot carries the colour and the word carries the meaning, so the state
 *  is still readable without separating the colours. */
const TONES: Record<MeetingStatus, { dot: string; text: string }> = {
  ready: { dot: 'bg-emerald-500', text: 'text-text-secondary' },
  recording: { dot: 'bg-red-500 animate-pulse', text: 'text-red-600' },
  processing: { dot: 'bg-amber-500', text: 'text-amber-700' },
  scheduled: { dot: 'bg-slate-400', text: 'text-text-secondary' },
  failed: { dot: 'bg-red-500', text: 'text-red-600' },
}

export default function StatusPill({ status }: { status: MeetingStatus }) {
  const tone = TONES[status]
  return (
    <span className={cx('inline-flex items-center gap-1.5 text-[12px] font-medium', tone.text)}>
      <span className={cx('size-1.5 rounded-full', tone.dot)} />
      {STATUS_LABELS[status]}
    </span>
  )
}
