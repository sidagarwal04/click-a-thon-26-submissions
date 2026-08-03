export default function StatusPill({ status, children }) {
  const key = String(status || 'neutral').toLowerCase()
  return <span className={`status-pill ${key}`}>{children ?? status}</span>
}
