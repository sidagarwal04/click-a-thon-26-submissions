'use client'

import {useCallback, useEffect, useState} from 'react'
import {DATASET_LIST, type DatasetId} from '@/lib/datasets'
import {DatasetSwitch} from '@/components/DatasetSwitch'
import type {ClientFilters, DimensionValue, InsightStatusResponse, InsightTableResponse} from '@/lib/types'
import {istDateTime} from '@/lib/time'
import AskAI from '@/components/AskAI'
import QueryPanel from '@/components/QueryPanel'
import styles from './console.module.css'

/** The nav. Each entry is a business question from the plan's section 21, not a table name:
 *  the table is shown underneath the answer, which is the right way round for a reader. */
const VIEWS = [
  {id: 'spikes', label: 'Spikes', blurb: 'why it moved, and did it hold'},
  {id: 'flow', label: 'Audience flow', blurb: 'arrivals, departures, and attention'},
  {id: 'states', label: 'State flow', blurb: 'backgrounded, returned, went silent'},
  {id: 'retention', label: 'Retention', blurb: 'did the audience it gained stay'},
  {id: 'health', label: 'Playback health', blurb: 'errors and heartbeat gaps'},
  {id: 'versions', label: 'App versions', blurb: 'which build loses viewers'},
  {id: 'switching', label: 'Content switching', blurb: 'who took whose audience'},
  {id: 'handoff', label: 'Device handoff', blurb: 'one person, or two screens'},
  {id: 'forecast', label: 'Forecast', blurb: 'next 15 min, with its error band'},
  {id: 'lateness', label: 'Data quality', blurb: 'what arrived after we answered'},
  // Not an insight table: the open-ended question the ten fixed views cannot answer. Last in the
  // list because it is the fallback, and it is the one tab that costs an LLM round trip.
  {id: 'ask', label: 'Ask AI', blurb: 'anything the ten views do not cover'},
] as const

type ViewId = (typeof VIEWS)[number]['id']

/** Hours back from the insight watermark. 'all' is kept because several of these tables are small
 *  enough to read whole and a cohort curve over the full corpus is a legitimate question. */
const RANGES = [
  {id: '1', label: 'last 1h of data'},
  {id: '3', label: 'last 3h of data'},
  {id: '24', label: 'last 24h of data'},
  {id: 'all', label: 'everything derived'},
] as const

type RangeId = (typeof RANGES)[number]['id']

function toCh(d: Date): string {
  return d.toISOString().slice(0, 19).replace('T', ' ')
}

/**
 * The window, anchored on the RAW watermark rather than the wall clock.
 *
 * Anchoring on `now` would be wrong in a way that looks right: the pipeline lags ingest, so "the
 * last hour" measured against a real clock can land entirely inside the gap and return nothing at
 * all, which reads as "no audience" rather than "not derived yet". Anchoring on the stream's own
 * latest event means the window always lands on data that exists.
 */
function windowFor(range: RangeId, rawLatest: string | null): {from: string; to: string} {
  if (range === 'all' || !rawLatest) return {from: '2000-01-01 00:00:00', to: '2100-01-01 00:00:00'}
  const end = new Date(`${rawLatest.replace(' ', 'T')}Z`)
  const to = toCh(new Date(end.getTime() + 60_000))
  const from = toCh(new Date(end.getTime() - Number(range) * 3_600_000))
  return {from, to}
}

const EMPTY_FILTERS: ClientFilters = {
  platform: '',
  country: '',
  video_type: '',
  app_version: '',
  audio_language: '',
  subtitle_language: '',
  player_version: '',
  video_resolution: '',
  content_id: 0,
  from_ts: '',
  to_ts: '',
}

const DIMS: {key: 'platform' | 'country' | 'video_type' | 'app_version'; label: string}[] = [
  {key: 'platform', label: 'Platform'},
  {key: 'country', label: 'Country'},
  {key: 'video_type', label: 'Video type'},
  {key: 'app_version', label: 'App version'},
]

const nf = new Intl.NumberFormat('en-IN')

/**
 * An identifier is a number that must never be read as a quantity. content_id 990001 formatted as
 * 9,90,001 invites a reader to compare it with a concurrency of 2,000, and it is not that kind of
 * number: it has no magnitude, no unit and no order. Detected by column NAME rather than by value,
 * because nothing about the digits themselves distinguishes the two.
 */
function isIdentifier(column: string): boolean {
  return column.endsWith('_id')
}

