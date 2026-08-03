import { useNavigate } from 'react-router-dom'

export default function AskInChatButton({ alertId, investigationId, question }) {
  const navigate = useNavigate()
  const prompt =
    question ||
    `What else could explain alert ${alertId}? Use investigation evidence and only cite numbers from the package.`

  function openChat() {
    const params = new URLSearchParams()
    params.set('q', prompt)
    if (investigationId) params.set('investigationId', investigationId)
    if (alertId) params.set('alertId', alertId)
    navigate(`/chat?${params.toString()}`)
  }

  return (
    <button type="button" className="btn btn-primary" onClick={openChat}>
      Ask in chat
    </button>
  )
}
