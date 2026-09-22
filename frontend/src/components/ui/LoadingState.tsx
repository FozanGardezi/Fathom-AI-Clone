import { cx } from '../../lib/cx'

/** Indeterminate spinner. Inherits `currentColor`, so it takes the tone of
 *  whatever it sits in. */
export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cx('animate-spin', className ?? 'size-4')}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.18" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

/** The loading body for a panel whose contents have not arrived.
 *
 *  `aria-busy` and the live region mean a screen reader announces the wait
 *  instead of reading an empty panel. */
export default function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      role="status"
      aria-busy="true"
      className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center"
    >
      <Spinner className="size-5 text-text-tertiary" />
      <p className="text-[13px] text-text-tertiary">{label}</p>
    </div>
  )
}
