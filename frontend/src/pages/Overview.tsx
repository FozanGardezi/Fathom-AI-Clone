import { Link } from 'react-router-dom'

import { Card, CardBody, CardHeader } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Icon from '../components/ui/Icon'
import PageHeader from '../components/ui/PageHeader'
import { NAV_ITEMS } from '../lib/navigation'
import { useHealth, useSession } from '../hooks/useSession'
import { focusRing } from '../lib/cx'

/** Landing page at `/`. Reached from the wordmark rather than a nav row. */
export default function Overview() {
  const session = useSession()
  const health = useHealth()

  return (
    <>
      <PageHeader
        title="Overview"
        description={
          session.user ? `Signed in as ${session.user.email}` : 'Your workspace at a glance.'
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {NAV_ITEMS.filter((item) => item.to !== '/settings').map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className={`group rounded-xl ${focusRing}`}
          >
            <Card className="h-full transition-colors duration-120 group-hover:border-line-strong">
              <CardBody className="flex items-start gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg border border-line bg-canvas text-text-tertiary transition-colors duration-120 group-hover:text-brand">
                  <Icon name={item.icon} />
                </span>
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-ink">{item.label}</p>
                  <p className="mt-0.5 text-[13px] leading-5 text-text-tertiary">
                    Nothing here yet.
                  </p>
                </div>
                <Icon
                  name="chevron-right"
                  className="ml-auto size-4 text-text-tertiary opacity-0 transition-opacity duration-120 group-hover:opacity-100"
                />
              </CardBody>
            </Card>
          </Link>
        ))}
      </div>

      <Card className="mt-4">
        <CardHeader title="System" description="Live status from the API." />
        <CardBody className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px]">
          <span className="flex items-center gap-2 text-text-secondary">
            API
            <Badge tone={health.data?.status === 'ok' ? 'positive' : 'neutral'}>
              {health.data?.status ?? 'checking…'}
            </Badge>
          </span>
          <span className="flex items-center gap-2 text-text-secondary">
            Database
            <Badge tone={health.data?.database === 'ok' ? 'positive' : 'neutral'}>
              {health.data?.database ?? 'checking…'}
            </Badge>
          </span>
        </CardBody>
      </Card>
    </>
  )
}
