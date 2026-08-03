import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import AlertsPage from './pages/AlertsPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import InvestigationPage from './pages/InvestigationPage.jsx'

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <NavLink to="/" className="brand">
          <img className="brand-mark" src="/favicon.svg" alt="" width={28} height={28} />
          <span className="brand-text">
            <span className="brand-name">InsightIQ</span>
            <span className="brand-tag">Ask your data why something changed</span>
          </span>
        </NavLink>
        <nav className="header-nav">
          <NavLink to="/" className={({ isActive }) => (isActive ? 'nav-link is-active' : 'nav-link')} end>
            Dashboard
          </NavLink>
          <NavLink
            to="/alerts"
            className={({ isActive }) => (isActive ? 'nav-link is-active' : 'nav-link')}
          >
            Alerts
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => (isActive ? 'nav-link is-active' : 'nav-link')}>
            Chat
          </NavLink>
        </nav>
        <div className="header-meta">
          <span>Root-cause analytics</span>
        </div>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/dashboard" element={<Navigate to="/" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/investigations/:investigationId" element={<InvestigationPage />} />
        </Routes>
      </main>
    </div>
  )
}
