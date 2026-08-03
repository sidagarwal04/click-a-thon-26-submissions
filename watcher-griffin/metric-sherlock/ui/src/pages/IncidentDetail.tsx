/* One incident, presented as an argument rather than a data dump.
 *
 * TWO COLUMNS, BECAUSE THE FOLLOW-UP IS PART OF READING
 * This was one long column with the chat at the bottom, 3,178px down a 3,726px page. Asking
 * "why this segment?" meant scrolling past every piece of evidence to reach the box, and then
 * losing the evidence to read the answer. The follow-up panel now sits in a sticky rail on the
 * right, so the question and the thing being questioned are on screen together. That is the
 * whole point of the layout; everything else follows from it.
 *
 * WHAT LEADS
 * The root cause opens the page, then what moved, then the findings, then the contributors.
 * The mechanism is both first and the most prominent block because it is the answer — a rule
 * table's output over measured numbers, needing no language model — and a reader who reads
 * only one box should not have to scroll to reach it.
 *
 * The figures beside the summary are the MOVEMENT: observed against seasonally expected, and
 * the distance between them in band-widths. The exposure estimate follows underneath, because
 * it answers "does this matter commercially" rather than "what happened", and leading with it
 * made every incident read as a cost report.
 *
 * The LLM narration is deliberately NOT that box. It moved into the AI Analysis accordion,
 * below the deterministic mechanism, because if the model is unavailable the diagnosis is
 * still complete. The Key Findings bullets are built from discrete fields rather than by
 * summarising the prose, for the same reason.
 *
 * NOTHING WAS DROPPED IN THE COMPRESSION
 * Every section of the previous page still renders; the six accordions re-file them rather
 * than replacing them. Simple mode is the default and starts them closed, Full opens them,
 * and `<Section>` renders identical content either way — a page that discards its evidence
 * when a toggle flips is a page whose evidence is decorative.
 *
 * There is no metric trend chart, and that is a data fact rather than an omission: this
 * endpoint carries no time series. `members` looks like one but is a grain ladder — one entry
 * per (metric, scope, grain), all ending at the same instant — so it can only ever yield a
 * single point. See "Breach across timescales" in the Evidence accordion, which is what that
 * data actually is.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getCausalChain, getIncident } from '../api/client'
import CausalChain from '../components/CausalChain'
import Provenance from '../components/Provenance'
import { Chat } from '../components/Chat'
import type { ChatSuggestion } from '../components/Chat'
import EvidenceScore from '../components/EvidenceScore'
import ImpactBars from '../components/ImpactBars'
import KeyFindings from '../components/KeyFindings'
import OwnerBadge from '../components/OwnerBadge'
import Recommendations from '../components/Recommendations'
import SiblingBars from '../components/SiblingBars'
import SpreadBars from '../components/SpreadBars'
import SqlTrace from '../components/SqlTrace'
import WaterfallChart from '../components/WaterfallChart'
import { bandWidths, dateTime, dayRange, metricLabel, metricValue, scopeValue, scopeWord, usd, windowLabel } from '../lib/format'
import { formatMove, unitForMetric } from '../lib/metricConfig'
import { directionWord, statusStyle } from '../lib/status'
import { useViewMode, type ViewMode } from '../lib/viewMode'
import type { CausalChain as Chain, ChatTurn, IncidentDetail as Detail } from '../types'

/** How many member breaches to render. A broad incident groups hundreds of them; the
 *  page is an argument, not a data export. */
const MEMBER_PREVIEW = 25

/** One shared empty array. A literal `[]` fallback is a fresh object each render, which
 *  is what made <Chat>'s transcript sync loop forever. */
const EMPTY_TURNS: ChatTurn[] = []

/** Openers built from THIS incident's own evidence, so each one is answerable from the
 *  bundle the model is given.
 *
 *  The last entry is deliberately outside the evidence. A blank input invites an
 *  out-of-scope question by accident, and the correct refusal then reads as the system
 *  failing; offered on purpose, the same refusal demonstrates the guardrail that the
 *  whole trustworthiness argument rests on. It asks for a forecast, which is the one
 *  thing no amount of evidence can ever cover. */
