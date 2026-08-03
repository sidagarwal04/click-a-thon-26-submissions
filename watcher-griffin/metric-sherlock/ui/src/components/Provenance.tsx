/* The query behind a number, next to the number.
 *
 * WHY THIS IS PER-FIGURE AND NOT ONE PANEL AT THE BOTTOM
 * A trace at the foot of the page proves that queries ran. It does not tell a reader
 * which of 68 queries produced the $21.03 they are looking at, and correlating them by
 * hand is exactly the work the page exists to remove. And it was worse than that: the
 * trace only ever existed for the few incidents that got a full investigation, so on
 * almost every page there was nothing at all.
 *
 * THREE KINDS, THREE HONEST ANSWERS
 *   measured  one query returns the figure -> show it, and offer to re-run it
 *   derived   arithmetic over queried inputs -> show the formula and link each input,
 *             every one of which is itself verifiable
 *   config    a settings constant -> say so, with its path
 * The third case is the one most easily fudged. A threshold rendered like a measurement
 * borrows authority it has not earned, so `signature_confidence = 0.55` is labelled a
 * hand-set rule literal rather than given a query it does not have.
 *
 * VERIFY IS WHAT MAKES IT PROOF
 * Showing SQL asks the reader to take it on trust that the SQL corresponds to the
 * number. Running it removes the trust: the returned value appears beside the displayed
 * one with a match marker. A figure that has drifted fails in the open. This already
 * earned its keep during development -- it caught a Decimal64 truncation and an
 * arbitrary-seasonal-cell bug that both produced plausible, wrong "supporting" queries.
 *
 * Closed by default, on every number. Provenance has to be available everywhere and in
 * the way nowhere, which is the same contract the Summary/Full toggle keeps.
 */

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

import { verifyFact } from '../api/client'
import type { Fact, VerifyResponse } from '../types'

const KIND_LABEL: Record<string, string> = {
  measured: 'measured',
  derived: 'derived',
  config: 'setting',
}

interface Props {
  /** The rendered figure — already formatted by the caller, so this component never
   *  re-formats a number and cannot disagree with the page about how it reads. */
  children: React.ReactNode
  fact?: Fact | null
  incidentId: string
  /** Resolves an input key to its Fact, so a derived figure can show its inputs. */
  facts?: Record<string, Fact>
  className?: string
}

function InputRow({ fact, incidentId }: { fact: Fact; incidentId: string }) {
  return (
    <li className="prov-input">
      <span className="prov-input-label">{fact.label}</span>
      <span className="prov-input-value tabular">
        {fact.value === null || fact.value === undefined ? '—' : String(fact.value)}
      </span>
      <Provenance fact={fact} incidentId={incidentId} className="prov-nested">
        <span className="prov-input-kind">{KIND_LABEL[fact.kind] ?? fact.kind}</span>
      </Provenance>
    </li>
  )
}

