import { cx } from '../../lib/cx'

/** The one raised surface in the system: white, hairline border, no shadow
 *  beyond a whisper. Everything on a page sits in one of these. */
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx('rounded-xl border border-line bg-surface shadow-xs', className)}
      {...props}
    />
  )
}

/** Optional header strip. Keeps the divider and padding consistent across
 *  every card that has a title. */
export function CardHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line px-4 py-3">
      <div className="min-w-0">
        <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
        {description && (
          <p className="mt-0.5 text-[13px] leading-5 text-text-tertiary">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('p-4', className)} {...props} />
}
