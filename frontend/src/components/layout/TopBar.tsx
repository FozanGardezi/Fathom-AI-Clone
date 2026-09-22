import { useLocation } from 'react-router-dom'

import { NAV_ITEMS } from '../../lib/navigation'
import Button from '../ui/Button'
import Icon from '../ui/Icon'
import { cx, focusRing } from '../../lib/cx'

/** Longest matching nav route wins, so /meetings/:id still reads "Meetings". */
function useSectionLabel() {
  const { pathname } = useLocation()
  const match = NAV_ITEMS.filter((item) => pathname.startsWith(item.to)).sort(
    (a, b) => b.to.length - a.to.length,
  )[0]
  return match?.label ?? 'Overview'
}

export default function TopBar({ onOpenNav }: { onOpenNav: () => void }) {
  const section = useSectionLabel()

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface/85 px-4 backdrop-blur-sm lg:px-6">
      <button
        type="button"
        onClick={onOpenNav}
        aria-label="Open navigation"
        className={cx(
          'flex size-8 items-center justify-center rounded-lg text-text-secondary',
          'transition-colors duration-120 hover:bg-ink/[0.04] hover:text-ink lg:hidden',
          focusRing,
        )}
      >
        <Icon name="menu" />
      </button>

      <p className="truncate text-[13px] font-semibold text-ink">{section}</p>

      <div className="ml-auto flex items-center gap-1.5">
        {/* A button rather than an input: search is its own route, and a fake
            input that navigates away on focus is a small lie. */}
        <button
          type="button"
          className={cx(
            'hidden h-8 items-center gap-2 rounded-lg border border-line-strong bg-surface pr-1.5 pl-2.5 sm:flex',
            'text-[13px] text-text-tertiary transition-colors duration-120',
            'hover:border-muted/40 hover:text-text-secondary',
            focusRing,
          )}
        >
          <Icon name="search" className="size-4" />
          <span>Search</span>
          <kbd className="tabular ml-4 rounded border border-line bg-canvas px-1.5 py-0.5 font-sans text-[11px] text-text-tertiary">
            ⌘K
          </kbd>
        </button>

        <Button variant="ghost" size="sm" aria-label="Notifications" className="px-1.5">
          <Icon name="bell" />
        </Button>

        <div className="mx-1 h-5 w-px bg-line" />

        <button
          type="button"
          className={cx(
            'flex items-center gap-2 rounded-lg py-1 pr-1.5 pl-1',
            'transition-colors duration-120 hover:bg-ink/[0.04]',
            focusRing,
          )}
        >
          <span className="flex size-7 items-center justify-center rounded-full bg-brand-soft text-[11px] font-semibold text-brand">
            FG
          </span>
          <Icon name="chevron-down" className="size-3.5 text-text-tertiary" />
        </button>
      </div>
    </header>
  )
}
