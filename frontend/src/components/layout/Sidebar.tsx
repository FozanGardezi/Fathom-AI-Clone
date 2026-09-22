import { Link } from 'react-router-dom'

import { NAV_ITEMS } from '../../lib/navigation'
import Icon from '../ui/Icon'
import { focusRing } from '../../lib/cx'
import NavItem from './NavItem'

/** The sidebar's contents.
 *
 *  Rendered twice - once docked on large screens, once inside the mobile
 *  drawer - so it takes `onNavigate` to let the drawer close itself when a
 *  link is followed.
 */
export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col bg-rail">
      {/* The wordmark doubles as the link home, which is why Overview needs no
          row of its own in the nav list. */}
      <div className="flex h-14 items-center px-3">
        <Link
          to="/"
          onClick={onNavigate}
          className={`flex items-center gap-2 rounded-lg px-1.5 py-1 ${focusRing}`}
        >
          <span className="flex size-6 items-center justify-center rounded-md bg-brand text-white">
            <Icon name="logo" className="size-4" />
          </span>
          <span className="text-[15px] font-semibold tracking-[-0.02em] text-ink">Fathom</span>
        </Link>
      </div>

      <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {NAV_ITEMS.map((item) => (
          <NavItem key={item.to} {...item} onNavigate={onNavigate} />
        ))}
      </nav>

      <div className="border-t border-line px-3 py-3">
        <div className="rounded-lg border border-line bg-surface px-3 py-2.5">
          <p className="text-[11px] font-semibold tracking-wide text-text-tertiary uppercase">
            Workspace
          </p>
          <p className="mt-0.5 truncate text-[13px] font-medium text-ink">Fathom AI</p>
        </div>
      </div>
    </div>
  )
}
