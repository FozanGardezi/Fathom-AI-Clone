import type { ActionItem } from '../../../lib/api'
import { Card } from '../../ui/Card'
import EmptyState from '../../ui/EmptyState'
import ErrorState, { InlineError } from '../../ui/ErrorState'
import Icon from '../../ui/Icon'
import Skeleton from '../../ui/Skeleton'
import { formatDateTime, initials } from '../../../lib/format'
import { cx, focusRing } from '../../../lib/cx'
import { useActionItems, useUpdateActionItem } from '../../../hooks/useMeetings'

function DueDate({ item }: { item: ActionItem }) {
  if (!item.due_date) return <span className="text-text-tertiary">No due date</span>
  // Dates arrive as YYYY-MM-DD; parsed as local noon so a timezone west of UTC
  // cannot roll them back a day.
  const label = formatDateTime(`${item.due_date}T12:00:00`).replace(/,.*$/, '')
  return (
    <span className={cx(item.is_overdue ? 'font-medium text-red-600' : 'text-text-tertiary')}>
      {item.is_overdue ? 'Overdue · ' : 'Due '}
      {label}
    </span>
  )
}

function Row({ item, meetingId }: { item: ActionItem; meetingId: string }) {
  const update = useUpdateActionItem(meetingId)
  const isBusy = update.isPending

  return (
    <li className="px-3 py-3">
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="checkbox"
          aria-checked={item.completed}
          aria-label={item.completed ? `Reopen ${item.title}` : `Complete ${item.title}`}
          disabled={isBusy}
          onClick={() => update.mutate({ id: item.id, patch: { completed: !item.completed } })}
          className={cx(
            'mt-0.5 flex size-[18px] shrink-0 items-center justify-center rounded-md border',
            'transition-colors duration-120 disabled:opacity-50',
            focusRing,
            item.completed
              ? 'border-brand bg-brand text-white'
              : 'border-line-strong bg-surface hover:border-brand',
          )}
        >
          {item.completed && (
            <svg viewBox="0 0 24 24" fill="none" className="size-3" aria-hidden="true">
              <path
                d="m5 12.5 4.5 4.5L19 7"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </button>

        <div className="min-w-0 flex-1">
          <p
            className={cx(
              'text-[13px] leading-5 font-medium',
              item.completed ? 'text-text-tertiary line-through' : 'text-ink',
            )}
          >
            {item.title}
          </p>
          {item.description && (
            <p className="mt-0.5 text-[13px] leading-5 text-text-tertiary">{item.description}</p>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
            {item.owner ? (
              <span className="flex items-center gap-1.5 text-text-secondary">
                <span className="flex size-5 items-center justify-center rounded-full bg-ink/[0.06] text-[9px] font-semibold">
                  {initials(item.owner.display_name)}
                </span>
                {item.owner.display_name}
              </span>
            ) : (
              <span className="text-text-tertiary">Unassigned</span>
            )}
            <span aria-hidden="true" className="text-text-tertiary">·</span>
            <DueDate item={item} />
          </div>

          {update.isError && (
            <div className="mt-1.5">
              <InlineError error={update.error} />
            </div>
          )}
        </div>
      </div>
    </li>
  )
}

export default function ActionItemsTab({ meetingId }: { meetingId: string }) {
  const items = useActionItems(meetingId)
  const rows = items.data?.results ?? []
  const open = rows.filter((item) => !item.completed).length

  if (items.isPending) {
    return (
      <Card className="p-2">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="flex gap-3 px-3 py-3">
            <Skeleton className="size-[18px] rounded-md" />
            <div className="flex-1">
              <Skeleton className="h-3.5 w-2/3" />
              <Skeleton className="mt-2 h-3 w-40" />
            </div>
          </div>
        ))}
      </Card>
    )
  }

  if (items.isError) {
    return (
      <Card>
        <ErrorState
          error={items.error}
          onRetry={() => items.refetch()}
          title="Couldn't load action items"
        />
      </Card>
    )
  }

  if (rows.length === 0) {
    return (
      <Card>
        <EmptyState
          icon="action-items"
          title="No action items"
          description="Follow-ups picked up from this meeting will be listed here."
        />
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <p className="flex items-center gap-1.5 text-[13px] text-text-tertiary">
        <Icon name="action-items" className="size-3.5" />
        {open} of {rows.length} still open
      </p>
      <Card className="p-2">
        <ul className="divide-y divide-line">
          {rows.map((item) => (
            <Row key={item.id} item={item} meetingId={meetingId} />
          ))}
        </ul>
      </Card>
    </div>
  )
}
