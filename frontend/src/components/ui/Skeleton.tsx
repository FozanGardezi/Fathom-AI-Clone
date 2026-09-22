import { cx } from '../../lib/cx'

/**
 * A shimmering placeholder block.
 *
 * Skeletons are sized to the content they stand in for, so the layout does not
 * jump when the data lands - which is the whole point of using one instead of
 * a spinner.
 */
export default function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cx('animate-pulse rounded-md bg-ink/[0.06]', className ?? 'h-4 w-full')}
    />
  )
}
