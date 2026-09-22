import { cx, focusRing } from '../../lib/cx'

export type TabItem<T extends string> = {
  id: T
  label: string
  count?: number
}

/**
 * Underlined tab bar.
 *
 * Built from buttons with the ARIA tab roles rather than links, because the
 * page owns the selected tab and mirrors it into the query string itself -
 * that way a tab is deep-linkable without every tab being a route.
 */
export default function Tabs<T extends string>({
  items,
  value,
  onChange,
}: {
  items: TabItem<T>[]
  value: T
  onChange: (id: T) => void
}) {
  return (
    <div
      role="tablist"
      aria-label="Meeting sections"
      // Scrolls rather than wraps on narrow screens: a tab bar that reflows to
      // two rows stops reading as a single control.
      className="-mx-4 flex gap-1 overflow-x-auto border-b border-line px-4 lg:mx-0 lg:px-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {items.map((item) => {
        const isActive = item.id === value
        return (
          <button
            key={item.id}
            role="tab"
            type="button"
            aria-selected={isActive}
            onClick={() => onChange(item.id)}
            className={cx(
              'relative -mb-px flex shrink-0 items-center gap-1.5 rounded-t-md px-3 py-2 text-[13px] whitespace-nowrap',
              'transition-colors duration-120',
              focusRing,
              isActive
                ? 'font-semibold text-ink'
                : 'font-medium text-text-tertiary hover:text-text-secondary',
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span
                className={cx(
                  'tabular rounded px-1 py-0.5 text-[11px] font-medium',
                  isActive ? 'bg-brand-soft text-brand' : 'bg-ink/[0.05] text-text-tertiary',
                )}
              >
                {item.count}
              </span>
            )}
            {/* The rule sits on the container's border line, so the active tab
                reads as connected to the panel below it. */}
            <span
              aria-hidden="true"
              className={cx(
                'absolute inset-x-0 -bottom-px h-0.5 rounded-full transition-colors duration-120',
                isActive ? 'bg-brand' : 'bg-transparent',
              )}
            />
          </button>
        )
      })}
    </div>
  )
}
