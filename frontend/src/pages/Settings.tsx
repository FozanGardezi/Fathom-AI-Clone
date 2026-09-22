import { Card } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import PageHeader from '../components/ui/PageHeader'

export default function Settings() {
  return (
    <>
      <PageHeader title="Settings" description="Workspace, members and integrations." />
      <Card>
        <EmptyState
          icon="settings"
          title="Settings are on the way"
          description="Profile, notification and integration preferences will live here."
        />
      </Card>
    </>
  )
}
