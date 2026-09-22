import { useSearchParams, useParams } from 'react-router-dom'

import { Card } from '../components/ui/Card'
import ErrorState from '../components/ui/ErrorState'
import Skeleton from '../components/ui/Skeleton'
import Tabs, { type TabItem } from '../components/ui/Tabs'
import ActionItemsTab from '../components/meetings/detail/ActionItemsTab'
import HighlightsTab from '../components/meetings/detail/HighlightsTab'
import MeetingHeader from '../components/meetings/detail/MeetingHeader'
import MeetingPlayer from '../components/meetings/detail/MeetingPlayer'
import SummaryTab from '../components/meetings/detail/SummaryTab'
import TranscriptTab from '../components/meetings/detail/TranscriptTab'
import PlayerProvider from '../components/meetings/detail/PlayerProvider'
import { useMeeting, useTranscriptPages } from '../hooks/useMeetings'
import type { Meeting } from '../lib/api'

const TAB_IDS = ['summary', 'transcript', 'highlights', 'action-items'] as const
type TabId = (typeof TAB_IDS)[number]

function isTabId(value: string | null): value is TabId {
  return TAB_IDS.includes(value as TabId)
}

/** The loading frame. Shaped like the real page so nothing jumps into place. */
function DetailSkeleton() {
  return (
    <>
      <Skeleton className="h-3.5 w-32" />
      <Skeleton className="mt-3 h-7 w-80" />
      <Skeleton className="mt-2 h-3.5 w-64" />
      <Card className="mt-5 p-4">
        <div className="flex items-center gap-3">
          <Skeleton className="size-10 rounded-full" />
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-8 w-16" />
        </div>
      </Card>
      <Skeleton className="mt-5 h-9 w-80" />
      <Card className="mt-4 p-4">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="mt-2 h-3 w-full" />
        <Skeleton className="mt-2 h-3 w-3/4" />
      </Card>
    </>
  )
}

/**
 * Everything below the fold, once the meeting has loaded.
 *
 * Split out so the PlayerProvider can be given a real duration - it needs one
 * to mount, and the meeting is what supplies it.
 */
function MeetingWorkspace({ meeting }: { meeting: Meeting }) {
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const tab: TabId = isTabId(raw) ? raw : 'summary'

  const transcript = useTranscriptPages(meeting.id)

  const tabs: TabItem<TabId>[] = [
    { id: 'summary', label: 'Summary' },
    { id: 'transcript', label: 'Transcript', count: transcript.total || undefined },
    { id: 'highlights', label: 'Highlights', count: meeting.highlights.length || undefined },
    { id: 'action-items', label: 'Action Items', count: meeting.action_items.length || undefined },
  ]

  return (
    // Duration comes from the meeting; a call with no measured length still
    // gets a usable timeline from where the transcript ends.
    <PlayerProvider
      durationMs={
        (meeting.duration_seconds ?? 0) * 1000 ||
        Math.max(0, ...transcript.segments.map((s) => s.end_seconds * 1000))
      }
    >
      <MeetingHeader meeting={meeting} />

      <MeetingPlayer segments={transcript.segments} isLoadingTranscript={transcript.isPending} />

      <Tabs
        items={tabs}
        value={tab}
        // Mirrored into the query string so a tab can be linked to and
        // survives a reload, without making each tab its own route.
        onChange={(next) => setParams({ tab: next }, { replace: true })}
      />

      <div className="mt-4">
        {tab === 'summary' && <SummaryTab meeting={meeting} />}
        {tab === 'transcript' && (
          <TranscriptTab
            meetingId={meeting.id}
            segments={transcript.segments}
            total={transcript.total}
            isPending={transcript.isPending}
            isError={transcript.isError}
            error={transcript.error}
            onRetry={() => transcript.refetch()}
            hasNextPage={Boolean(transcript.hasNextPage)}
            isFetchingNextPage={transcript.isFetchingNextPage}
            onLoadMore={() => transcript.fetchNextPage()}
          />
        )}
        {tab === 'highlights' && <HighlightsTab meetingId={meeting.id} />}
        {tab === 'action-items' && <ActionItemsTab meetingId={meeting.id} />}
      </div>
    </PlayerProvider>
  )
}

export default function MeetingDetail() {
  const { id } = useParams<{ id: string }>()
  const meeting = useMeeting(id)

  if (meeting.isPending) return <DetailSkeleton />

  if (meeting.isError) {
    return (
      <Card>
        <ErrorState
          error={meeting.error}
          onRetry={() => meeting.refetch()}
          title="Couldn't load this meeting"
        />
      </Card>
    )
  }

  return <MeetingWorkspace meeting={meeting.data} />
}
