// One handler for every insight view, because they share one contract: the same seven filters in,
// a named-column table out, and the read cost reported alongside the answer.
//
// A REGISTRY, NOT A PATH. `view` comes from the URL, so it is untrusted, and it is never used to
// build a filename. It is looked up in the closed map below and a miss is a 404, which is what
// keeps a request for `../../../etc/passwd` a typo rather than a file read.
//
// COLUMNS PASS THROUGH BY NAME rather than being restated per view. Each .sql file already names
// its output columns and each one is the single source of truth for its own shape; re-declaring
// them here would be a second copy to drift, which is the exact failure lib/sql.ts exists to
// prevent. The client reads by name off `meta`, never by position, so a column added to a query
// for the benchmark harness cannot shift which number appears under which label.
import {NextRequest, NextResponse} from 'next/server'
import {resolveDataset} from '@/lib/datasets.server'
import {insightQuery, insightSql, parseInsightFilters} from '@/lib/insights'
import {errorResponse} from '@/lib/apiError'
import type {ApiError, InsightTableResponse} from '@/lib/types'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

/**
 * view name -> the shipped query that answers it, the question it answers, and which of the
 * standard filters that query can actually honour.
 *
 * `honours` is not decoration. A query that does not reference a parameter ignores it silently,
 * so a viewer who sets a platform filter on the spike view would get the same rows back and
 * reasonably conclude the platform made no difference. The console reads this list and says which
 * filters are inert for the current view, which is the difference between a limitation and a bug.
 */
const ALL_FILTERS = [
  'platform',
  'country',
  'video_type',
  'app_version',
  'content_id',
  'time',
] as const

// The four dimensions the unseen day added live on the CONCURRENCY delta tables, not on the
// insight tables, which were derived before those columns existed. Declaring them here as
// universally inert is the honest position: the v2 rail will show them disabled with the reason,
// which is a limitation the viewer can see, rather than a control that quietly does nothing.
// Denormalising them onto the ten insight tables is a re-derive, tracked as Phase 4 follow-up.
const INSIGHT_INERT_FILTERS = [
  'audio_language',
  'subtitle_language',
  'player_version',
  'video_resolution',
] as const

const VIEWS: Record<string, {file: string; question: string; reads: string; honours: readonly string[]}> = {
  flow: {
    file: 'audience_snapshot_minute_trend.sql',
    question: 'How did the audience arrive and leave, minute by minute?',
    reads: 'audience_minute_snapshot',
    honours: ALL_FILTERS,
  },
  states: {
    file: 'state_flow.sql',
    question: 'How many backgrounded, how many came back, how many went silent?',
    reads: 'session_state_transitions',
    honours: ALL_FILTERS,
  },
  retention: {
    file: 'cohorts_retention_curve.sql',
    question: 'Did the viewers it gained actually stay?',
    reads: 'content_entry_cohorts',
    honours: ALL_FILTERS,
  },
  health: {
    file: 'health_incident_window.sql',
    question: 'Did errors or heartbeat gaps cause the drop?',
    reads: 'playback_health_minute',
    honours: ALL_FILTERS,
  },
  versions: {
    file: 'session_facts_app_version_health.sql',
    question: 'Which app version loses viewers?',
    reads: 'session_insight_facts',
    honours: ALL_FILTERS,
  },
  spikes: {
    file: 'spike_explanation.sql',
    question: 'Why did concurrency spike, and was it healthy or short-lived?',
    // A spike is detected on the total curve for a piece of content, so it has no platform or
    // country of its own. What it has are the contribution columns, which are attributes of the
    // spike rather than filters on it.
    reads: 'concurrency_spike_events',
    honours: ['content_id', 'time'],
  },
  switching: {
    file: 'journey_content.sql',
    question: 'Which content takes its audience from which, and how much of that is real switching?',
    reads: 'user_content_transitions',
    honours: ['content_id', 'video_type', 'time'],
  },
  handoff: {
    file: 'journey_platform.sql',
    question: 'Which devices hand off to which, and how much is one person versus two screens?',
    reads: 'user_platform_transitions',
    honours: ['platform', 'content_id', 'time'],
  },
  forecast: {
    file: 'concurrency_forecast.sql',
    question: 'What is the next fifteen minutes likely to look like, and how sure is that?',
    reads: 'audience_minute_snapshot',
    honours: ALL_FILTERS,
  },
  lateness: {
    file: 'lateness_audit.sql',
    question: 'What arrived late, and did it change an answer we had already given?',
    // late_event_audit carries the event and its timing, not the session's dimensions. Joining
    // back to raw_events for them would put raw_events in this query's plan, which Gate B forbids.
    reads: 'late_event_audit',
    honours: ['time'],
  },
}

// A query that does not reference a parameter simply ignores it, so every view is called with the
// same filter set even though the spike and lateness tables carry fewer dimensions. Their headers
// say which filters they can honour; passing an unused one is inert rather than silently wrong.

export async function GET(
  req: NextRequest,
  {params}: {params: Promise<{view: string}>},
): Promise<NextResponse<InsightTableResponse | ApiError>> {
  const {view} = await params
  // Object.hasOwn, not a truthiness test. `VIEWS['constructor']` and `VIEWS['__proto__']` are
  // both truthy on a plain object literal, so they skipped this 404 and reached insightSql() with
  // an undefined filename. No attacker-controlled path was reachable, but the header above
  // presents this registry as the traversal defence and it has to hold for every input, not most.
  const spec = Object.hasOwn(VIEWS, view) ? VIEWS[view] : undefined
  if (!spec) {
    return NextResponse.json(
      {error: `unknown insight view "${view}". Known views: ${Object.keys(VIEWS).join(', ')}`},
      {status: 404},
    )
  }

  const filters = parseInsightFilters(req.nextUrl.searchParams)
  const dataset = resolveDataset(req.nextUrl.searchParams)
  const t0 = Date.now()
  try {
    const sql = insightSql(spec.file)
    const result = await insightQuery(sql, filters, dataset.insights)
    return NextResponse.json({
      view,
      question: spec.question,
      // Named so a reader can go from a number on screen to the table it came from without
      // reading the SQL. This is the plan's Gate B evidence, made visible rather than filed.
      reads: spec.reads,
      honours: spec.honours,
      ignores: [
        ...ALL_FILTERS.filter((f) => !spec.honours.includes(f)),
        ...INSIGHT_INERT_FILTERS,
      ],
      database: dataset.insights,
      sqlFile: `sql/insights/benchmark/${spec.file}`,
      // The text that just ran, not a copy of it. Read from the file at request time, so what is
      // on screen is what executed.
      sql,
      columns: result.meta.map((c) => c.name),
      rows: result.data,
      ms: Date.now() - t0,
      rowsRead: result.statistics?.rows_read ?? 0,
      bytesRead: result.statistics?.bytes_read ?? 0,
      serverMs: Math.round((result.statistics?.elapsed ?? 0) * 1000),
    })
  } catch (e) {
    return errorResponse('app/api/v2/insight/[view]/route.ts', e)
  }
}
