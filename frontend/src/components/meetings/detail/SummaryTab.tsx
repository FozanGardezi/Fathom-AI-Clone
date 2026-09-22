import type { Meeting } from '../../../lib/api'
import { Card, CardBody, CardHeader } from '../../ui/Card'
import EmptyState from '../../ui/EmptyState'
import Icon from '../../ui/Icon'
import { formatDateTime } from '../../../lib/format'

/** AI summary, key topics and decisions. */
export default function SummaryTab({ meeting }: { meeting: Meeting }) {
  const { summary, topics, decisions } = meeting

  if (!summary) {
    return (
      <Card>
        <EmptyState
          icon="meetings"
          title="No summary yet"
          description={
            meeting.status === 'ready'
              ? 'This meeting has no generated summary.'
              : 'A summary is generated once the recording finishes processing.'
          }
        />
      </Card>
    )
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
      <Card>
        <CardHeader
          title="Summary"
          description={
            summary.generated_at ? `Generated ${formatDateTime(summary.generated_at)}` : undefined
          }
        />
        <CardBody>
          {/* Wide enough to be dense, capped so the lines stay readable. */}
          <p className="max-w-[68ch] text-[14px] leading-6 text-text-secondary">
            {summary.summary}
          </p>
        </CardBody>
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader title="Key topics" />
          <CardBody className="p-0">
            {topics.length === 0 ? (
              <p className="px-4 py-3 text-[13px] text-text-tertiary">None recorded.</p>
            ) : (
              <ul className="divide-y divide-line">
                {topics.map((topic) => (
                  <li key={topic} className="px-4 py-2.5 text-[13px] leading-5 text-text-secondary">
                    {topic}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Decisions" />
          <CardBody className="p-0">
            {decisions.length === 0 ? (
              <p className="px-4 py-3 text-[13px] text-text-tertiary">None recorded.</p>
            ) : (
              <ul className="divide-y divide-line">
                {decisions.map((decision) => (
                  <li key={decision} className="flex gap-2.5 px-4 py-2.5">
                    <Icon
                      name="action-items"
                      className="mt-0.5 size-3.5 shrink-0 text-emerald-600"
                    />
                    <span className="text-[13px] leading-5 text-text-secondary">{decision}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
