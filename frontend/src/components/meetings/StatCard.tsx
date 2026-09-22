import { Card } from '../ui/Card'
import Icon, { type IconName } from '../ui/Icon'
import Skeleton from '../ui/Skeleton'

/** One number in the statistics row. */
export function StatCard({
  label,
  value,
  icon,
}: {
  label: string
  value: string
  icon: IconName
}) {
  return (
    <Card className="px-4 py-3.5">
      <div className="flex items-center gap-2 text-text-tertiary">
        <Icon name={icon} className="size-4" />
        <span className="text-[12px] font-medium">{label}</span>
      </div>
      {/* Tabular figures so the four cards' numbers sit on the same rhythm. */}
      <p className="tabular mt-2 text-[26px] leading-none font-semibold tracking-[-0.03em] text-ink">
        {value}
      </p>
    </Card>
  )
}

export function StatCardSkeleton() {
  return (
    <Card className="px-4 py-3.5">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-2.5 h-6 w-16" />
    </Card>
  )
}
