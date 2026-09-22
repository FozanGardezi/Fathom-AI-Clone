import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import Icon from '../ui/Icon'
import { cx, focusRing } from '../../lib/cx'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

/**
 * The frame every route renders inside: a docked sidebar from `lg` up, a
 * sticky top bar, and a scrolling main column.
 *
 * Below `lg` the sidebar becomes an overlay drawer. It is rendered in the DOM
 * at all times and translated off-screen so opening and closing can animate,
 * and it is hidden from assistive technology while closed.
 */
export default function AppShell() {
  const [navOpen, setNavOpen] = useState(false)
  const { pathname } = useLocation()
  const [lastPath, setLastPath] = useState(pathname)

  // Following a link should never leave the drawer sitting over the page it
  // just navigated to. Adjusting during render rather than in an effect keeps
  // it to one render pass, and catches back/forward as well as link clicks.
  if (pathname !== lastPath) {
    setLastPath(pathname)
    setNavOpen(false)
  }

  // Escape closes the drawer, and the page behind it must not scroll while it
  // is open.
  useEffect(() => {
    if (!navOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setNavOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = ''
    }
  }, [navOpen])

  return (
    <div className="flex min-h-full">
      {/* Docked rail. `lg:` only - the drawer below covers everything else. */}
      <aside className="hidden w-[228px] shrink-0 border-r border-line lg:block">
        <div className="sticky top-0 h-screen">
          <Sidebar />
        </div>
      </aside>

      {/* Mobile drawer. */}
      <div
        className={cx(
          'fixed inset-0 z-50 lg:hidden',
          navOpen ? 'pointer-events-auto' : 'pointer-events-none',
        )}
        aria-hidden={!navOpen}
      >
        <button
          type="button"
          tabIndex={navOpen ? 0 : -1}
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
          className={cx(
            'absolute inset-0 bg-ink/25 transition-opacity duration-200',
            navOpen ? 'opacity-100' : 'opacity-0',
          )}
        />
        <div
          className={cx(
            'absolute inset-y-0 left-0 w-[260px] border-r border-line shadow-xl',
            'transition-transform duration-200 ease-out',
            navOpen ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          <button
            type="button"
            tabIndex={navOpen ? 0 : -1}
            onClick={() => setNavOpen(false)}
            aria-label="Close navigation"
            className={cx(
              'absolute top-3.5 right-3 flex size-8 items-center justify-center rounded-lg',
              'text-text-secondary transition-colors duration-120 hover:bg-ink/[0.04] hover:text-ink',
              focusRing,
            )}
          >
            <Icon name="close" />
          </button>
          <Sidebar onNavigate={() => setNavOpen(false)} />
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onOpenNav={() => setNavOpen(true)} />
        <main className="flex-1 px-4 py-6 lg:px-6 lg:py-8">
          {/* Capped so dense tables stay readable on very wide displays. */}
          <div className="mx-auto w-full max-w-[1180px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
