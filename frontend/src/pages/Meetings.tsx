import { useState } from 'react'

import Button from '../components/ui/Button'
import Icon from '../components/ui/Icon'
import LiveNowBanner from '../components/live/LiveNowBanner'
import NewMeetingDialog from '../components/live/NewMeetingDialog'
import MeetingSection from '../components/meetings/MeetingSection'
import MeetingStats from '../components/meetings/MeetingStats'
import Skeleton from '../components/ui/Skeleton'
import { firstName, greeting } from '../lib/format'
import { useMeetings } from '../hooks/useMeetings'
import { useSession } from '../hooks/useSession'

/**
 * The meetings dashboard.
 *
 * Three independent queries - upcoming, recent and statistics - rather than
 * one. Each section then loads, fails and retries on its own, so a stats
 * request that falls over does not take the meetings list down with it.
 */
export default function Meetings() {
  const session = useSession()
  const [isStarting, setIsStarting] = useState(false)

  // Two filtered queries rather than one list split client-side: "upcoming"
  // and "recent" are genuinely different questions, and splitting a page of
  // results would only ever see the meetings that happened to be on it.
  const upcoming = useMeetings({ status: 'scheduled', ordering: 'scheduled_start' })
  const recent = useMeetings({ status: 'ready', ordering: '-started_at' })

  return (
    <>
      <header className="mb-6">
        {session.isPending ? (
          <Skeleton className="h-7 w-64" />
        ) : (
          <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-ink">
            {greeting()}, {firstName(session.user?.full_name, session.user?.email)}
          </h1>
        )}
        <p className="mt-1 text-sm leading-5 text-text-secondary">
          Here's what's happened across your meetings.
        </p>
      </header>

      <LiveNowBanner />

      <MeetingStats />

      <MeetingSection
        title="Upcoming"
        count={upcoming.data?.count}
        meetings={upcoming.data?.results ?? []}
        variant="upcoming"
        isPending={upcoming.isPending}
        isError={upcoming.isError}
        error={upcoming.error}
        onRetry={() => upcoming.refetch()}
        emptyIcon="calendar"
        emptyTitle="Nothing scheduled"
        emptyDescription="Meetings from your connected calendars will appear here before they start."
        skeletonCount={2}
      />

      <MeetingSection
        title="Recent"
        count={recent.data?.count}
        meetings={recent.data?.results ?? []}
        isPending={recent.isPending}
        isError={recent.isError}
        error={recent.error}
        onRetry={() => recent.refetch()}
        emptyIcon="meetings"
        emptyTitle="No meetings yet"
        emptyDescription="Once a call has been recorded and processed, it will show up here with its summary."
        action={
          <Button variant="primary" size="sm" onClick={() => setIsStarting(true)}>
            <Icon name="plus" className="size-4" />
            New meeting
          </Button>
        }
      />

      {isStarting && <NewMeetingDialog onClose={() => setIsStarting(false)} />}
    </>
  )
}