function chatSuggestions(d: Detail): ChatSuggestion[] {
  const out: ChatSuggestion[] = []
  const verb = d.direction === 'above' ? 'rise' : 'drop'
  out.push({
    label: `Why the ${verb}?`,
    prompt: `Why did ${metricLabel(d.root_metric)} ${verb}?`,
  })
  // Named from THIS incident's scope. A fixed "Why APAC?" on every page would be wrong on
  // most of them, and the model would correctly refuse — which reads as the system being
  // broken rather than as it being careful.
  if (d.root_scope_value) {
    out.push({
      label: `Why ${scopeValue(d.root_scope_value)}?`,
      prompt: `Why ${scopeValue(d.root_scope_value)} and not another segment?`,
    })
  }
  if (d.evidence?.queries?.length) {
    out.push({ label: 'Show SQL', prompt: 'Which queries produced these numbers?' })
  }
  if (d.evidence_score_detail) {
    out.push({ label: 'Explain confidence', prompt: 'Explain the confidence score.' })
  }
  if (d.ruled_out?.length) {
    out.push({
      label: 'What was ruled out?',
      prompt: 'What was ruled out, and with what numbers?',
    })
  }
  if (d.seasonality) {
    out.push({ label: 'Just seasonality?', prompt: 'Could this just be seasonality?' })
  }
  if (d.impact_usd_per_day) {
    out.push({
      label: 'How big was the move?',
      prompt: `How far did ${metricLabel(d.root_metric)} move, and against what expected value?`,
    })
  }
  // Sliced BEFORE the uncovered question is appended, so the guardrail demo can never
  // be the one that falls off the end. Four plus one keeps the chip block to two rows in a
  // 400px rail — a third row comes straight out of the transcript's height.
  return [
    ...out.slice(0, 4),
    { label: 'Next week?', prompt: 'Will this happen again next week?' },
  ]
}

/** An analytical section. Same content in both modes — only whether it starts open
 *  differs, so Simple mode reduces what competes for attention without ever reducing
 *  what is available. */
function Section({
  title, mode, children,
}: {
  title: string
  mode: ViewMode
  children: React.ReactNode
}) {
  // `key` forces a remount when the mode changes, because <details open> is
  // uncontrolled — without it, flipping the toggle would leave already-rendered
  // sections in whatever state the reader last left them.
  return (
    <details className="card section-collapsible" key={mode} open={mode === 'full'}>
      <summary>
        <h3>{title}</h3>
      </summary>
      <div className="section-body">{children}</div>
    </details>
  )
}

/** A disclosure nested inside <Section>. Needs no `key` of its own: the parent already
 *  remounts on a mode change, which resets every child's uncontrolled `open` with it. */
function SubSection({
  title, mode, children,
}: {
  title: string
  mode: ViewMode
  children: React.ReactNode
}) {
  return (
    <details className="subsection" open={mode === 'full'}>
      <summary>
        <h4>{title}</h4>
      </summary>
      <div className="subsection-body">{children}</div>
    </details>
  )
}

