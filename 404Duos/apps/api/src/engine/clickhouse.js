import { createClient } from '@clickhouse/client'

function envOr(key, fallback) {
  const v = process.env[key]
  return v != null && v !== '' ? v : fallback
}

function truncate(s, n) {
  if (s.length <= n) return s
  return s.slice(0, n)
}

/**
 * Create a ClickHouse client from env (CLICKHOUSE_*).
 * Pings with SELECT 1.
 */
export async function createClickHouse() {
  const host = envOr('CLICKHOUSE_HOST', 'localhost')
  const port = envOr('CLICKHOUSE_PORT', '8443')
  const username = envOr('CLICKHOUSE_USER', 'default')
  const password = process.env.CLICKHOUSE_PASSWORD || ''
  const database = envOr('CLICKHOUSE_DATABASE', 'insightiq')
  const secure = envOr('CLICKHOUSE_SECURE', 'true') === 'true'
  const logQueries = envOr('CLICKHOUSE_LOG_QUERIES', 'true') !== 'false'

  const scheme = secure ? 'https' : 'http'
  const client = createClient({
    url: `${scheme}://${host}:${port}`,
    username,
    password,
    database,
    request_timeout: 90_000,
    clickhouse_settings: {
      send_progress_in_http_headers: 1,
      http_headers_progress_interval_ms: '15000',
    },
  })

  client._insightiq = { database, logQueries }

  try {
    await queryMaps(client, 'SELECT 1')
  } catch (err) {
    await client.close().catch(() => {})
    throw new Error(`clickhouse ping: ${err.message || err}`)
  }

  if (logQueries) {
    console.log('clickhouse query logging enabled (set CLICKHOUSE_LOG_QUERIES=false to disable)')
  }

  return client
}

/**
 * Run a SQL query and return rows as an array of plain objects
 * (ClickHouse JSON format `data` array — same shape as Go QueryMaps).
 */
export async function queryMaps(client, sql) {
  const logQueries = client._insightiq?.logQueries ?? envOr('CLICKHOUSE_LOG_QUERIES', 'true') !== 'false'
  const start = Date.now()
  const trimmed = String(sql).trim()

  try {
    const result = await client.query({
      query: trimmed,
      format: 'JSON',
    })
    const parsed = await result.json()
    const data = Array.isArray(parsed?.data) ? parsed.data : []
    const elapsed = Date.now() - start

    if (logQueries && trimmed !== 'SELECT 1') {
      console.log(
        `clickhouse ok rows≈${data.length} ${elapsed}ms\n--- SQL ---\n${trimmed}\n--- END ---`,
      )
    }
    return data
  } catch (err) {
    const elapsed = Date.now() - start
    if (logQueries) {
      console.log(
        `clickhouse ERROR after ${elapsed}ms\n--- SQL ---\n${trimmed}\n--- END ---\nerr=${err.message || err}`,
      )
    }
    throw err
  }
}

export function asFloat(v) {
  if (v == null) return 0
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0
  if (typeof v === 'bigint') return Number(v)
  if (typeof v === 'boolean') return v ? 1 : 0
  if (typeof v === 'string') {
    const f = parseFloat(v)
    return Number.isFinite(f) ? f : 0
  }
  return 0
}

export function asString(v) {
  if (v == null) return ''
  return String(v)
}

/** Quote a Date/string for ClickHouse DateTime literals (UTC). */
export function quoteTime(t) {
  const d = t instanceof Date ? t : new Date(t)
  const iso = d.toISOString() // YYYY-MM-DDTHH:mm:ss.sssZ
  const s = iso.slice(0, 19).replace('T', ' ')
  return `'${s}'`
}

export function quoteString(s) {
  return `'${String(s).replace(/'/g, "\\'")}'`
}

export { truncate, envOr }
