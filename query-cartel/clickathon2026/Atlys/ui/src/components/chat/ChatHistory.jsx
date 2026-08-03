/**
 * Past-chats sidebar for the React shell.
 */
export default function ChatHistory({
  conversations,
  activeId,
  loading,
  disabled,
  onSelect,
  onNewChat,
}) {
  return (
    <aside className="chat-history" aria-label="Past chats">
      <div className="chat-history-header">
        <span className="chat-history-title">Chats</span>
        <button
          type="button"
          className="chat-history-new"
          onClick={onNewChat}
          disabled={disabled}
          title="New chat"
          aria-label="New chat"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New
        </button>
      </div>

      <div className="chat-history-list">
        {loading && conversations.length === 0 && (
          <div className="chat-history-empty">Loading…</div>
        )}
        {!loading && conversations.length === 0 && (
          <div className="chat-history-empty">No past chats yet</div>
        )}
        {conversations.map(c => (
          <button
            key={c.id}
            type="button"
            className={`chat-history-item${c.id === activeId ? ' active' : ''}`}
            onClick={() => onSelect(c.id)}
            disabled={disabled && c.id !== activeId}
            title={c.title || 'Chat'}
          >
            <span className="chat-history-item-title">{c.title || 'New chat'}</span>
            {c.updatedAt && (
              <span className="chat-history-item-meta">{formatRelative(c.updatedAt)}</span>
            )}
          </button>
        ))}
      </div>
    </aside>
  )
}

function formatRelative(iso) {
  try {
    const t = new Date(iso).getTime()
    if (Number.isNaN(t)) return ''
    const diff = Date.now() - t
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    if (days < 7) return `${days}d ago`
    return new Date(iso).toLocaleDateString()
  } catch {
    return ''
  }
}
