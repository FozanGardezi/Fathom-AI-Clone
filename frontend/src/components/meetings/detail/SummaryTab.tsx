import { useState } from 'react'

import type { GenerateSummaryTemplate, Meeting, MeetingSummary } from '../../../lib/api'
import { Card, CardBody, CardHeader } from '../../ui/Card'
import Button from '../../ui/Button'
import EmptyState from '../../ui/EmptyState'
import { InlineError } from '../../ui/ErrorState'
import Icon from '../../ui/Icon'
import { Spinner } from '../../ui/LoadingState'
import { cx, focusRing } from '../../../lib/cx'
import { formatDateTime } from '../../../lib/format'
import { useGenerateSummary } from '../../../hooks/useLiveMeeting'

/** The templates offered in the switcher, in the order they read best. `custom`
 *  is left out - it has no extraction rules of its own. */
const TEMPLATES: { id: GenerateSummaryTemplate; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'action_items', label: 'Action items' },
  { id: 'sales_call', label: 'Sales call' },
  { id: 'one_on_one', label: 'One-on-one' },
  { id: 'standup', label: 'Standup' },
  { id: 'interview', label: 'Interview' },
]

/** AI summary under a chosen template, plus its topics and decisions. */
export default function SummaryTab({ meeting }: { meeting: Meeting }) {
  // The server returns every ready summary; fall back to the single primary one
  // so an older cached meeting still renders.
  const summaries: MeetingSummary[] =
    meeting.summaries?.length ? meeting.summaries : meeting.summary ? [meeting.summary] : []

  const generate = useGenerateSummary(meeting.id)

  const byTemplate = new Map(summaries.map((s) => [s.template, s]))
  // Default to the newest generated summary's template, else the first offered.
  const [selected, setSelected] = useState<GenerateSummaryTemplate>(() => {
    const first = summaries[0]?.template
    return (TEMPLATES.find((t) => t.id === first)?.id) ?? 'general'
  })

  if (summaries.length === 0) {
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

  const active = byTemplate.get(selected) ?? null

  function switchTo(template: GenerateSummaryTemplate) {
    setSelected(template)
    generate.reset()
  }

  function generateSelected() {
    generate.mutate({ template: selected })
  }

  return (
    <div className="space-y-4">
      {/* Template switcher. A template already generated selects instantly; one
          that is not offers to generate it, since each is derived on demand. */}
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Summary template">
        {TEMPLATES.map((template) => {
          const isSelected = template.id === selected
          const isReady = byTemplate.has(template.id)
          return (
            <button
              key={template.id}
              type="button"
              role="tab"
              aria-selected={isSelected}
              onClick={() => switchTo(template.id)}
              className={cx(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium',
                'transition-colors duration-120', focusRing,
                isSelected
                  ? 'bg-brand text-white'
                  : 'bg-ink/[0.04] text-text-secondary hover:bg-ink/[0.08]',
              )}
            >
              {template.label}
              {!isReady && (
                <span
                  className={cx(
                    'text-[10px]',
                    isSelected ? 'text-white/70' : 'text-text-tertiary',
                  )}
                >
                  ·&nbsp;new
                </span>
              )}
            </button>
          )
        })}
      </div>

      {active ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
          <Card>
            <CardHeader
              title="Summary"
              description={
                active.generated_at ? `Generated ${formatDateTime(active.generated_at)}` : undefined
              }
            />
            <CardBody>
              {/* Wide enough to be dense, capped so the lines stay readable.
                  whitespace-pre-line keeps the per-line templates (standup,
                  action items) readable rather than running them together. */}
              <p className="max-w-[68ch] whitespace-pre-line text-[14px] leading-6 text-text-secondary">
                {active.summary}
              </p>
            </CardBody>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader title="Key topics" />
              <CardBody className="p-0">
                {active.topics.length === 0 ? (
                  <p className="px-4 py-3 text-[13px] text-text-tertiary">None recorded.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {active.topics.map((topic) => (
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
                {active.decisions.length === 0 ? (
                  <p className="px-4 py-3 text-[13px] text-text-tertiary">None recorded.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {active.decisions.map((decision) => (
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
      ) : (
        // The selected template has not been generated yet.
        <Card>
          <CardBody className="flex flex-col items-start gap-3">
            <div>
              <p className="text-[14px] font-medium text-ink">
                {TEMPLATES.find((t) => t.id === selected)?.label} summary not generated yet
              </p>
              <p className="mt-1 max-w-[60ch] text-[13px] leading-5 text-text-secondary">
                It reads the same transcript as the others, framed for this template. Nothing is
                invented — it quotes what was said.
              </p>
            </div>
            <Button variant="primary" size="sm" onClick={generateSelected} disabled={generate.isPending}>
              {generate.isPending ? (
                <>
                  <Spinner className="size-4" />
                  Generating…
                </>
              ) : (
                'Generate'
              )}
            </Button>
            {generate.isError && <InlineError error={generate.error} />}
          </CardBody>
        </Card>
      )}
    </div>
  )
}