export default function Provenance({ children, fact, incidentId, facts, className }: Props) {
  const [open, setOpen] = useState(false)
  const [result, setResult] = useState<VerifyResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /* Escape closes the overlay. A full-screen panel with no keyboard exit is a trap, and
   * the click-outside backdrop alone does not serve anyone on a keyboard.
   *
   * Declared ABOVE the early return below: a hook after a conditional return runs on some
   * renders and not others, which breaks hook ordering. Caught by the linter here, and it
   * is the second time this shape appeared in this component's neighbourhood. */
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  // No provenance for this figure: render it plainly rather than an affordance that
  // opens on nothing. An empty disclosure is worse than none — it implies the evidence
  // exists and is simply unhelpful.
  if (!fact) return <>{children}</>

  async function run() {
    setBusy(true)
    setError(null)
    try {
      setResult(await verifyFact(incidentId, fact!.key))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const inputs = (fact.inputs ?? [])
    .map((k) => facts?.[k])
    .filter((f): f is Fact => Boolean(f))

  /* A multi-CTE query is a different object from a one-line aggregate and cannot share its
   * container. The confidence score's SQL is ~45 lines with several long `multiIf` terms;
   * in a 420px popover with wrapped lines and a 240px cap it was technically present and
   * practically unreadable. Wide + uncapped for those, so "show me the SQL" means the
   * whole statement, formatted as written. */
  const sqlLines = fact.sql ? fact.sql.split('\n').length : 0
  const longSql = Boolean(fact.sql && (fact.sql.length > 400 || sqlLines > 6))

  async function copySql() {
    if (!fact!.sql) return
    try {
      await navigator.clipboard.writeText(fact!.sql)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      // Clipboard access can be refused (permissions, insecure origin). The SQL is
      // selectable on the page either way, so this is not worth an error state.
    }
  }

  const panel = (
        <span
          className={`prov-panel${longSql ? ' prov-panel-wide' : ''}`}
          role="region"
          aria-label={`Evidence for ${fact.label}`}
        >
          <span className="prov-head">
            <strong>{fact.label}</strong>
            <span className={`prov-kind prov-${fact.kind}`}>
              {KIND_LABEL[fact.kind] ?? fact.kind}
            </span>
          </span>

          {fact.formula && (
            <code className="prov-formula">{fact.formula}</code>
          )}

          {fact.config_path && (
            <span className="prov-meta">
              from <code>{fact.config_path}</code> — a configured constant, not a measurement
            </span>
          )}

          {fact.step && (
            <span className="prov-meta">
              step <code>{fact.step}</code>
              {fact.table && (
                <>
                  {' · '}reads <code>{fact.table}</code>
                </>
              )}
            </span>
          )}

          {fact.sql && (
            <>
              <span className="prov-sql-bar">
                <span className="prov-meta">
                  {sqlLines} line(s) · runs as written
                </span>
                <button type="button" className="prov-copy" onClick={copySql}>
                  {copied ? 'copied' : 'copy'}
                </button>
              </span>
              <pre className="prov-sql">
                <code>{fact.sql}</code>
              </pre>
            </>
          )}

          {inputs.length > 0 && (
            <>
              <span className="prov-meta">
                computed from {inputs.length} input{inputs.length === 1 ? '' : 's'}, each
                verifiable on its own:
              </span>
              <ul className="prov-inputs">
                {inputs.map((f) => (
                  <InputRow key={f.key} fact={f} incidentId={incidentId} />
                ))}
              </ul>
            </>
          )}

          {fact.note && <span className="prov-note">{fact.note}</span>}

          {fact.kind === 'measured' && fact.sql && (
            <span className="prov-actions">
              <button type="button" className="pill" onClick={run} disabled={busy}>
                {busy ? 'running…' : result ? 'run again' : 'run it and check'}
              </button>
              {result && result.matches === true && (
                <span className="prov-ok">
                  returned <span className="tabular">{String(result.returned)}</span> ✓ matches
                </span>
              )}
              {result && result.matches === false && (
                <span className="prov-bad">
                  returned <span className="tabular">{String(result.returned)}</span> ✗ does NOT
                  match the displayed {String(result.displayed)}
                </span>
              )}
              {result && result.matches === null && (
                <span className="prov-meta">
                  {result.row_count} row(s) returned — {result.note}
                </span>
              )}
              {result && (
                <span className="prov-meta">
                  scanned {result.read_rows?.toLocaleString()} rows · {result.latency_ms}ms
                </span>
              )}
              {error && <span className="prov-bad">{error}</span>}
            </span>
          )}
        </span>
  )

  return (
    <span className={`prov ${className ?? ''}`}>
      {children}
      <button
        type="button"
        className={`prov-toggle prov-${fact.kind}`}
        aria-expanded={open}
        title={`${KIND_LABEL[fact.kind] ?? fact.kind} — show the evidence for this number`}
        onClick={() => setOpen((v) => !v)}
      >
        {fact.kind === 'measured' ? 'SQL' : fact.kind === 'derived' ? 'ƒ' : 'set'}
      </button>

      {/* A LONG QUERY IS PORTALLED TO document.body, NOT LEFT IN PLACE.
       *
       * `position: fixed` is supposed to be enough for a centred overlay, and it was not:
       * measured in the running page, `left: 50%` resolved against a 650px box rather than
       * the viewport, putting the panel at y=930 in a 742px window — off screen, which for
       * "show me the SQL" is the same as not rendering it. A portal sidesteps the whole
       * class of problem (any ancestor that becomes a containing block for fixed
       * positioning, and any `overflow`/stacking context on the way up) instead of
       * chasing whichever property caused it in this particular subtree.
       *
       * Short panels stay inline, anchored to their figure, which is the right behaviour
       * for a one-line aggregate and keeps the reader's eye next to the number. */}
      {open && !longSql && panel}
      {open && longSql && createPortal(
        <>
          <span
            className="prov-backdrop"
            role="presentation"
            onClick={() => setOpen(false)}
          />
          {panel}
        </>,
        document.body,
      )}
    </span>
  )
}
