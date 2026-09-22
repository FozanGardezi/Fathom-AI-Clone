import { NavLink } from 'react-router-dom'

import Icon, { type IconName } from '../ui/Icon'
import { cx, focusRing } from '../../lib/cx'

/** A single sidebar row.
 *
 *  The active state is carried by a tinted background and a weight change
 *  rather than a colour-only shift, so it survives at a glance and for anyone
 *  who cannot separate the two colours.
 */
export default function NavItem({
  to,
  label,
  icon,
  end,
  onNavigate,
}: {
  to: string
  label: string
  icon: IconName
  end?: boolean
  onNavigate?: () => void
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cx(
          'group relative flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13px]',
          'transition-colors duration-120',
          focusRing,
          isActive
            ? 'bg-brand-soft font-semibold text-brand'
            : 'font-medium text-text-secondary hover:bg-ink/[0.04] hover:text-ink',
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            name={icon}
            className={cx(
              'size-[17px] transition-colors duration-120',
              isActive ? 'text-brand' : 'text-text-tertiary group-hover:text-text-secondary',
            )}
          />
          <span className="truncate">{label}</span>
        </>
      )}
    </NavLink>
  )
}