function fmt(value: unknown, column?: string): string {
  if (column && isIdentifier(column)) return value == null ? '-' : String(value)
  if (value == null) return '-'
  if (typeof value === 'number') return Number.isInteger(value) ? nf.format(value) : value.toFixed(2)
  const s = String(value)
  // ClickHouse hands back big integers as strings in JSONCompact. Format them as numbers so a
  // count and a rate do not sit in the same column looking like different kinds of thing.
  if (/^-?\d+$/.test(s)) return nf.format(Number(s))
  if (/^-?\d+\.\d+$/.test(s)) return Number(s).toFixed(2)
  // A bare timestamp is UTC off the wire and must not be printed as-is: every other time on this
  // page is IST, and one stray UTC value is worse than none.
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/.test(s)) return istDateTime(s)
  return s === '' ? '(none)' : s
}

/** Right-align anything numeric so columns compare down the page rather than across it. */
function isNumeric(value: unknown): boolean {
  return typeof value === 'number' || (typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value))
}

/**
 * A horizontal magnitude bar behind the leading measure of each row. Deliberately not a chart
 * library: the shape every one of these views needs is "rank these rows by one number", and a bar
 * width is the whole of that. It also degrades honestly, since a zero-width bar reads as zero.
 */
function Bar({value, max}: {value: number; max: number}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0
  return (
    <span className={styles.barTrack} aria-hidden="true">
      <span className={styles.barFill} style={{width: `${pct}%`}}/>
    </span>
  )
}

function DataTable({data}: {data: InsightTableResponse}) {
  if (data.rows.length === 0) {
    return (
      <p className={styles.empty}>
        No rows. The query ran and the table it reads is empty for this window, which is a pipeline
        state rather than an error: see the watermarks in the header.
      </p>
    )
  }
  // The bar tracks the first numeric column that is actually a MEASURE. Skipping identifiers
  // matters: on the spike view the first numeric column is content_id, and a bar drawn from it
  // would rank spikes by which piece of content they happened to be about.
  const first = data.rows[0] ?? []
  const barCol = data.columns.findIndex((c, i) => isNumeric(first[i]) && !isIdentifier(c))
  const max = barCol >= 0 ? Math.max(...data.rows.map((r) => Number(r[barCol]) || 0)) : 0

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
        <tr>
          {data.columns.map((c, i) => (
            <th key={c} className={isNumeric(first[i]) && !isIdentifier(c) ? styles.num : ''}>
              {c.replace(/_/g, ' ')}
            </th>
          ))}
        </tr>
        </thead>
        <tbody>
        {data.rows.slice(0, 200).map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => {
              const column = data.columns[j] ?? ''
              return (
                <td key={j} className={isNumeric(cell) && !isIdentifier(column) ? styles.num : ''}>
                  {j === barCol && <Bar value={Number(cell) || 0} max={max}/>}
                  <span className={styles.cellValue}>{fmt(cell, column)}</span>
                </td>
              )
            })}
          </tr>
        ))}
        </tbody>
      </table>
    </div>
  )
}

/** Watermark row. Its job is to make staleness impossible to miss, so the lag is computed and
 *  labelled rather than left for the reader to subtract two timestamps in their head. */
function Watermarks({status}: {status: InsightStatusResponse}) {
  const raw = status.rawLatest ? Date.parse(`${status.rawLatest.replace(' ', 'T')}Z`) : 0
  const rows: {label: string; at: string | null; extra: string}[] = [
    {label: 'session facts', at: status.factsLatest, extra: `${nf.format(status.factsSessions)} sessions`},
    {label: 'minute snapshot', at: status.snapshotLatest, extra: `${nf.format(status.snapshotMinutes)} minutes`},
    {label: 'state transitions', at: status.transitionsLatest, extra: `${nf.format(status.transitionsAsserted)} asserted`},
    {label: 'playback health', at: status.healthLatest, extra: ''},
    {label: 'entry cohorts', at: status.cohortsLatest, extra: ''},
  ]
  return (
    <div className={styles.watermarks}>
      {rows.map((r) => {
        const t = r.at ? Date.parse(`${r.at.replace(' ', 'T')}Z`) : 0
        const lagMin = raw && t ? Math.round((raw - t) / 60000) : null
        const stale = lagMin != null && lagMin > 15
        return (
          <div key={r.label} className={styles.watermark}>
            <span className={styles.wmLabel}>{r.label}</span>
            <span className={styles.wmValue}>{istDateTime(r.at)}</span>
            <span className={`${styles.wmLag} ${stale ? styles.wmLagStale : ''}`}>
              {lagMin == null ? 'no data' : lagMin <= 0 ? 'current' : `${nf.format(lagMin)} min behind`}
            </span>
            {r.extra && <span className={styles.wmExtra}>{r.extra}</span>}
          </div>
        )
      })}
    </div>
  )
}

