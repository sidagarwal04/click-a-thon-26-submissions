/* The investigation copilot: follow-up Q&A grounded strictly in one subject's
 * already-computed evidence.
 *
 * The model cannot run a query or invent a number (engine/chat.py). If a question is
 * not covered by the evidence it says so, and that refusal is the feature, not a
 * shortfall -- so the starter chips below deliberately include one the evidence does
 * NOT cover. A blank input invites an out-of-scope question by accident and makes the
 * correct refusal read as a broken answer; offering it on purpose makes the same
 * behaviour legible as a guardrail.
 *
 * `initialTurns` comes from the server. Previously the caller hardcoded [], while the
 * API went on feeding the persisted turns to the model as history -- so the model
 * remembered a conversation the operator could not see, and a page reload silently
 * desynchronised the two.
 *
 * LAYOUT CONTRACT
 * Five bands, of which exactly one scrolls. Header, context, chips and input are fixed;
 * the transcript takes the remaining height and scrolls inside itself. That is what lets
 * the panel sit in a sticky rail without the input ever walking off the bottom of the
 * viewport -- the thing that makes a copilot feel like a copilot rather than like a form
 * at the end of a page.
 */

import { useEffect, useRef, useState } from 'react'

import { sendChatMessage, sendIncidentChatMessage } from '../api/client'
import { dateTime } from '../lib/format'
import type { ChatTurn } from '../types'

/** One line of the context card. Label/value pairs rather than named fields, so this
 *  component stays subject-agnostic and the caller decides what is worth showing. */
export interface ChatContextItem {
  label: string
  value: string
}

/** A starter chip. `label` is what fits in a 400px rail; `prompt` is the question actually
 *  asked. They differ because a chip reading "What was ruled out, and with what numbers?"
 *  wraps to three rows and eats the conversation, while a chip reading "Ruled out?" that
 *  SENDS the short form gets a vaguer answer. Short to read, precise to ask. */
export interface ChatSuggestion {
  label: string
  prompt: string
}

interface Props {
  /** Which evidence the answers are grounded in. An incident always exists; an
   *  investigation only exists for the few incidents a sweep fully investigates. */
  subject: 'incident' | 'investigation'
  subjectId: string
  initialTurns: ChatTurn[]
  /** Suggested openers, built by the caller from this subject's own evidence. */
  suggestions?: ChatSuggestion[]
  /** Compact "what am I looking at" card under the header. */
  context?: ChatContextItem[]
}

/* Rotated while a reply is in flight.
 *
 * These are TIME-BASED, not observed. The endpoint is a single non-streaming POST, so the
 * client cannot see which phase the server is in; the labels describe what it is broadly
 * doing (load the evidence bundle, then call the model) rather than reporting measured
 * progress. That is why the animated dots stay: they are the honest indeterminate signal,
 * and a determinate-looking bar next to these words would claim precision that does not
 * exist. Same reasoning that kept a spinner off this component originally. */
const PHASES = ['Thinking', 'Searching evidence', 'Generating answer']
const PHASE_MS = 1800

/** Do two transcripts hold the same conversation? Length plus the last message is
 *  sufficient here — turns are append-only and indexed, so nothing earlier can change
 *  without the tail changing too. */
function sameTurns(a: ChatTurn[], b: ChatTurn[]): boolean {
  if (a === b) return true
  if (a.length !== b.length) return false
  if (a.length === 0) return true
  return a[a.length - 1].content === b[b.length - 1].content
}

function SendIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false" className="copilot-send-icon">
      <path
        d="M3.4 10h6.1M3.1 4.6l13.4 5.4-13.4 5.4 1.7-5.4z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function Chat({ subject, subjectId, initialTurns, suggestions = [], context = [] }: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>(initialTurns)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [phase, setPhase] = useState(0)
  const logRef = useRef<HTMLDivElement>(null)

  // Re-seed when the server's transcript arrives or the subject changes; without this
  // the first render's empty list would stick.
  //
  // Guarded on CONTENT, not identity. An inline `data.chat ?? []` in the caller allocates
  // a fresh array every render, so this effect's deps change every render, so setTurns
  // fires, so it re-renders — an infinite loop that froze the renderer outright rather
  // than merely being slow. An identity check does not break that cycle, because each new
  // array genuinely is a different object; only comparing what is IN them does. The caller
  // memoises too, but this must not depend on the caller remembering.
  useEffect(() => {
    setTurns((prev) => (sameTurns(prev, initialTurns) ? prev : initialTurns))
  }, [initialTurns, subjectId])

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns.length, sending])

  // Advance the waiting label. Reset to the first phase on each new request so a fast
  // reply never opens on "Generating answer".
  useEffect(() => {
    if (!sending) {
      setPhase(0)
      return
    }
    const id = setInterval(() => setPhase((p) => Math.min(p + 1, PHASES.length - 1)), PHASE_MS)
    return () => clearInterval(id)
  }, [sending])

  async function send(text: string) {
    const content = text.trim()
    if (!content || sending) return
    setTurns((t) => [
      ...t,
      { turn_index: t.length, role: 'user', content, created_at: new Date().toISOString() },
    ])
    setMessage('')
    setSending(true)
    setError(null)
    try {
      const res =
        subject === 'incident'
          ? await sendIncidentChatMessage(subjectId, content)
          : await sendChatMessage(subjectId, content)
      if (res.available && res.reply) {
        setTurns((t) => [
          ...t,
          { turn_index: t.length, role: 'assistant', content: res.reply as string, created_at: new Date().toISOString() },
        ])
      } else {
        // Never substitute a guess for an unavailable model. The turn stays in the
        // transcript so it is visible that the question was asked and not answered.
        setError(`The language model is unavailable (${res.provider}): ${res.error ?? 'unknown error'}. Every number on this page stands without it.`)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="copilot">
      <header className="copilot-head">
        <h3>Investigation copilot</h3>
        {/* The trust claims replace a paragraph saying the same thing. Three checks scan
            in about a second; the paragraph did not get read at all. */}
        <ul className="copilot-trust">
          <li>Answers only from this {subject}&rsquo;s evidence</li>
          <li>Never invents or recomputes a number</li>
          <li>Cites the query step behind each figure</li>
        </ul>
      </header>

      {context.length > 0 && (
        <dl className="copilot-context">
          {context.map((c) => (
            <div key={c.label}>
              <dt>{c.label}</dt>
              <dd className="tabular">{c.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {/* Retired once the conversation starts. Openers exist to get a reader past a blank
          box; after the first exchange they are the least useful band in the panel and the
          most expensive, because the rail's height is fixed and every pixel they hold is one
          the transcript cannot have. Hiding them hands ~60px to the messages at exactly the
          moment there are messages to show. The reader still has the input. */}
      {suggestions.length > 0 && turns.length === 0 && (
        <div className="copilot-chips">
          {suggestions.map((s) => (
            <button
              key={s.label}
              type="button"
              className="copilot-chip"
              disabled={sending}
              onClick={() => send(s.prompt)}
              title={s.prompt}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      <div className="copilot-log" ref={logRef} aria-live="polite">
        {turns.length === 0 && !sending && (
          <p className="copilot-empty">
            No questions yet. Pick one above, or ask your own.
          </p>
        )}
        {turns.map((t, i) => (
          <div key={`${t.turn_index}-${i}`} className={`copilot-msg copilot-${t.role}`}>
            <div className="copilot-bubble">{t.content}</div>
            {/* Muted, and only on hover — a timestamp on every turn in a 400px column is
                noise, but it has to be recoverable to reconstruct a session. */}
            <time className="copilot-time" dateTime={t.created_at}>
              {dateTime(t.created_at)}
            </time>
          </div>
        ))}
        {sending && (
          <div className="copilot-msg copilot-assistant">
            <div className="copilot-bubble copilot-pending">
              <span className="chat-dots" aria-hidden="true">
                <i /><i /><i />
              </span>
              <span className="copilot-phase">{PHASES[phase]}…</span>
            </div>
          </div>
        )}
      </div>

      {error && <p className="chat-error">{error}</p>}

      <div className="copilot-input">
        <label className="sr-only" htmlFor={`chat-${subjectId}`}>
          Ask a question about this {subject}
        </label>
        <input
          id={`chat-${subjectId}`}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send(message)}
          placeholder="Ask about this investigation…"
          disabled={sending}
        />
        <button
          type="button"
          className="copilot-send"
          onClick={() => send(message)}
          disabled={sending || !message.trim()}
          aria-label="Send question"
          title="Send"
        >
          <SendIcon />
        </button>
      </div>
    </div>
  )
}
