'use client'

import styles from './QueryPanel.module.css'

/**
 * The query that was sent, with what it cost underneath.
 *
 * The submission guidelines ask for the ClickHouse query alongside the answer, because the
 * modelling is what is being judged rather than the chart. So this shows the TEXT, not a filename:
 * the server reads it from sql/queries/serving/ or sql/insights/benchmark/ at request time and
 * hands back exactly what it executed, which is the one version that cannot have drifted. The
 * file's explanatory comments are stripped for display only; see stripComments below.
 *
 * The cost line is read from ClickHouse's own `statistics`, not timed here. Rows read is the
 * number the read-budget gate is written against; bytes is what makes it mean something, since
 * 26,904 rows off a 61 KiB delta table and the same count off raw_events are a very different
 * read. Server ms and wall ms are separate because the difference between them is the network,
 * and conflating the two is how a fast query gets blamed for a slow link.
 *
 * Shared by both consoles. One component, one contract, one place to fix.
 */
interface Props {
  /** One entry per query executed for this answer. */
  sql: readonly string[]
  /** Repo-relative paths, in the same order. */
  files: readonly string[]
  /** The table these queries read. */
  reads?: string
  rowsRead?: number
  bytesRead?: number
  serverMs?: number
  /** Round trip measured in the route handler, network included. */
  wallMs?: number
  /** Open by default on the insight console, where the query IS the answer being examined. */
  defaultOpen?: boolean
}

const nf = new Intl.NumberFormat('en-IN')

/**
 * The query without its commentary.
 *
 * These files carry long headers explaining why each clause is shaped the way it is, which is the
 * right thing for the repo and the wrong thing on screen: forty lines of prose above eight lines
 * of SQL buries the query a reader came to see. The SERVER still sends and executes the whole
 * file, comments included, so nothing about what ran is changed by this; only the reading of it.
 *
 * Line-based, not a parser. A `--` inside a string literal would be stripped by a regex that
 * hunted mid-line, so only lines that are entirely a comment are dropped, and runs of blank lines
 * left behind are collapsed to one.
 */
function stripComments(sql: string): string {
  return sql
    .split('\n')
    .filter((line) => !line.trimStart().startsWith('--'))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function bytes(b: number): string {
  if (b >= 1e9) return `${(b / 1e9).toFixed(2)} GB`
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} MB`
  if (b >= 1e3) return `${(b / 1e3).toFixed(0)} KB`
  return `${b} B`
}

export default function QueryPanel({
  sql, files, reads, rowsRead, bytesRead, serverMs, wallMs, defaultOpen = false,
}: Props) {
  if (!sql.length) return null
  return (
    <details className={styles.panel} open={defaultOpen}>
      <summary className={styles.summary}>
        <span className={styles.summaryLabel}>Query sent</span>
        <span className={styles.cost}>
          {reads && <>reads <code>{reads}</code> &middot; </>}
          {rowsRead != null && <>{nf.format(rowsRead)} rows</>}
          {bytesRead != null && bytesRead > 0 && <> &middot; {bytes(bytesRead)}</>}
          {serverMs != null && <> &middot; {serverMs} ms server</>}
          {wallMs != null && <> &middot; {wallMs} ms wall</>}
        </span>
      </summary>
      {sql.map((text, i) => (
        <figure key={files[i] ?? i} className={styles.figure}>
          <figcaption className={styles.caption}>{files[i]}</figcaption>
          <pre className={styles.sql}>{stripComments(text)}</pre>
        </figure>
      ))}
    </details>
  )
}
