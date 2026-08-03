// Loads shipped query text from sql/queries/serving/, which is the ONE place it lives.
//
// WHY THIS REPLACED INLINE SQL. The route handlers used to carry their own copy of the query,
// justified as "self-contained, deployable without the rest of the repo". The cost of that
// choice, measured: the copies were forked from the retired benchmark copies, which the repo had
// already measured at 185.95 against a true 88.20 over the same day, and the fix committed to
// sql/queries/serving/ never got ported across. The dashboard shipped a number 2.1x too high
// while a correct query sat in the repo unused. A second copy of a query is not a deployment
// convenience, it is a number waiting to go stale.
//
// The trade is explicit: this app now requires the repo checkout at runtime, exactly as
// src/lib/env.ts already required ../.env. scripts/check_query_sources.sh enforces that no
// route reinstates an inline copy.
import fs from 'node:fs'
import path from 'node:path'

const SERVING_DIR = path.join(process.cwd(), '..', 'sql', 'queries', 'serving')

// Read once per file per process. Route handlers are hot paths on a 5-second refresh; re-reading
// from disk on every request buys nothing, and a changed .sql file should be picked up by a
// restart rather than mid-session, so the numbers on screen cannot change without the process
// that reported them changing too.
const cache = new Map<string, string>()

/** Reads a query from sql/queries/serving/ by filename, e.g. servingSql('concurrency_curve.sql'). */
export function servingSql(name: string): string {
  const cached = cache.get(name)
  if (cached !== undefined) return cached
  let text: string
  try {
    text = fs.readFileSync(path.join(SERVING_DIR, name), 'utf8')
  } catch (cause) {
    throw new Error(
      `cannot read sql/queries/serving/${name}. This app reads shipped query text from the ` +
        `repo checkout; run it from the frontend/ directory inside the repo. (${(cause as Error).message})`,
    )
  }
  cache.set(name, text)
  return text
}

/**
 * Reads named columns out of a JSONCompact result row.
 *
 * By name and not by index on purpose: the serving queries are shared with the benchmark and
 * validation harnesses, so a column added there would silently shift every positional read in
 * this app and put the wrong number under the right label. Missing names throw instead.
 */
export function columnReader(meta: { name: string }[]): (row: unknown[], name: string) => unknown {
  const index = new Map(meta.map((c, i) => [c.name, i]))
  return (row, name) => {
    const i = index.get(name)
    if (i === undefined) {
      throw new Error(`serving query did not return a column named "${name}" (got: ${[...index.keys()].join(', ')})`)
    }
    return row[i]
  }
}
