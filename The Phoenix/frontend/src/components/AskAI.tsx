'use client'

import {useEffect, useRef, useState} from 'react'
import {LLM_PRESETS, type LlmProvider} from '@/lib/ask.presets'
import ReactMarkdown from 'react-markdown'
import styles from './AskAI.module.css'
import type {AskMessage} from '@/lib/types'

async function safeJson(res: Response): Promise<any> {
  const text = await res.text()
  try {
    return JSON.parse(text)
  } catch {
    return {error: text.trim().slice(0, 140) || `${res.status} ${res.statusText}`}
  }
}

interface Props {
  /** Which console is asking. /api/ask is pinned to phoenix, /api/v2/ask to phoenix_next. The
   *  endpoint is the ONLY thing that differs between the two, and the database it may read is
   *  fixed server-side rather than sent from here: a client that could name its own database
   *  would hand that choice to anything able to get a message into the thread. */
  endpoint?: '/api/ask' | '/api/v2/ask'
  /** What this console's assistant reads, named on screen so the answer's source is not a guess. */
  reads?: string
}

/** Natural-language fallback for questions with no fixed query to hardcode. Calls the real
 *  LibreChat agent (LLM + clickhouse MCP tool) through the API rather than duplicating a chat
 *  UI here: every other mode answers a known question fast and without an LLM, and this is the
 *  one place that trades that speed for an open-ended question. */
export default function AskAI({endpoint = '/api/ask', reads = 'phoenix'}: Props = {}) {
  const [thread, setThread] = useState<AskMessage[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  // BRING YOUR OWN MODEL. This is the user's own LLM provider key, not a credential on our
  // deployment. Held in component state only: never written to localStorage, never put in a URL,
  // never sent anywhere but the Authorization header this app builds server-side. It is gone the
  // moment the tab closes, which is exactly what the disclaimer below promises.
  const [apiKey, setApiKey] = useState('')
  const [provider, setProvider] = useState<LlmProvider>('google')
  const [keyOpen, setKeyOpen] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listRef.current?.scrollTo({top: listRef.current.scrollHeight})
  }, [thread, pending])

  async function send() {
    const text = input.trim()
    if (!text || pending) return
    const next: AskMessage[] = [...thread, {role: 'user', content: text}]
    setThread(next)
    setInput('')
    setError('')
    setPending(true)
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // A HEADER, not a query parameter and not the body. Query strings reach access logs and
          // Referer headers; this project also publishes system.query_log extracts as graded
          // evidence, so a key in a URL would be a key in the submission.
          ...(apiKey.trim() ? {'X-LLM-Key': apiKey.trim(), 'X-LLM-Provider': provider} : {}),
        },
        body: JSON.stringify({messages: next}),
      })
      const body = await safeJson(res)
      if (!res.ok) throw new Error(body.error || `${endpoint} failed`)
      setThread([...next, {role: 'assistant', content: body.content as string}])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.meta}>
        <p className={styles.hint}>
          Backed by the LibreChat agent with a live <code>clickhouse</code> MCP tool, not a canned
          query, and scoped to <code>{reads}</code>. Slower than the other tabs and it can be
          wrong: verify anything load-bearing against the curve.
        </p>
        {thread.length > 0 && (
          <button
            className={styles.clear}
            onClick={() => {
              setThread([])
              setError('')
            }}
          >
            Clear
          </button>
        )}
      </div>

      <div className={styles.keyBar}>
        <button
          type="button"
          className={styles.keyToggle}
          aria-expanded={keyOpen}
          onClick={() => setKeyOpen((v) => !v)}
        >
          {apiKey.trim() ? `Using your ${LLM_PRESETS[provider].label} key` : 'Use your own AI API key'}
        </button>
        {keyOpen && (
          <div className={styles.keyPanel}>
            <label className={styles.keyLabel} htmlFor="llm-provider">
              Model provider
            </label>
            <div className={styles.providerRow} role="group" aria-label="Model provider">
              {(Object.keys(LLM_PRESETS) as LlmProvider[]).map((id) => (
                <button
                  key={id}
                  type="button"
                  className={styles.providerButton}
                  aria-pressed={id === provider}
                  onClick={() => setProvider(id)}
                >
                  {LLM_PRESETS[id].label}
                </button>
              ))}
            </div>

            <label className={styles.keyLabel} htmlFor="llm-key">
              Your {LLM_PRESETS[provider].label} API key
            </label>
            <input
              id="llm-key"
              className={styles.keyInput}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder={`paste your ${LLM_PRESETS[provider].label} key`}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <p className={styles.keyNote}>
              <strong>Your key stays in this browser tab.</strong> We do not store it, log it,
              write it to any file, or share it with anyone. It is sent only as the authorization
              header on your own question and is discarded the moment you close the tab. Questions
              are billed to your provider account, not ours. Get a key from{' '}
              <a href={LLM_PRESETS[provider].keyUrl} target="_blank" rel="noreferrer">
                {LLM_PRESETS[provider].label}
              </a>
              . Leave this blank to use the demo host&apos;s key if one is configured.
            </p>
            {apiKey.trim() && (
              <button type="button" className={styles.keyClear} onClick={() => setApiKey('')}>
                Forget key
              </button>
            )}
          </div>
        )}
      </div>

      <div className={styles.listWrap} ref={listRef}>
        {thread.length === 0 && !pending && <p className={styles.empty}>Ask a question about the pipeline below.</p>}
        {thread.map((m, i) => (
          <div key={i} className={m.role === 'user' ? styles.rowUser : styles.rowAssistant}>
            <span className={styles.role}>{m.role === 'user' ? 'you' : 'agent'}</span>
            <div className={styles.bubble}>
              {m.role === 'assistant' ? <ReactMarkdown>{m.content}</ReactMarkdown> : m.content}
            </div>
          </div>
        ))}
        {pending && (
          <div className={styles.rowAssistant}>
            <span className={styles.role}>agent</span>
            <div className={styles.bubble}>
              <span className={styles.thinking}>thinking…</span>
            </div>
          </div>
        )}
      </div>

      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.inputRow}>
        <input
          className={styles.input}
          value={input}
          placeholder="e.g. what's driving the concurrency spike today?"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          disabled={pending}
        />
        <button className={styles.send} onClick={send} disabled={pending || !input.trim()}>
          {pending ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
