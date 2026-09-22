import Icon, { type IconName } from './Icon'

/** Placeholder body used by every route until its real content lands. */
export default function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: IconName
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-4 flex size-11 items-center justify-center rounded-xl border border-line bg-canvas text-text-tertiary">
        <Icon name={icon} className="size-5" />
      </div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1.5 max-w-sm text-[13px] leading-5 text-text-tertiary">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