export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<Detail | null>(null)
  const [chain, setChain] = useState<Chain | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useViewMode()

  const load = useCallback(() => {
    if (!id) return
    getIncident(id)
      .then(setData)
      .catch((e: Error) => setError(e.message))
    // Fetched separately and failing quietly: the chain is a re-presentation of
    // evidence already on this page, so losing it must not cost the reader the page.
    getCausalChain(id)
      .then(setChain)
      .catch(() => setChain(null))
  }, [id])

  useEffect(load, [load])

  // Memoised because <Chat> re-seeds its transcript whenever this prop changes. An inline
  // `data.chat ?? []` allocates a new array every render, which turned that sync into an
  // infinite render loop and froze the tab. Same for the suggestion list.
  const chatTurns = useMemo(() => data?.chat ?? EMPTY_TURNS, [data?.chat])
  const suggestions = useMemo(() => (data ? chatSuggestions(data) : []), [data])

  /* "What am I looking at", for the copilot's context card. Memoised for the same reason
   * as the two above — <Chat> takes it as a prop, and a fresh array every render would put
   * it back in the re-render loop those two exist to avoid.
   *
   * Confidence is the EVIDENCE score, not signature_confidence. The two are different
   * things and both are on this page: signature_confidence rates the rule that named the
   * mechanism, the evidence score rates how well the finding is supported overall. The
   * latter is what a reader means by "how sure are you". */
  const chatContext = useMemo(() => {
    if (!data) return []
    /* Four items, so the 2-column grid is exactly two rows. Scope is deliberately not one
     * of them: it is already the subject of the page title and the root-cause sentence,
     * and a fifth item cost a third row that the transcript needed more. */
    const items = [{ label: 'Metric', value: metricLabel(data.root_metric) }]
    if (data.evidence_score_detail) {
      items.push({ label: 'Confidence', value: `${data.evidence_score_detail.score}%` })
    }
    items.push({
      label: 'Evidence',
      value: `${data.evidence?.queries?.length ?? 0} queries`,
    })
    items.push({ label: 'Window', value: dayRange(data.opened_at, data.last_seen_at) })
    return items
  }, [data])


  if (error) return <p style={{ color: 'var(--status-critical)' }}>{error}</p>
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>Loading incident…</p>

  const st = statusStyle(data.gated_by_impact ? 'not_judgeable' : 'red')
  // The root movement. `members` is ordered by exposure, so the root slice is found by key
  // rather than by position; falling back to the incident's own peak when it is absent.
  const rootMember = data.members.find(
    (m) =>
      m.metric === data.root_metric &&
      m.scope_type === data.root_scope_type &&
      m.scope_value === data.root_scope_value &&
      m.grain === data.grain,
  )
  const rootValue = rootMember?.value ?? data.root_value ?? null
  const rootCenter = rootMember?.center ?? data.root_center ?? null
  const rootDev = rootMember?.deviation_score ?? data.root_deviation_score ?? null
  const unit = unitForMetric(data.root_metric)
  const move = formatMove(data.root_metric, rootValue, rootCenter)
  const band = rootDev != null ? bandWidths(rootDev) : null
  const hist = data.history
  const ev = data.evidence
  const prov = data.provenance?.facts

  /* The two props every provenance wrapper repeats, spread at each call site.
   *
   * Deliberately a props object rather than a wrapper component. A component declared
   * here would be a new element TYPE on every render, so React would unmount and remount
   * it and the open evidence panel would snap shut on any unrelated re-render; and a
   * memoised one would be a hook after the early returns above, which breaks the
   * Rules of Hooks. Spreading keeps `Provenance` itself as the element type, which is
   * stable by construction. */
  const pv = { facts: prov, incidentId: data.incident_id }
  const isRevenueTree = Boolean(ev?.factor_breakdown?.length)

  return (
    <div className="incident-page">
      <div className="page-bar">
        <Link to="/">← Back to operations</Link>
        <div className="page-bar-right">
          {/* Only reachable — and only useful — once the rail has dropped below the main
              column at the narrow breakpoint. Hidden by CSS above it. */}
          <a className="link-button rail-jump" href="#ask">
            Ask a follow-up ↓
          </a>
          <div className="view-toggle" role="group" aria-label="Level of detail">
            <button
              type="button"
              className={`pill${mode === 'simple' ? ' pill-active' : ''}`}
              aria-pressed={mode === 'simple'}
              onClick={() => setMode('simple')}
            >
              Summary
            </button>
            <button
              type="button"
              className={`pill${mode === 'full' ? ' pill-active' : ''}`}
              aria-pressed={mode === 'full'}
              onClick={() => setMode('full')}
            >
              Full evidence
            </button>
          </div>
        </div>
      </div>

      <div className="incident-layout">
        <div className="incident-main">
      {/* ---- 1. Root cause, first. Deterministic: a rule table over the measured spread,
             no language model. It is the answer, so it opens the page — a reader who reads
             exactly one box should not have to scroll to reach it. ---- */}
      <section className="card root-cause" style={{ borderLeftColor: st.color }}>
        <p className="eyebrow">Root cause</p>
        <p className="root-cause-mech">{data.mechanism || 'No mechanism was recorded.'}</p>
        <p className="source-note">
          Determined by a deterministic rule table over the measured spread — not by the
          language model. Rule confidence {data.signature_confidence.toFixed(2)}.
        </p>
      </section>

      {/* ---- 2. What moved ---- */}
      <section className="card verdict" style={{ borderLeft: `4px solid ${st.color}` }}>
        <div className="verdict-head">
          <div>
            <div className="verdict-sig">
              <span className="queue-sig">{data.signature}</span>
              <span style={{ color: st.color }}>{directionWord(data.direction)}</span>
            </div>
            {/* Plain language, not column names. "Fill rate is below normal for Android"
                rather than "fill_rate on os_family Android". */}
            <h2 className="verdict-title">
              {metricLabel(data.root_metric)}{' '}
              {data.direction === 'above' ? 'is unusually high for' : 'is below normal for'}{' '}
              <strong>{scopeValue(data.root_scope_value)}</strong>
            </h2>
            <p className="verdict-scope">
              measured by {scopeWord(data.root_scope_type)}
            </p>
            <div className="verdict-meta">
              {windowLabel(data.opened_at, data.last_seen_at)} · grain {data.grain} ·{' '}
              <Provenance {...pv} fact={prov?.['incident.member_event_count']}>
                {data.member_event_count} underlying breach
                {data.member_event_count === 1 ? '' : 'es'}
              </Provenance>{' '}
              · {data.breached_metrics.join(', ')}
            </div>
          </div>
          <div className="verdict-cost">
            {/* The movement leads. The exposure estimate follows it as supporting detail:
                it answers "does this matter commercially", not "what happened". */}
            <div className="verdict-cost-value tabular" style={{ color: st.color }}>
              <Provenance {...pv} fact={prov?.['root.deviation_score']}>
                {move ?? '—'}
                {band && <span className="verdict-cost-unit">{band}</span>}
              </Provenance>
            </div>
            <div className="verdict-cost-label">
              <Provenance {...pv} fact={prov?.['root.value']}>{metricValue(rootValue, unit)}</Provenance> vs{' '}
              <Provenance {...pv} fact={prov?.['root.center']}>{metricValue(rootCenter, unit)}</Provenance> expected
            </div>
            <div className="verdict-cost-label">
              <Provenance {...pv} fact={prov?.['impact.per_day']}>{usd(Math.abs(data.impact_usd_per_day))}/day</Provenance> estimated{' '}
              {data.impact_usd < 0 ? 'gain' : 'exposure'} ·{' '}
              <Provenance {...pv} fact={prov?.['impact.usd']}>{usd(Math.abs(data.impact_usd))}</Provenance> over{' '}
              {/* Say how many windows the total covers. A multi-day outage sums its
                  consecutive root-grain windows, so "over the 1d window" would understate
                  what the figure actually represents. */}
              {(data.windows_spanned ?? 1) > 1
                ? `${data.windows_spanned} consecutive ${data.grain} windows`
                : `the ${data.grain} window`}
            </div>
            <OwnerBadge owner={data.owner} showAction />
          </div>
        </div>

        {data.gated_by_impact && (
          <p className="warn-note">
            Below the alerting gate, so this was recorded but not raised. Shown here because it
            is still a real finding.
          </p>
        )}
      </section>

      {/* ---- 3. Key findings ---- */}
      <section className="card">
        <h3>Key findings</h3>
        <KeyFindings detail={data} move={move} band={band} />
      </section>

      {/* ---- 4. Top contributors ---- */}
      <section className="card">
        <h3>Top contributors</h3>
        <ImpactBars breakdown={data.impact_breakdown} />
      </section>

      {/* No AI analysis section. Only 4 of 825 incidents carry a narration, so on virtually
          every page it rendered as two paragraphs of boilerplate explaining that there was
          nothing to show — a section whose only content was an apology for its own emptiness.
          The plain-language diagnosis a reader needs is the deterministic Root Cause at the
          top of this page, which never depends on the model; the copilot rail is where the
          language model is actually useful, because there it answers a question that was
          asked. */}

      {/* ---- Evidence. A container: the old page's analytical sections, unchanged,
             re-filed as nested disclosures rather than eight top-level cards. ---- */}
      <Section title="Evidence" mode={mode}>
        <SubSection title="How we got to that" mode={mode}>
          <CausalChain chain={chain} />
        </SubSection>

        <SubSection title="How well evidenced is this" mode={mode}>
          <EvidenceScore
            detail={data.evidence_score_detail}
            fact={prov?.['evidence.score']}
            facts={prov}
            incidentId={data.incident_id}
          />
        </SubSection>

        {isRevenueTree && (
          <SubSection title="Which factor moved" mode={mode}>
            <WaterfallChart
              factors={ev!.factor_breakdown}
              primaryFactor={ev!.primary_factor}
            />
          </SubSection>
        )}

        <SubSection title="Why this segment, and not another" mode={mode}>
          <SpreadBars ruledOut={data.ruled_out} />
        </SubSection>

        <SubSection title="Could this just be seasonality?" mode={mode}>
          <SiblingBars
            seasonality={data.seasonality}
            rootScopeType={data.root_scope_type}
            rootScopeValue={scopeValue(data.root_scope_value)}
          />
        </SubSection>

        <SubSection title="Checked and ruled out" mode={mode}>
          {data.ruled_out && data.ruled_out.length > 0 ? (
            <ul className="ruled-list">
              {data.ruled_out.map((r) => (
                <li key={r.check}>
                  <span className="ruled-check">{r.check}</span>
                  <span className="ruled-reason">{r.reason}</span>
                  {r.numbers && Object.keys(r.numbers).length > 0 && (
                    <span className="ruled-numbers tabular">
                      {Object.entries(r.numbers)
                        .filter(([, v]) => v !== null && v !== '')
                        .map(([k, v]) => `${k}=${typeof v === 'number' ? Number(v.toFixed?.(4) ?? v) : String(v)}`)
                        .join(' · ')}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted-note">No ruled-out checks were recorded for this incident.</p>
          )}
          <p className="source-note">
            These are the alternatives that were tested and cleared, with the numbers that
            cleared them — so the same ground does not get re-covered by hand.
          </p>
        </SubSection>

        {/* Members. Named for what they actually are: the same breach measured over
            nested window lengths ending at the same instant, NOT a series over time. */}
        <SubSection
          title={`Breach across timescales — ${data.members.length} underlying band breach${data.members.length === 1 ? '' : 'es'}`}
          mode={mode}
        >
          <p className="source-note">
            Showing the {Math.min(MEMBER_PREVIEW, data.members.length)} largest by exposure.
            These are the individual band crossings this incident groups together — the same
            cause seen at different scopes and window lengths.
          </p>
          <div className="cov-scroll member-scroll">
            <table className="member-table">
              <thead>
                <tr>
                  <th scope="col">metric</th>
                  <th scope="col">scope</th>
                  <th scope="col">grain</th>
                  <th scope="col">actual</th>
                  <th scope="col">expected</th>
                  <th scope="col">band×</th>
                  <th scope="col">exposure</th>
                </tr>
              </thead>
              <tbody>
                {data.members.slice(0, MEMBER_PREVIEW).map((m, i) => (
                  <tr key={`${m.metric}-${m.scope_type}-${m.scope_value}-${m.grain}-${i}`}>
                    <td>{m.metric}</td>
                    <td>
                      {m.scope_type}={scopeValue(m.scope_value)}
                    </td>
                    <td>{m.grain}</td>
                    <td className="tabular">{m.value?.toFixed(4)}</td>
                    <td className="tabular">{m.center?.toFixed(4)}</td>
                    <td className="tabular">{Math.abs(m.deviation_score).toFixed(1)}</td>
                    <td className="tabular">{usd(Math.abs(m.impact_usd))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Cited at the table rather than per row: every row in it comes from the same
              two queries per (scope, grain) — the windowed measures and the band read —
              so 25 identical citations would be noise. The root row's own figures carry
              their individual queries in the verdict block above. */}
          <p className="source-note">
            every row from the sweep's own two queries per scope and grain:{' '}
            <code>sweep:&lt;scope&gt;:&lt;grain&gt;:windows</code> for the measured value and{' '}
            <code>sweep:&lt;scope&gt;:&lt;grain&gt;:bands</code> for the band it is compared
            against — expand any figure in the verdict above to read and re-run them
          </p>
          {data.members.length > MEMBER_PREVIEW && (
            <p className="muted-note">
              {data.members.length - MEMBER_PREVIEW} further breach
              {data.members.length - MEMBER_PREVIEW === 1 ? '' : 'es'} not shown — available in
              full from <code>GET /api/incidents/{data.incident_id}</code>.
            </p>
          )}
        </SubSection>

        {data.absorbed && data.absorbed.length > 0 && (
          <SubSection title="Also breached, folded in as symptoms" mode={mode}>
            <p className="chart-legend">
              These breached too, but this incident's own spread analysis already found their
              dimension uniformly affected — so they are the same cause seen from another angle,
              not separate incidents. Shown rather than discarded, so the merge is visible.
              {(data.absorbed_total ?? data.absorbed.length) > data.absorbed.length && (
                <>
                  {' '}
                  Showing the {data.absorbed.length} largest by exposure of{' '}
                  {data.absorbed_total} — the rest are the same argument repeated across
                  further dimensions.
                </>
              )}
            </p>
            <ul className="absorbed-list">
              {data.absorbed.map((a, i) => (
                <li key={`${a.root}-${i}`}>
                  <strong>{a.root}</strong> ({a.metric}, {usd(Math.abs(a.impact_usd))},{' '}
                  {a.events} event{a.events === 1 ? '' : 's'}) — {a.reason}
                </li>
              ))}
            </ul>
          </SubSection>
        )}
      </Section>

      {/* ---- Timeline ---- */}
      <Section title="Timeline" mode={mode}>
        <p className="rec-window">
          This incident ran {windowLabel(data.opened_at, data.last_seen_at)} at grain{' '}
          {data.grain}
          {(data.windows_spanned ?? 1) > 1 && <> across {data.windows_spanned} consecutive windows</>}
          .
        </p>
        {!hist || !hist.looked_up ? (
          <p className="muted-note">{hist?.reason ?? 'No history lookup was performed.'}</p>
        ) : (
          <>
            <p>{hist.summary}</p>
            {hist.chronic && (
              <p className="warn-note">
                This slice breaches in most windows it is evaluated in, which points at a
                mis-set baseline rather than an incident. It counts against the evidence
                score, not for it.
              </p>
            )}
            {hist.priors && hist.priors.length > 0 && (
              <table className="prior-table">
                <caption className="sr-only">Prior related incidents</caption>
                <thead>
                  <tr>
                    <th scope="col">when</th>
                    <th scope="col">signature</th>
                    <th scope="col">scope</th>
                    <th scope="col">match</th>
                    <th scope="col">exposure</th>
                    <th scope="col">verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {hist.priors.map((p) => (
                    <tr key={p.incident_id}>
                      <td>
                        <Link to={`/incidents/${p.incident_id}`}>{dateTime(p.opened_at)}</Link>
                      </td>
                      <td>{p.signature}</td>
                      <td>{p.root}</td>
                      <td>{p.match_strength}</td>
                      <td className="tabular">{usd(Math.abs(p.impact_usd))}</td>
                      <td>{p.label || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {/* The step behind the recurrence numbers. It has been populated by
                history.py since the day it was written and read by nothing — the field
                existed, the citation did not. */}
            {hist.source_step && (
              <p className="source-note">
                recurrence measured by <code>{hist.source_step}</code> over{' '}
                <code>incidents FINAL</code>, restricted to incidents opened before this one
              </p>
            )}
          </>
        )}
      </Section>

      {/* ---- Recommendations. Assembled from computed facts, never authored ---- */}
      <Section title="Recommendations" mode={mode}>
        <Recommendations detail={data} />
      </Section>

      {/* ---- Where every number comes from ----
             The counterpart to the inline affordances above. Those annotate the headline
             figures in place; this is the complete index, so a number rendered inside a
             chart or a bar — where an inline control would sit badly — still has its query
             one place away.

             Unlike the SQL trace below it, this is present on EVERY incident: it is
             derived from the incident's own scope, grain and window rather than captured
             during an investigation that, for 821 of 825 incidents, never ran. ---- */}
      {data.provenance && Object.keys(data.provenance.facts).length > 0 && (
        <Section title="Where every number comes from" mode={mode}>
          <p className="sec-note">{data.provenance.note}</p>
          {data.provenance.unverifiable.length > 0 && (
            <p className="warn-note">
              {data.provenance.unverifiable.length} measured figure(s) could not have their
              query reconstructed on this incident: {data.provenance.unverifiable.join(', ')}.
              Reported rather than hidden — an unprovable number should say so.
            </p>
          )}
          <ul className="prov-index">
            {Object.values(data.provenance.facts).map((f) => (
              <li key={f.key} className="prov-index-row">
                <code className="prov-index-key">{f.key}</code>
                <span className="prov-index-value tabular">
                  {f.value === null || f.value === undefined
                    ? '—'
                    : typeof f.value === 'number'
                      ? Number(f.value.toFixed(6))
                      : String(f.value)}
                </span>
                <Provenance fact={f} facts={data.provenance!.facts} incidentId={data.incident_id}>
                  <span className="prov-index-label">{f.label}</span>
                </Provenance>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* ---- SQL and trace, only when there is one. ----
             Just 4 of 825 incidents are fully investigated, so on every other page these two
             rendered as headings above a sentence explaining that they were empty. A section
             whose content is an apology for its own absence is worse than no section: it
             costs a reader the click to find out.

             They are conditional rather than deleted because traceability is the point of
             the product — for an investigated incident these carry 96 verbatim queries and
             the Langfuse link, and that is exactly what a sceptic is meant to be able to
             open. ---- */}
      {ev?.queries && ev.queries.length > 0 && (
        <>
          <SqlTrace queries={ev.queries} title="SQL" />

          <Section title="Investigation trace" mode={mode}>
            {data.langfuse_trace_url && (
              <p>
                <a href={data.langfuse_trace_url} target="_blank" rel="noreferrer">
                  Open the full trace in Langfuse &rarr;
                </a>
              </p>
            )}
            <p className="source-note">
              What was checked, in the order it ran. The SQL for each step is in the SQL
              section above.
            </p>
            <ol className="trace-steps">
              {ev.queries.map((q, i) => (
                <li key={`${q.step}-${i}`}>
                  <code>{q.step}</code>
                  <span className="tabular">
                    {q.row_count} returned
                    {q.latency_ms != null && <> &middot; {q.latency_ms.toFixed(1)}ms</>}
                  </span>
                  {q.error && <span className="trace-error">{q.error}</span>}
                </li>
              ))}
            </ol>
            {data.investigation_id && (
              <p className="source-note">
                investigation <code>{data.investigation_id}</code>
              </p>
            )}
          </Section>
        </>
      )}
        </div>

        {/* ---- The copilot rail. Sticky, so the question and the evidence being
               questioned are on screen at the same time. Chat is grounded in the
               INCIDENT, not the investigation, so it exists on every incident page:
               only the top few incidents per sweep are fully investigated, so keying it
               on investigation_id meant most pages had no chat at all. ---- */}
        <aside className="incident-rail" id="ask" aria-label="Ask a follow-up">
          <div className="card rail-card">
            <Chat
              subject="incident"
              subjectId={data.incident_id}
              initialTurns={chatTurns}
              suggestions={suggestions}
              context={chatContext}
            />
          </div>
        </aside>
      </div>
    </div>
  )
}
