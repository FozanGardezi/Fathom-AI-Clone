import type { IconName } from '../components/ui/Icon'

export type NavItem = {
  label: string
  to: string
  icon: IconName
  /** Only `/` should match exactly; the rest stay active on their children,
   *  so /meetings/:id keeps Meetings lit. */
  end?: boolean
}

/** One source of truth for the sidebar, the mobile drawer and the page title
 *  in the top bar. Adding a section here is all it takes to add it everywhere. */
export const NAV_ITEMS: NavItem[] = [
  { label: 'Meetings', to: '/meetings', icon: 'meetings' },
  { label: 'Calendar', to: '/calendar', icon: 'calendar' },
  { label: 'Highlights', to: '/highlights', icon: 'highlights' },
  { label: 'Action Items', to: '/action-items', icon: 'action-items' },
  { label: 'Search', to: '/search', icon: 'search' },
  { label: 'Settings', to: '/settings', icon: 'settings' },
]
