import { Card } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import PageHeader from '../components/ui/PageHeader'

export default function Search() {
  return (
    <>
      <PageHeader title="Search" description="Search across transcripts, summaries and decisions." />
      <Card>
        <EmptyState
          icon="search"
          title="Search is not wired up yet"
          description="Once indexing lands, this will search summaries and decisions first, then transcripts."
        />
      </Card>
    </>
  )
}
