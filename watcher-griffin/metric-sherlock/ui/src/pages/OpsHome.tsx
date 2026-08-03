/* The operations home. NOTHING HAS TO BE ENTERED.
 *
 * No date picker, no dimension filter, no submit button. "Now" is the data's own clock,
 * which is what removes the date picker rather than hiding it.
 *
 * IT LEADS WITH WHAT MOVED, NOT WITH WHAT IT COST
 * This screen used to open on "$625.43 at risk per day". That is a real number and it is
 * still on the page, but it was answering a question the system does not detect: the
 * detector finds metrics leaving their seasonal band, and money is an estimate layered on
 * top of that afterwards. Leading with the estimate made the diagnosis read as a footnote to
 * a cost report. So the headline is now the movement itself -- how many segments are outside
 * their normal range, and the single furthest one, named.
 *
 * Dollars still gate (a large deviation on a commercially immaterial slice is not an
 * incident) and are still shown per row. They no longer order anything a reader sees.
 *
 * READING ORDER:
 *   1. where in the funnel did it move       -> the funnel chart
 *   2. what is outside its normal range      -> the headline
 *   3. what do I act on, and who owns it     -> the queue, newest first
 *   4. how was this computed                 -> the trace
 *
 * THE FUNNEL'S METRIC SELECTOR IS THE ONE INPUT, AND IT SELECTS A VIEW
 * The selector does not decide what gets measured; every stage is evaluated on every sweep
 * either way. It opens on the stage the engine itself marked as the driver, and every option
 * carries its own status colour, so the screen still answers "where did it move" before
 * anyone touches it. That is the condition under which a control is allowed on this page.
 */

import { getCalibration, getOpsSummary } from '../api/client'
import IncidentQueue from '../components/IncidentQueue'
import Reveal from '../components/Reveal'
import RevenueFunnel from '../components/RevenueFunnel'
import SqlTrace from '../components/SqlTrace'
import { usePolling } from '../hooks/usePolling'
import type { PeakMovement } from '../types'
import { bandWidths, count, dateTime, metricLabel, scopeValue } from '../lib/format'
import { formatMove } from '../lib/metricConfig'
import { useCountUp } from '../lib/motion'
import { ownerColor, statusStyle } from '../lib/status'

const POLL_MS = 30_000
/** Calibration only changes when a backtest is re-run, so it is not on the 30s loop. */
const CALIBRATION_POLL_MS = 300_000

/** The headline: how many segments are outside their normal range, and the furthest one.
 *
 *  Counts up once on load — the only animated number on the page, because it is the one
 *  thing the screen exists to say. Colour comes from the peak movement's own severity, not
 *  from the sign of a dollar figure: the previous version painted the hero green whenever
 *  exposure was <= 0, which called an above-band click-fraud spike "healthy" because it
 *  happened to earn money. */
function OutOfBand({ count: n, peak }: { count: number; peak: PeakMovement | null }) {
  const shown = useCountUp(n)
  const healthy = n <= 0
  const st = statusStyle(healthy ? 'good' : peak?.root_severity || 'red')
  const move = peak ? formatMove(peak.root_metric, peak.root_value, peak.root_center) : null

  return (
    <div className="hero-figure">
      <span className="hero-value tabular" style={{ color: st.color }}>
        {shown}
      </span>
      <span className="hero-unit">
        {n === 1 ? 'segment outside its normal range' : 'segments outside their normal range'}
      </span>
      {peak && move && (
        <p className="hero-peak">
          Furthest: <strong>{metricLabel(peak.root_metric)}</strong>{' '}
          {peak.direction === 'above' ? 'up' : 'down'} <strong>{move.replace(/^[+−]/, '')}</strong>{' '}
          for <strong>{scopeValue(peak.root_scope_value)}</strong>
          {peak.root_deviation_score != null && (
            <> · <span className="tabular">{bandWidths(peak.root_deviation_score)}</span></>
          )}
        </p>
      )}
    </div>
  )
}

/** One line saying how often this detector is wrong, on the screen that asks to be
 *  believed. Rendered only when a backtest exists — a calibration claim with no
 *  measurement behind it is worse than no claim, so an uncalibrated build says nothing
 *  here rather than something reassuring. */
function TrustLine() {
  const { data } = usePolling(getCalibration, CALIBRATION_POLL_MS)
  if (!data?.available || !data.settings?.length) return null

  const adopted = data.settings.find((s) => s.adopted) ?? data.settings[0]
  const labels = (data.ground_truth ?? []).map((g) => g.label)
  const found = labels.filter((l) => adopted.detections?.[l]).length

  return (
    <p className="trust-line">
      Calibrated on a {data.days_replayed}-day replay:{' '}
      <strong>
        {found} of {labels.length}
      </strong>{' '}
      planted incidents caught on the earliest sweep that could see them ·{' '}
      <strong>{adopted.fp_distinct}</strong> false alarms across {adopted.quiet_days} quiet
      days.
      {/* The scorecard is a file describing a replay of the PRIMARY dataset, and it does not
          change when the dataset switcher does -- the replay takes minutes, and the unseen
          dataset has 5 days of history to replay 35 of. So when another dataset is on
          screen, say whose measurement this is. Unlabelled, it would read as this dataset's
          false-alarm rate, which is a claim about data that was never tested. Captioned
          rather than hidden: dropping an unflattering number is its own dishonesty. */}
      {data.measured_on_active === false && (
        <span className="trust-line-caveat">
          {' '}
          Measured on the primary dataset ({data.measured_on}), not the one shown — this
          dataset has not been replayed.
        </span>
      )}
    </p>
  )
}

