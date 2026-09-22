/**
 * Inline icon set.
 *
 * Hand-rolled rather than pulled from a package: the shell needs a dozen
 * glyphs, and a consistent 24px grid with a 1.5 stroke keeps them optically
 * matched in a way mixing icon sets does not. `currentColor` throughout, so an
 * icon takes the colour of whatever it sits in.
 */
import { cx } from '../../lib/cx'

export type IconName =
  | 'meetings'
  | 'calendar'
  | 'highlights'
  | 'action-items'
  | 'search'
  | 'settings'
  | 'menu'
  | 'close'
  | 'bell'
  | 'plus'
  | 'chevron-right'
  | 'chevron-down'
  | 'logo'

const PATHS: Record<IconName, React.ReactNode> = {
  meetings: (
    <>
      <rect x="2.75" y="5.75" width="12.5" height="12.5" rx="2.5" />
      <path d="M15.25 10.5 21.25 7v10l-6-3.5" />
    </>
  ),
  calendar: (
    <>
      <rect x="3.25" y="4.75" width="17.5" height="16" rx="2.5" />
      <path d="M3.25 9.25h17.5M8 2.75v4M16 2.75v4" />
    </>
  ),
  highlights: (
    <path d="M12 3.5l2.6 5.27 5.82.85-4.21 4.1.99 5.78L12 16.77l-5.2 2.73.99-5.78-4.21-4.1 5.82-.85z" />
  ),
  'action-items': (
    <>
      <rect x="3.25" y="3.75" width="17.5" height="17" rx="3" />
      <path d="m8 12.25 2.75 2.75L16.25 9.5" />
    </>
  ),
  search: (
    <>
      <circle cx="10.75" cy="10.75" r="6.5" />
      <path d="m15.5 15.5 4.75 4.75" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2.25" />
      <circle cx="8" cy="17" r="2.25" />
    </>
  ),
  menu: <path d="M3.75 6.5h16.5M3.75 12h16.5M3.75 17.5h16.5" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  bell: (
    <>
      <path d="M6.25 9.5a5.75 5.75 0 0 1 11.5 0c0 4 1.25 5.5 1.25 5.5H5s1.25-1.5 1.25-5.5Z" />
      <path d="M10.25 18.5a1.9 1.9 0 0 0 3.5 0" />
    </>
  ),
  plus: <path d="M12 5.75v12.5M5.75 12h12.5" />,
  'chevron-right': <path d="m9.5 5.75 6.25 6.25-6.25 6.25" />,
  'chevron-down': <path d="m5.75 9.5 6.25 6.25 6.25-6.25" />,
  logo: (
    <>
      <path d="M4.5 12a7.5 7.5 0 0 1 13.2-4.85" />
      <path d="M19.5 12a7.5 7.5 0 0 1-13.2 4.85" />
      <circle cx="12" cy="12" r="2.4" />
    </>
  ),
}

type IconProps = {
  name: IconName
  className?: string
}

export default function Icon({ name, className }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={cx('shrink-0', className ?? 'size-[18px]')}
    >
      {PATHS[name]}
    </svg>
  )
}
