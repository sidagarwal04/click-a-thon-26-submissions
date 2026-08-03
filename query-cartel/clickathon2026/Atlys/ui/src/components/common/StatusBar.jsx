import { useState, useEffect } from 'react'
import { getAgentStatus } from '../../api/client'

export default function StatusBar() {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    let mounted = true
    const check = () =>
      getAgentStatus().then(s => { if (mounted) setStatus(s) }).catch(() => {})

    check()
    const id = setInterval(check, 10000)
    return () => { mounted = false; clearInterval(id) }
  }, [])

  if (!status) return null

  const dotClass = status.provisioned ? '' : 'not-ready'
  const label = status.provisioned
    ? `Agent: ${status.agent_name}`
    : 'Connecting to LibreChat...'

  return (
    <div className="status-bar">
      <span className={`status-dot ${dotClass}`} />
      <span>{label}</span>
    </div>
  )
}
