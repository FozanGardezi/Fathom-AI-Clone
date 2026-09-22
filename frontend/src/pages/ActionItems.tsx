import { useState } from 'react'
import { Link } from 'react-router-dom'

import Button from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import ErrorState, { InlineError } from '../components/ui/ErrorState'
import PageHeader from '../components/ui/PageHeader'
import Skeleton from '../components/ui/Skeleton'
import { formatDateTime, initials } from '../lib/format'
import { cx, focusRing } from '../lib/cx'
import { useAllActionItems, useToggleActionItem } from '../hooks/useWorkspace'
import type { ActionItemWithMeeting } from '../lib/api'

type Filter = 'open' | 'done' | 'all'

const FILTERS: { id: Filter; label: string; completed?: boolean }[] = [
  { id: 'open', label: 'Open', completed: false },
  { id: 'done', label: 'Completed', completed: true },
  { id: 'all', label: 'All' },
]

function DueDate({ item }: { item: ActionItemWithMeeting }) {
  if (!item.due_date) return <span className="text-text-tertiary">No due date</span>
  // Parsed at local noon so a timezone west of UTC cannot roll the date back a day.
  const label = formatDateTime(`${item.due_date}T12:00:00`).replace(/,.*$/, '')
  return (
    <span className={item.is_overdue ? 'font-medium text-red-600' : 'text-text-tertiary'}>
      {item.is_overdue ? 'Overdue · ' : 'Due '}
      {label}
    </span>
  )
}

function Row({ item }: { item: ActionItemWithMeeting }) {
  const toggle = useToggleActionItem()

  return (
    <li className="p-3">
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="checkbox"
          aria-checked={item.completed}
          aria-label={item.completed ? `Reopen ${item.title}` : `Complete ${item.title}`}
          disabled={toggle.isPending}
          onClick={() => toggle.mutate({ id: item.id, patch: { completed: !item.completed } })}
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
              <path d="m5 12.5 4.5 4.5L19 7" stroke="currentColor" strokeWidth="3"
                strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </button>

        <div className="min-w-0 flex-1">
          <p className={cx('text-[13px] leading-5 font-medium',
            item.completed ? 'text-text-tertiary line-through' : 'text-ink')}>
            {item.title}
          </p>
          {item.description && (
            <p className="mt-0.5 text-[13px] leading-5 text-text-tertiary">{item.description}</p>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px]">
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
            <span aria-hidden="true" className="text-text-tertiary">·</span>
            {/* The meeting is the context that makes the task make sense. */}
            <Link
              to={`/meetings/${item.meeting.id}?tab=action-items`}
              className={cx('truncate rounded px-0.5 text-text-secondary',
                'transition-colors duration-120 hover:text-brand', focusRing)}
            >
              {item.meeting.title}
            </Link>
          </div>

          {toggle.isError && (
            <div className="mt-1.5">
              <InlineError error={toggle.error} />
            </div>
          )}
        </div>
      </div>
    </li>
  )
}

export default function ActionItems() {
  const [filter, setFilter] = useState<Filter>('open')
  const completed = FILTERS.find((f) => f.id === filter)?.completed
  const items = useAllActionItems(completed === undefined ? {} : { completed })
  const rows = items.items

  return (
    <>
      <PageHeader
        title="Action Items"
        description="Follow-ups captured across every meeting, soonest first."
      />

      <div className="mb-3 flex items-center gap-1">
        {FILTERS.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setFilter(option.id)}
            aria-pressed={filter === option.id}
            className={cx(
              'rounded-lg px-2.5 py-1 text-[13px] transition-colors duration-120',
              focusRing,
              filter === option.id
                ? 'bg-brand-soft font-semibold text-brand'
                : 'font-medium text-text-tertiary hover:bg-ink/[0.04] hover:text-ink',
            )}
          >
            {option.label}
          </button>
        ))}
        {!items.isPending && !items.isError && (
          <span className="tabular ml-1 text-[12px] text-text-tertiary">
            {items.total}
          </span>
        )}
      </div>

      {items.isPending ? (
        <Card className="p-2">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="flex gap-3 p-3">
              <Skeleton className="size-[18px] rounded-md" />
              <div className="flex-1">
                <Skeleton className="h-3.5 w-2/3" />
                <Skeleton className="mt-2 h-3 w-48" />
              </div>
            </div>
          ))}
        </Card>
      ) : items.isError ? (
        <Card>
          <ErrorState
            error={items.error}
            onRetry={() => items.refetch()}
            title="Couldn't load action items"
          />
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon="action-items"
            title={filter === 'done' ? 'Nothing completed yet' : 'No action items'}
            description={
              filter === 'done'
                ? 'Items you tick off will be collected here.'
                : 'Follow-ups picked up from your meetings will be listed here.'
            }
          />
        </Card>
      ) : (
        <Card className="p-2">
          <ul className="divide-y divide-line">
            {rows.map((item) => (
              <Row key={item.id} item={item} />
            ))}
          </ul>
          {items.hasNextPage && (
            <div className="flex justify-center py-3">
              <Button
                size="sm"
                onClick={() => items.fetchNextPage()}
                disabled={items.isFetchingNextPage}
              >
                {items.isFetchingNextPage
                  ? 'Loading…'
                  : `Show more (${rows.length} of ${items.total})`}
              </Button>
            </div>
          )}
        </Card>
      )}
    </>
  )
}
