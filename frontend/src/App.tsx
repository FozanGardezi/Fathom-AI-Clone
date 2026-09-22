import { Navigate, Route, Routes } from 'react-router-dom'

import AppShell from './components/layout/AppShell'
import { tokens } from './lib/api'
import ActionItems from './pages/ActionItems'
import Calendar from './pages/Calendar'
import Highlights from './pages/Highlights'
import Login from './pages/Login'
import MeetingDetail from './pages/MeetingDetail'
import Meetings from './pages/Meetings'
import Overview from './pages/Overview'
import Search from './pages/Search'
import Settings from './pages/Settings'

function RequireAuth({ children }: { children: React.ReactNode }) {
  return tokens.access ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      {/* Everything else renders inside the shell, so the sidebar and top bar
          mount once and survive navigation between sections. */}
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Overview />} />
        <Route path="/meetings" element={<Meetings />} />
        <Route path="/meetings/:id" element={<MeetingDetail />} />
        <Route path="/calendar" element={<Calendar />} />
        <Route path="/highlights" element={<Highlights />} />
        <Route path="/action-items" element={<ActionItems />} />
        <Route path="/search" element={<Search />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