export default function OpsHome() {
  const { data, error, loading } = usePolling(getOpsSummary, POLL_MS)

  if (error) {
    return (
      <div className="panel">
        <h2>Something went wrong</h2>
        <p style={{ color: 'var(--status-critical)' }}>{error}</p>
        <p className="muted-note">
          The page failed rather than rendering an empty, all-green dashboard. A monitoring
          screen that looks healthy while it is broken is worse than one that says so.
        </p>
      </div>
    )
  }

  if (loading && !data) {
    return (
      <div className="skeleton-stack" aria-busy="true" aria-live="polite">
        <span className="sr-only">Loading the operations view…</span>
        <div className="skeleton skeleton-hero" />
        <div className="skeleton skeleton-row" />
        <div className="skeleton skeleton-row" />
      </div>
    )
  }
  if (!data) return null

  const { clock, tree, last_sweep: sweep } = data
  // {} when nothing is breaching — narrow it to null so the headline can branch once.
  const peak = (data.peak_movement && 'root_metric' in data.peak_movement
    ? (data.peak_movement as PeakMovement)
    : null)
  const owners = Object.entries(data.incidents_by_owner).sort((a, b) => b[1] - a[1])
  const healthy = data.incidents_open === 0

  return (
    <div className="ops">
      {/* ---- 1. Where in the funnel did it move? ---- */}
      <Reveal as="section">
        <div className="sec-head">
          <h2>The metric funnel</h2>
          <p className="sec-sub">
            Every stage against its own normal range for this time of day and day of week ·{' '}
            {dateTime(tree.window_start)} to {dateTime(tree.window_end)}
          </p>
        </div>
        <p className="sec-note">
          Revenue is requests × fill rate × show rate × eCPM. That holds exactly, so the stage
          marked <em>main driver</em> is the one that moved — and it is the one already
          selected below. Every stage is measured on every sweep; choosing one only changes
          which is drawn.
        </p>

        <RevenueFunnel tree={tree} />
      </Reveal>

      {/* ---- 2. Is money leaking, and how much? ---- */}
      <Reveal className="hero" as="section" delay={60}>
        <div className="hero-main">
          <p className="eyebrow">Right now</p>
          <OutOfBand count={data.incidents_open} peak={peak} />
          <p className="hero-sub">
            {healthy ? (
              <>Everything is inside its normal range.</>
            ) : (
              <>
                Across <strong>{data.incidents_open}</strong>{' '}
                {data.incidents_open === 1 ? 'issue' : 'issues'} worth acting on
                {data.incidents_gated > 0 && `, plus ${data.incidents_gated} smaller ones`}.
              </>
            )}
          </p>

          {owners.length > 0 && (
            <ul className="hero-owners">
              {owners.map(([owner, n]) => (
                <li key={owner} style={{ ['--owner' as string]: ownerColor(owner) }}>
                  <strong className="tabular">{n}</strong> for {owner}
                </li>
              ))}
            </ul>
          )}
        </div>

        <dl className="hero-meta">
          <div>
            <dt>Data through</dt>
            <dd className="tabular" title={clock.explanation}>
              {dateTime(clock.as_of)}
            </dd>
            <dd className="hero-meta-sub tabular">{count(clock.total_rows)} events</dd>
          </div>
          {sweep && (
            <div>
              <dt>Last check</dt>
              <dd className="tabular">{count(sweep.evaluations)} measurements</dd>
              <dd className="hero-meta-sub tabular">
                {sweep.queries_issued} queries · {(sweep.duration_ms / 1000).toFixed(1)}s
              </dd>
            </div>
          )}
        </dl>
      </Reveal>

      <TrustLine />

      {data.staleness?.stale && (
        <p className="notice notice-warn">{data.staleness.reason}</p>
      )}

      {/* ---- 3. What do I act on? ---- */}
      <Reveal as="section" delay={90}>
        <div className="sec-head">
          <h2>What needs action</h2>
          <p className="sec-sub">
            Newest first
            {/* Say when the list is truncated. A queue that shows 25 of 33 without saying so
                reads as "these are all of them", which is the same class of quiet
                overstatement as reporting 0 suppressed incidents when 791 were. */}
            {data.incidents_open > data.incidents_returned &&
              ` · showing the top ${data.incidents_returned} of ${data.incidents_open}`}
          </p>
        </div>
        <IncidentQueue incidents={data.incidents} />
      </Reveal>

      {/* ---- 4. How was this computed? ---- */}
      <Reveal as="section" delay={120}>
        <SqlTrace queries={data.queries} title="How this page was computed" />
      </Reveal>
    </div>
  )
}
