import { useState, useEffect, useRef, useCallback } from 'react'
import './index.css'
import ChatPanel from './components/chat/ChatPanel'
import Dashboard from './components/dashboard/Dashboard'
import StatusBar from './components/common/StatusBar'
import { getAgentStatus } from './api/client'
import DocumentPreview from './components/chat/DocumentPreview'

const MIN_LEFT_PCT  = 25   // minimum left panel width %
const MAX_LEFT_PCT  = 75   // maximum left panel width %
const DEFAULT_LEFT_PCT = 75

export default function App() {
  const [langfuseBaseUrl, setLangfuseBaseUrl]     = useState('https://us.cloud.langfuse.com')
  const [langfuseProjectId, setLangfuseProjectId] = useState(null)
  const [leftPct, setLeftPct] = useState(DEFAULT_LEFT_PCT)
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [previewPath, setPreviewPath] = useState(null)
  const dragging  = useRef(false)
  const shellRef  = useRef(null)

  const triggerRefresh = useCallback(() => {
    setRefreshTrigger(prev => prev + 1)
  }, [])

  useEffect(() => {
    getAgentStatus()
      .then(status => {
        if (status?.langfuse_base_url)    setLangfuseBaseUrl(status.langfuse_base_url)
        if (status?.langfuse_project_id)  setLangfuseProjectId(status.langfuse_project_id)
      })
      .catch(() => {})
  }, [])

  // ── Drag-to-resize ─────────────────────────────────────────────────────────
  const onMouseDown = useCallback((e) => {
    e.preventDefault()
    dragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  useEffect(() => {
    const onMove = (e) => {
      if (!dragging.current || !shellRef.current) return
      const rect = shellRef.current.getBoundingClientRect()
      const pct  = ((e.clientX - rect.left) / rect.width) * 100
      setLeftPct(Math.min(MAX_LEFT_PCT, Math.max(MIN_LEFT_PCT, pct)))
    }
    const onUp = () => {
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  return (
    <div className="app-shell" ref={shellRef}>
      {/* Header spans full width */}
      <header className="app-header">
        <div className="logo-wrap" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <img src="/logo.png" alt="Atlys Logo" className="logo-img" style={{ height: 26, width: 'auto', borderRadius: '4px' }} />
          <span className="logo" style={{ fontWeight: 800 }}>Atlys Copilot</span>
        </div>
        <span className="subtitle" style={{ marginLeft: 6 }}>Feature spec to ClickHouse schema and PM insight</span>
        <div className="header-spacer" />
        <StatusBar />
      </header>

      {/* Resizable body */}
      <div
        className="app-body"
        style={{ '--left-pct': `${leftPct}%` }}
      >
        {/* Left panel: Chat */}
        <div className="panel panel-left chat-panel-wrap">
          <ChatPanel
            langfuseBaseUrl={langfuseBaseUrl}
            langfuseProjectId={langfuseProjectId}
            onRefresh={triggerRefresh}
            onPreview={setPreviewPath}
          />
        </div>

        {/* Drag handle */}
        <div className="resize-handle" onMouseDown={onMouseDown} title="Drag to resize">
          <div className="resize-handle-bar" />
        </div>

        {/* Right panel: Dashboard */}
        <div className="panel panel-right">
          <Dashboard
            langfuseBaseUrl={langfuseBaseUrl}
            langfuseProjectId={langfuseProjectId}
            refreshTrigger={refreshTrigger}
          />
        </div>
      </div>
      {previewPath && (
        <DocumentPreview path={previewPath} onClose={() => setPreviewPath(null)} />
      )}
    </div>
  )
}
