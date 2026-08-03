'use client'

import type {Mode} from '@/lib/types'
import styles from './ModeSwitch.module.css'

interface Props {
  mode: Mode | 'compare' | 'open'
  onChange: (mode: Mode | 'compare' | 'open') => void
}

// Ask AI is deliberately absent. LibreChat is the v2 conversational layer only; v1 answers the
// concurrency question and shows the query that answered it, which is the graded deliverable.
const OPTIONS: { id: Mode | 'compare' | 'open'; label: string; hint: string }[] = [
  {id: 'sessions', label: 'Sessions', hint: 'session-aware'},
  {id: 'users', label: 'Users', hint: 'session-independent'},
  {id: 'compare', label: 'Compare', hint: 'both, overlaid'},
  // Deliberately last and deliberately not a curve: it reads raw_events, so it is a drill-down
  // the viewer asks for rather than something the refresh loop pays for.
  {id: 'open', label: 'Open', hint: 'still counting'},
  // Natural-language fallback for questions with no fixed query to hardcode. Embeds the LibreChat
  // agent (real LLM + clickhouse MCP tool) rather than duplicating a chat UI here.
]

/** Console-style toggle bank, not a soft tab strip, each option reads as a physically thrown switch. */
export default function ModeSwitch({mode, onChange}: Props) {
  return (
    <div className={styles.bank} role="tablist" aria-label="Concurrency mode">
      {OPTIONS.map((opt) => (
        <button
          key={opt.id}
          role="tab"
          aria-selected={mode === opt.id}
          className={`${styles.switch} ${mode === opt.id ? styles.active : ''}`}
          onClick={() => onChange(opt.id)}
        >
          <span className={styles.label}>{opt.label}</span>
          <span className={styles.hint}>{opt.hint}</span>
        </button>
      ))}
    </div>
  )
}
