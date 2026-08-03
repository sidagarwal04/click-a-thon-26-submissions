'use client'

import {useEffect, useState} from 'react'
import type {OpenSessionsResponse} from '@/lib/types'
import {istDateTime, istTime} from '@/lib/time'
import StatReadout from './StatReadout'
import styles from './OpenSessions.module.css'

interface Props {
  /** Watermark to evaluate against, ClickHouse "YYYY-MM-DD HH:mm:ss" UTC. Normally the latest
   *  ingested event, so "open" means open as of what the pipeline has actually seen. */
  asOf: string | null
}

const nf = new Intl.NumberFormat('en-IN')

/** Seconds as a human duration, with an hours term. A single session's provisional tail is at
 *  most the tolerance, so it is always seconds or minutes, but the TOTAL across thousands of open
 *  sessions runs to hundreds of hours and rendering that as "13253m" is a number nobody can read. */
function duration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m ${seconds % 60}s`
  return `${Math.floor(m / 60)}h ${m % 60}m`
}

/**
 * The answer to "how do you handle sessions that are still open, whose active ranges keep
 * growing as new heartbeats arrive", from the serving side.
 *
 * The number this panel exists for is PROVISIONAL SECONDS: the part of the concurrency figure
 * on the other tabs that a later heartbeat is still allowed to retract. Every open session is
 * counted through last_event + tolerance, and a session that turns out to have been paused or
 * backgrounded gives those seconds back. Showing the curve without showing this would present a
 * settled number where a moving one is the truth.
 *
 * FETCHED ON DEMAND, once per mount and on explicit refresh, never on the console's 5-second
 * tick: sql/queries/serving/open_sessions.sql reads raw_events rather than a delta table, and
 * that file is explicit that it is a drill-down rather than a refresh-path query.
 */
export default function OpenSessions({asOf}: Props) {
  const [data, setData] = useState<OpenSessionsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!asOf) return
    let cancelled = false
    setLoading(true)
    fetch(`/api/open-sessions?as_of=${encodeURIComponent(asOf)}`, {cache: 'no-store'})
      .then(async (res) => {
        const body = await res.json().catch(() => ({error: `${res.status} ${res.statusText}`}))
        if (cancelled) return
        if (!res.ok) throw new Error(body.error || '/api/open-sessions failed')
        setData(body as OpenSessionsResponse)
        setError(null)
      })
      .catch((e) => !cancelled && setError((e as Error).message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
    // asOf is captured at mount and only re-read on an explicit refresh: re-running whenever the
    // watermark moves would put this query back on the 5-second tick by the back door.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce])

  if (error) return <p className={styles.error}>{error}</p>
  if (!data) return <p className={styles.hint}>{loading ? 'reading raw_events...' : 'no watermark yet'}</p>

  return (
    <div className={styles.wrap}>
      <div className={styles.stats}>
        <StatReadout label="sessions still open" value={nf.format(data.openSessions)} accent="signal" size="lg"/>
        <StatReadout
          label="provisional time, still retractable"
          value={duration(data.provisionalSecondsTotal)}
          accent="cool"
          size="lg"
        />
      </div>
      <div className={styles.meta}>
        <StatReadout variant="inline" label="as of, IST" value={istDateTime(data.asOf)}/>
        <StatReadout variant="inline" label="gap tolerance" value={`${data.toleranceSeconds}s`}/>
        <StatReadout variant="inline" label="open after a background" value={nf.format(data.openWithBackground)}/>
        <StatReadout variant="inline" label="query latency" value={`${data.ms} ms`}/>
        <StatReadout
          variant="inline"
          label="rows read"
          value={data.rowsRead != null ? nf.format(data.rowsRead) : 'n/a'}
        />
        <button className={styles.refresh} onClick={() => setNonce((n) => n + 1)} disabled={loading}>
          {loading ? 'reading...' : 're-read'}
        </button>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
          <tr>
            <th>session</th>
            <th>platform</th>
            <th>country</th>
            <th>last event, IST</th>
            <th>counted until, IST</th>
            <th className={styles.num}>provisional</th>
            <th className={styles.num}>bg events</th>
          </tr>
          </thead>
          <tbody>
          {data.rows.map((r) => (
            <tr key={r.videoSessionId}>
              <td className={styles.id}>{r.videoSessionId}</td>
              <td>{r.platform}</td>
              <td>{r.country}</td>
              <td>{istTime(r.lastEvent)}</td>
              <td>{istTime(r.countedUntil)}</td>
              <td className={styles.num}>{duration(r.provisionalSeconds)}</td>
              <td className={styles.num}>{r.backgrounds}</td>
            </tr>
          ))}
          </tbody>
        </table>
      </div>

      <p className={styles.footnote}>
        Sorted by how much is still provisional, capped at 100 rows; the two figures above are over
        every open session, not this page. A session counts as open when it has no{' '}
        <code>VideoSessionEnd</code> and its last event is still within the {data.toleranceSeconds}s
        gap tolerance: an abandoned client that stopped emitting an hour ago is gone, not open, and
        the tolerance is the only thing that tells those apart.
      </p>
    </div>
  )
}
