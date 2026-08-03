// Talks to the ClickHouse HTTP interface directly, the same contract the retired demo server uses:
// POST the fixed SQL text, pass all user-controlled values as `param_*` query-string
// parameters (never string-built into the SQL), read back JSONCompact. SQL text lives inline
// in each route handler (see src/app/api/*/route.ts), self-contained, no read from ../sql.
import {CH_HOST, CH_PORT, CH_USER, CH_PASSWORD, CH_DATABASE} from './env'

interface JSONCompactResult {
  meta: { name: string; type: string }[]
  data: unknown[][]
  // bytes_read is what makes "rows read" mean something: 26,904 rows off a 61 KiB table and the
  // same count off raw_events are the same number and a very different read.
  statistics?: { rows_read?: number; bytes_read?: number; elapsed?: number }
}

/**
 * The database is a per-CALL choice, not a per-process one, because the two consoles read
 * different generations: v1 serves the validated concurrency engine out of `phoenix`, and the v2
 * insight console reads `phoenix_next`, which is where the insight layer lives and the only place
 * it exists. Making it a parameter rather than an environment switch means both can be open in
 * two browser tabs at once and neither can silently move the other.
 */
export async function chQuery<P extends object>(
  sql: string,
  params: P = {} as P,
  database: string = CH_DATABASE,
): Promise<JSONCompactResult> {
  if (!CH_HOST) {
    throw new Error('CH_HOST is not set, copy .env.example to ../.env and fill in ClickHouse Cloud credentials')
  }
  const qs = new URLSearchParams({
    database,
    session_timezone: 'UTC',
    default_format: 'JSONCompact',
    // SERVER-SIDE CEILING. Without it a slow query keeps running on the service after the client
    // has given up, and the consoles' 5-second tick stacks those queries on top of each other.
    // Set below the client abort so ClickHouse cancels itself first and returns a real error
    // rather than the client tearing down a socket mid-read.
    max_execution_time: '25',
  })
  for (const [k, v] of Object.entries(params)) qs.append(`param_${k}`, String(v as string | number))

  const res = await fetch(`https://${CH_HOST}:${CH_PORT}/?${qs}`, {
    method: 'POST',
    headers: {
      'X-ClickHouse-User': CH_USER,
      'X-ClickHouse-Key': CH_PASSWORD,
    },
    body: sql,
    cache: 'no-store',
    // CLIENT-SIDE CEILING. askAgent has had one since it was written; this path did not, so a
    // hung ClickHouse request held a Node handle indefinitely while nginx cut the browser off at
    // 90s. The two consoles poll every 5 seconds, so "indefinitely" compounds.
    signal: AbortSignal.timeout(30_000),
  })

  const body = await res.text()
  if (!res.ok) throw new Error(body.slice(0, 500))
  try {
    return JSON.parse(body) as JSONCompactResult
  } catch {
    throw new Error(`ClickHouse returned non-JSON: ${body.slice(0, 200)}`)
  }
}
