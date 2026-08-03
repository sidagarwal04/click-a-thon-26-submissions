import { useState } from "react"

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ask } from "@/api/client"

export default function ChatBox({ context }) {
  const [question, setQuestion] = useState("")
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const q = question.trim()
    if (!q || loading) return
    setQuestion("")
    setMessages((m) => [...m, { role: "user", text: q }])
    setLoading(true)
    try {
      const res = await ask(q, context)
      setMessages((m) => [...m, { role: "assistant", text: res.answer }])
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  const contextLabel = context
    ? [context.metric, context.day, context.dimension && context.value ? `${context.dimension}=${context.value}` : null]
        .filter(Boolean)
        .join(" · ")
    : null

  return (
    <div className="space-y-3">
      {contextLabel && (
        <p className="text-xs text-muted-foreground">
          Answering in context of: <span className="font-medium text-foreground">{contextLabel}</span>
        </p>
      )}
      <div className="scroll-thin flex h-[24rem] flex-col gap-3 overflow-y-auto rounded-md border bg-muted/30 p-3">
        {messages.length === 0 && (
          <p className="text-xs text-muted-foreground">
            {context
              ? `Try: "What about fill rate?" - resolves against ${contextLabel} unless you say otherwise.`
              : 'Try: "What was fill rate for Android in APAC yesterday?"'}
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`w-fit max-w-[80%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm shadow-sm ${
                m.role === "user"
                  ? "rounded-br-sm bg-primary text-primary-foreground"
                  : "rounded-bl-sm bg-secondary text-secondary-foreground"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="w-fit rounded-2xl rounded-bl-sm bg-secondary px-3.5 py-2 text-sm text-muted-foreground shadow-sm">
              Thinking…
            </div>
          </div>
        )}
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about a metric, segment, or day…"
          disabled={loading}
          autoFocus
        />
        <Button type="submit" disabled={loading || !question.trim()}>
          Send
        </Button>
      </form>
    </div>
  )
}