export default function InsightConsole() {
  const [view, setView] = useState<ViewId>('spikes')
  const [range, setRange] = useState<RangeId>('3')
  const [filters, setFilters] = useState<ClientFilters>(EMPTY_FILTERS)
  const [dims, setDims] = useState<DimensionValue[]>([])
  const [contentText, setContentText] = useState('')
  const [status, setStatus] = useState<InsightStatusResponse | null>(null)
  const [data, setData] = useState<InsightTableResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // Which generation the insight layer answers from. phoenix_unseen carries the same ten
  // insight tables as phoenix_next, so every view works against either.
  const [dataset, setDataset] = useState<DatasetId>('original')

  // Refetched per dataset: the two generations carry different content ids, so a stale rail
  // would offer filters that return nothing.
  useEffect(() => {
    fetch(`/api/v2/dimensions?dataset=${dataset}`)
      .then((r) => r.json())
      .then((b) => setDims(b.values ?? []))
      .catch(() => setDims([]))
  }, [dataset])

  // The watermark is per-dataset too, and it anchors every view's window. Clearing status first
  // stops the new dataset's first read being anchored on the previous one's watermark.
  useEffect(() => {
    setStatus(null)
    fetch(`/api/v2/status?dataset=${dataset}`, {cache: 'no-store'})
      .then((r) => r.json())
      .then((b) => (b.error ? setError(b.error) : setStatus(b)))
      .catch((e) => setError((e as Error).message))
  }, [dataset])

  const load = useCallback(
    (id: ViewId, r: RangeId, rawLatest: string | null, f: ClientFilters, ds: DatasetId) => {
    // 'ask' has no serving query behind it. Fetching /api/v2/insight/ask would 404 against the
    // route's closed registry, which is the registry working, not a bug to route around.
    if (id === 'ask') { setData(null); setError(null); setLoading(false); return }
    setLoading(true)
    setData(null)
    const {from, to} = windowFor(r, rawLatest)
    const qs = new URLSearchParams({from, to})
    if (f.platform) qs.set('platform', f.platform)
    if (f.country) qs.set('country', f.country)
    if (f.video_type) qs.set('video_type', f.video_type)
    if (f.app_version) qs.set('app_version', f.app_version)
    if (f.audio_language) qs.set('audio_language', f.audio_language)
    if (f.subtitle_language) qs.set('subtitle_language', f.subtitle_language)
    if (f.player_version) qs.set('player_version', f.player_version)
    if (f.video_resolution) qs.set('video_resolution', f.video_resolution)
    if (f.content_id) qs.set('content_id', String(f.content_id))
    qs.set('dataset', ds)
    fetch(`/api/v2/insight/${id}?${qs}`, {cache: 'no-store'})
      .then(async (r) => {
        const b = await r.json()
        if (!r.ok) throw new Error(b.error || `/api/v2/insight/${id} failed`)
        setData(b as InsightTableResponse)
        setError(null)
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false))
    },
    [],
  )

  /**
   * Which filters this view throws away, straight from the response rather than from a second copy
   * of the honours map kept here. A query that does not reference a parameter ignores it silently,
   * so an active control over an inert filter tells the viewer the dimension made no difference
   * when the truth is that it was never asked. Disabled with the reason is a limitation; enabled
   * and ignored is a bug.
   *
   * Guarded on `data.view === view` because the response for the newly selected view has not
   * arrived yet during a switch. Everything stays enabled for that one tick rather than inheriting
   * the previous view's answer.
   */
  const inert = (f: string): boolean => data?.view === view && data.ignores.includes(f)

  // Waits for the watermark before the first read, so the window is anchored on real data rather
  // than on a default that would have to be corrected a moment later.
  useEffect(() => {
    if (range !== 'all' && !status) return
    load(view, range, status?.rawLatest ?? null, filters, dataset)
  }, [view, range, status, filters, dataset, load])

  const spike = status?.spikeEvents ?? 0
  const late = status?.lateEvents ?? 0

  return (
    <>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>PHOENIX</span>
          <span className={styles.brandSub}>Insights</span>
          <nav className={styles.brandLinks} aria-label="Related consoles">
            <a href="/">concurrency console</a>
          </nav>
        </div>
        <DatasetSwitch
          datasets={DATASET_LIST}
          active={dataset}
          busy={loading}
          onChange={(id) => {
            // Drop the previous generation's table before the new one lands: leaving it on screen
            // under the new label is the one failure mode this control must not have.
            setData(null)
            setDataset(id)
          }}
        />

        <nav className={styles.nav} aria-label="Insight views">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              className={`${styles.navItem} ${view === v.id ? styles.navItemActive : ''}`}
              aria-current={view === v.id ? 'page' : undefined}
              onClick={() => setView(v.id)}
            >
              <span className={styles.navLabel}>{v.label}</span>
              <span className={styles.navBlurb}>{v.blurb}</span>
            </button>
          ))}
        </nav>

        <div className={styles.rangeBlock}>
          <span className={styles.footLabel}>Dimensions</span>
          {DIMS.map(({key, label}) => (
            <div key={key} className={styles.field}>
              <label className={styles.fieldLabel} htmlFor={key}>
                {label}
                {inert(key) && <span className={styles.inertMark}> not in {data?.reads}</span>}
              </label>
              <select
                id={key}
                className={styles.select}
                disabled={inert(key)}
                title={inert(key) ? `${data?.reads} does not carry ${key}` : undefined}
                value={filters[key]}
                onChange={(e) => setFilters({...filters, [key]: e.target.value})}
              >
                <option value="">all</option>
                {dims.filter((d) => d.dim === key).map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </div>
          ))}

          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="content">
              Content
              {inert('content_id') && <span className={styles.inertMark}> not in {data?.reads}</span>}
            </label>
            {/* By TITLE, never by id, for the reason the v1 rail gives: thousands of content ids
                reach the serving layer and nobody filtering a dashboard knows which 8-digit number
                is which show. Local text state, because deriving the input value from content_id
                erases every keystroke that does not yet complete a real title. */}
            <input
              id="content"
              className={styles.select}
              list="v2-content-titles"
              disabled={inert('content_id')}
              title={inert('content_id') ? `${data?.reads} does not carry content_id` : undefined}
              placeholder={inert('content_id') ? 'not filterable here' : 'all titles'}
              value={contentText}
              onChange={(e) => {
                setContentText(e.target.value)
                const match = dims.find((d) => d.dim === 'content' && d.label === e.target.value)
                setFilters({...filters, content_id: Number(match?.value ?? 0)})
              }}
            />
            <datalist id="v2-content-titles">
              {dims.filter((d) => d.dim === 'content').map((d) => (
                <option key={d.value} value={d.label}/>
              ))}
            </datalist>
          </div>

          <hr className={styles.rule}/>

          <label className={styles.footLabel} htmlFor="range">Window</label>
          <select
            id="range"
            className={styles.select}
            value={range}
            onChange={(e) => setRange(e.target.value as RangeId)}
          >
            {RANGES.map((r) => (
              <option key={r.id} value={r.id}>{r.label}</option>
            ))}
          </select>
          <p className={styles.footNote}>
            Anchored on the latest ingested event, not on the wall clock: the insight layer lags
            ingest, so a window measured against a real clock can land inside the gap and return
            nothing.
          </p>
        </div>

        <div className={styles.sidebarFoot}>
          <span className={styles.footLabel}>reading</span>
          <code className={styles.footValue}>{status?.database ?? 'phoenix_next'}</code>
          {status && (
            <p className={styles.footNote}>
              {nf.format(status.rawEvents)} raw events, latest {istDateTime(status.rawLatest)} IST.
            </p>
          )}
        </div>
      </aside>

      <main className={styles.main}>
        <header className={styles.hero}>
          <h1 className={styles.heroTitle}>
            Concurrency tells you <mark className={styles.mark}>what</mark> changed. This tells
            you why.
          </h1>
          <p className={styles.heroLede}>
            The audience intelligence layer over the foreground-only concurrency engine. Every view
            below reads one purpose-built table and names it, along with what that read cost.
          </p>
        </header>

        {status && <Watermarks status={status}/>}

        {(spike === 0 || late === 0) && (
          <div className={styles.notice}>
            <strong>Two tables are still empty and their views are therefore not listed:</strong>{' '}
            {spike === 0 && <>spike detection has produced {spike} rows, </>}
            {late === 0 && <>the lateness audit has produced {late} rows. </>}
            They exist in the schema and their producers have not run. Reported here rather than
            shown as an empty chart, because an empty chart and a chart of zeroes look identical.
          </div>
        )}

        {view === 'ask' && <AskAI endpoint="/api/v2/ask" reads="phoenix_next"/>}

        {error && <p className={styles.error}>{error}</p>}

        {data && (
          <section className={styles.panel}>
            <div className={styles.panelHead}>
              <h2 className={styles.panelTitle}>{data.question}</h2>
              {/* Gate B evidence and the query itself, open by default: on this console the query
                  is the thing being examined, not a footnote to a chart. */}
              <QueryPanel
                sql={[data.sql]}
                files={[data.sqlFile]}
                reads={data.reads}
                rowsRead={data.rowsRead}
                bytesRead={data.bytesRead}
                serverMs={data.serverMs}
                wallMs={data.ms}
                defaultOpen
              />
              {data.ignores.length > 0 && (
                <p className={styles.ignores}>
                  This view cannot filter by {data.ignores.filter((f) => f !== 'time').join(', ')}.
                  The table it reads does not carry those columns, so those controls are inert here
                  rather than returning a filtered answer.
                </p>
              )}
            </div>
            <DataTable data={data}/>
          </section>
        )}

        {loading && view !== 'ask' && <p className={styles.loading}>reading {view}...</p>}
      </main>
    </>
  )
}
