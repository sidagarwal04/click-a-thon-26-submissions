# Inspect Tab, Event Limits, Trace Completeness & Refresh UX — Engineering Plan

> **Status:** Proposed — not yet implemented.
> **Audience:** Implementers of `Atlys/service/**` (FastAPI, bus, tracing, MCP) and
> `Atlys/ui/**` (React dashboard + chat). Companion docs: `ENGINEERING.md`,
> `docs/resilience-plan.md`, `docs/agent-schema-inspect-plan.md`, `docs/chat-viz-plan.md`.
>
> **Scope (this plan):**
> 1. **Wave A — Inspect tab**: a judge/PM-facing view of the raw event log — payloads,
>    trace links, run grouping, pending-run states, tool-call history.
> 2. **Wave B — Event & storage limits**: retention/caps so a long demo or the unseen
>    spec cannot flood `atlys.event_log` or the in-memory bus mirror.
> 3. **Wave C — Trace completeness**: fix the `tool.called` trace_id gap, trace read-only
>    exploration, enrich playbook spans, add spans for journal/MV/seeding/REST.
> 4. **Wave D — Refresh & staleness UX**: per-tab "last refreshed" indicators, sane
>    auto-refresh policies, stale-while-revalidate, change detection, error states.
>
> **Explicitly out of scope:** auth, real-time push (WebSocket/SSE-to-browser is a stretch
> option only), ClickStack/OTLP, per-feature instrumentation of the app codebase.

---

## 0. Why this matters (judged criteria → requirement)

From `Atlys/PROBLEM_STATEMENT.md`, the traceability criterion reads: *"a judge should be
able to open your traces and follow the full reasoning chain: what each agent did, why,
and based on what context"* and the unseen spec is *"no trace, no credit"*.

| Judged criterion | How this plan serves it |
|---|---|
| Traceability | Inspect tab replays the event chain per run in-app; every row links to its Langfuse trace; tool.called events finally carry trace_id (Wave C). |
| Context freshness | Refresh UX makes it visible *which* context version is shown and when it was last fetched (Wave D). |
| Unseen spec robustness | Event-log TTL + per-run event caps prevent a pathological spec from flooding the store (Wave B). |
| PM insight quality | Read-only exploration gets traced as `explore:*` traces so the PM's ad-hoc questions are also replayable (Wave C). |

---

## 1. Current state (what exists today)

### 1.1 Data written by the pipeline (already durable)

- **`atlys.event_log`** — every event persisted via `EventBus._persist_event` (append-only,
  `ORDER BY (event_type, created_at)`). Fields: `event_id, event_type, aggregate_id, version,
  actor, payload (JSON string), trace_id, created_at`.
- **`meta.*`** — `schema_catalog`, `schema_changelog`, `context_snapshots`,
  `context_changelog`, `insights`, `known_issues`, `pending_runs`, `migration_journal`.
- **`generated/`** — `ddl.sql`, `schema_card.json`, `insight.md` per feature.

### 1.2 Current REST surface (dashboard read path, `service/api.py`)

| Endpoint | Returns | Notes |
|---|---|---|
| `GET /api/insights` | all insight cards | `evidence` parsed to array |
| `GET /api/insights/{feature}` | latest card | |
| `GET /api/changelog?scope=&limit=` | context/schema/event rows | default limit 50 |
| `GET /api/context?version=` / `/api/context-versions` | snapshot + diff | |
| `GET /api/event-log?limit=` | event rows w/ parsed payload | default limit 100, **no filters** |
| `GET /api/schema-catalog` | table cards | |
| `GET /api/migrations` | migration journal rows | exists, **no UI tab** |
| `GET /api/pending-runs` | run state machine rows | exists, **no UI tab** |
| `GET /api/specs` | spec inventory | |

### 1.3 Current dashboard tabs (`Dashboard.jsx`)

`Insights | Schema | Context | Events` — each fetches on tab switch; a global refresh
button refetches the active tab; the **Events tab polls every 5 s**; Context has a version
dropdown. There is **no "last refreshed" / staleness indicator**, no pagination, no
filters, and payloads are not shown in the Events table (only
`event_type / aggregate_id / actor / created_at`).

### 1.4 Current refresh wiring (`App.jsx` → `ChatPanel` → `Dashboard`)

- `ChatPanel` calls `onRefresh()` when a chat turn finishes → `App` bumps
  `refreshTrigger` → `Dashboard` refetches the active tab.
- Loading is all-or-nothing: the content area is replaced by a spinner while fetching
  (`{loading && <loading-dots/>}`); old data disappears on every refetch (no
  stale-while-revalidate), so a slow refresh causes visible flicker.
- Fetches are not cancelled on tab switch; a slow response for a previous tab can land
  after the new tab rendered (minor race, mostly benign today).

### 1.5 Current tracing (`service/tracing.py`, `mcp_server.py`, agents)

- One Langfuse trace per spec run (`tracer.start("spec:<dir>", session_id=run_id)`);
  trace_id flows to every `meta.*` row and event-log row.
- Spans: `instrumentation`, `load`, `context`, `analytics`, `playbook:<kind>` per query,
  `mcp_tool:<name>` on most MCP handlers. `NullTracer` when no keys (logs tree to stdout).
- **Known gaps (the point of Wave C):**
  1. `mcp_server._tool_called(name, arguments, trace_id="")` is invoked **without** a
     trace_id in `call_tool` → every `tool.called` event row has `trace_id=''`, so the
     audit log and Langfuse cannot be joined on tool events.
  2. Read-only tools (`db_schema`, `table_stats`, `aggregate`, `sample_rows`, `get_*`)
     run under the **stale** `tracer.trace_id` from the last spec run — PM exploration is
     effectively untraced.
  3. Playbook spans carry only `label`; no `row_count`, `elapsed_ms`, or SQL output.
  4. No spans for: context seeding, MV creation, migration-journal steps, event
     persistence, REST dashboard reads.
  5. `progress_hub` events (the chat tool chips) carry no `trace_id`, so a chip cannot be
     cross-linked to its span.

---

## 2. Wave A — Inspect tab

### 2.1 Goal

Give the PM and the judge one screen that answers: *what happened, in what order, with
what payloads, tied to which trace, and in what run state* — without opening Langfuse.

### 2.2 Backend changes (`service/api.py`)

**A1. `/api/event-log` — add filters + pagination (backwards compatible).**

```
GET /api/event-log
  ?limit=100            (default 100, clamp to 500)
  &run_id=<uuid>        (optional — filter by trace_id; a run's trace_id links its events)
  &event_type=<name>    (optional — e.g. schema.proposed)
  &actor=<name>         (optional — instrumentation|context|analytics|mcp|user)
  &before=<event_id or ISO ts>   (optional — keyset cursor for "older than X")
  &after=<...>          (optional — for live tailing)
```

- Response: `{ events: [...], next_cursor: <event_id|null>, total: <int|null> }`.
- `total` is a cheap `count()` only when requested (`&count=1`), not by default.
- Keep the current bare-array shape when no new params are passed (so the existing
  Events tab keeps working until it is migrated).

**A2. `GET /api/runs` — run registry (one row per spec run).**

Built from `meta.pending_runs` joined with `atlys.event_log` (grouped by `trace_id`):

```
GET /api/runs
  ?limit=50
  &state=proposed|running|approved|rejected|failed   (optional)
```

Response per run:
```json
{
  "run_id": "…uuid…",
  "trace_id": "…",
  "spec_dir": "01_express_checkout",
  "feature": "express_checkout",
  "state": "approved",                 // from meta.pending_runs
  "event_types": ["spec.run.requested", "spec.ingested", "…"],
  "event_count": 11,
  "first_event_at": "…", "last_event_at": "…",
  "duration_ms": 4321,
  "insight_title": "Express Checkout feature health"   // join on trace_id → meta.insights
}
```

**A3. `GET /api/runs/{run_id}` — full event chain for one run.**

- Resolve the run's `trace_id` (via `meta.pending_runs`), then return **every**
  `atlys.event_log` row with that trace_id in chronological order (the happy path already
  carries the same trace_id end-to-end; `schema.proposed`'s payload also embeds the
  `run_id` for extra robustness).
- **Dependency note:** until Wave C W0 ships, `tool.called` rows are persisted with
  `trace_id=''`, so a pure trace_id join will silently omit tool events. Until then,
  resolve the chain by `schema.proposed`'s embedded `run_id` + event order as a fallback
  (or merge in `tool.called` rows via the run's aggregate/time window). After W0, the
  trace_id join is exact.
- Response: `{ run: {…as above…}, chain: [ {event_id, event_type, actor, version,
  payload, created_at} … ] }`.

**A4. `GET /api/tool-calls` — read the `tool.called` events as a flat, PM-readable list.**

```
GET /api/tool-calls ?limit=100 &tool=<name> &run_id=<uuid>
```

- Filters `atlys.event_log WHERE event_type='tool.called'`, parses
  `payload.{tool, arguments}`.
- Response rows: `{ event_id, tool, arguments, trace_id, created_at }`.
- Purpose: the Inspect tab's "Tool calls" view and a debug surface for "why did the agent
  call aggregate with that filter?".

### 2.3 Frontend changes (`Atlys/ui/src/components/dashboard/`)

**A5. New `InspectTab.jsx`** — a new tab in `Dashboard.jsx` (`TABS` → add `'Inspect'`).
Four stacked sections (each its own fetch + its own "last refreshed", per Wave D):

1. **Runs** — table from `/api/runs`: run_id (mono, clickable), feature, state badge
   (reuse the `ConfidenceBadge` styling pattern for state colors:
   proposed=amber, running=blue, approved=green, rejected/failed=red), event_count,
   duration, trace link (reuse the `InsightCard` traceUrl pattern with
   `langfuseBaseUrl`/`langfuseProjectId`). Clicking a row drills into the chain (A6).
2. **Event chain** (per selected run, or "latest run" by default) — from
   `/api/runs/{run_id}`: a vertical timeline like `SchemaTimeline`, each node showing
   `event_type` badge, actor, version, timestamp, and an **expandable payload** (`<details>`
   + `<pre>` JSON pretty-printed — reuse `.diff-block` styling or a new `.json-block`).
   First/last event show duration delta.
3. **Tool calls** — flat list from `/api/tool-calls`: icon + name (reuse `TOOL_ICONS` map
   from `ChatMessage.jsx` if extracted to a shared util), short args summary
   (`summarizeToolCall` from `utils/toolSummary.js`), ok/err implied by payload, trace link.
4. **Pending runs** — from `/api/pending-runs`: the approval state machine at a glance
   (`proposed → running → approved | failed | rejected`), with the run_id a judge can
   cross-check in chat.

**A6. `EventChain.jsx`** (new, or fold into InspectTab) — the per-run timeline. Key
interactions:

- Collapse/expand each event's raw JSON payload (default: collapsed, showing only a
  one-line summary: `payload.schema_card.table`, `payload.arguments.tool`, etc.).
- **Truncate large payloads client-side.** `schema.proposed` embeds a full schema card
  (DDL + rationale + migration plan) that can be many KB — rendering it raw produces a
  wall of JSON. Default: first ~2000 chars with "show more", or reuse the spirit of
  `payloads.py::truncate_for_mcp` (list/string caps) for the REST response so the wire
  payload is slim too.
- "Copy event_id / trace_id" affordance (navigator.clipboard) — cheap, judges love it.
- Jump-to-trace link per event row (same URL builder as InsightCard).
- Give the new tab button `id="dash-tab-inspect"` to match the existing
  `dash-tab-*` ids that e2e selectors rely on.

**A7. API client additions** (`Atlys/ui/src/api/client.js`): `getRuns(limit)`,
`getRun(runId)`, `getToolCalls(params)`, and an upgraded `getEventLog(params)` that passes
filters/cursor and reads `next_cursor`. **Backward compat:** the existing Events tab calls
`getEventLog(100)` positionally — keep `limit` accepted as a bare number (or update the
Events tab call site in the same PR) so the current tab doesn't break.

### 2.4 Data shape edge cases

- `payload` may be non-JSON on rare legacy rows → parse with `try/catch`, show raw string.
- A run with no `meta.pending_runs` row (e.g. events persisted but propose never finished)
  → `/api/runs/{id}` still returns the chain via trace_id lookup on the event log; state
  shows `unknown`.
- Run grouping key: prefer `trace_id`; fall back to `aggregate_id LIKE 'spec/%'` grouping
  by the `run_id` embedded in `schema.proposed` payloads.

---

## 3. Wave B — Event & storage limits

### 3.1 `atlys.event_log` TTL (the big one)

The event log is the only unbounded table. Add retention in the bootstrap DDL
(`Atlys/service/app.py` → `DDL_STATEMENTS`):

```sql
CREATE TABLE IF NOT EXISTS atlys.event_log (
    …existing columns…
) ENGINE = MergeTree
ORDER BY (event_type, created_at)
TTL created_at + INTERVAL 90 DAY;
```

- Why 90 days: covers the whole hackathon + rehearsal with margin; well past any judge
  review window.
- ClickHouse applies TTL lazily on merges — acceptable for this scale; note it in the doc.
- Alternative (only if the cluster is version-sensitive): a periodic
  `DELETE WHERE created_at < now() - INTERVAL 90 DAY` guard job in the service. Prefer TTL.

### 3.2 Per-run event cap in the bus (`service/bus.py`)

Guard against a pathological spec emitting hundreds of events (loop-guard prevents
*infinite* loops but not *floods*).

- Add `MAX_EVENTS_PER_RUN` (default e.g. 200) in `settings.py`
  (`ATLYS_MAX_EVENTS_PER_RUN`).
- **Key the counter on `payload.run_id` (fallback: `trace_id`), NOT `aggregate_id`.**
  The bus's `aggregate_id` for run events is `spec/<spec_dir>` — the `run_id` only
  lives in the payload — so counting by aggregate would make a **second run of the
  same spec hit the first run's cap** (a real hazard for re-running the unseen spec
  during the demo). Explicit rules:
  - Events whose payload carries `run_id` (spec.run.requested, spec.ingested,
    schema.*, context.*, insight.created) count against that run_id's budget.
  - Events without a run_id (`tool.called` → `mcp/<name>`, `context.update.proposed`)
    are **exempt** from the cap (they are bounded by the 25-call chat tool budget
    already).
- When a run's counter exceeds the cap: log loudly, persist a synthetic
  `run.aborted (reason=event_cap)` event (so the chain shows *why* it stopped), and
  stop dispatching handlers for that run (persist-only mode).
- The new `run.aborted` type must be **added to `events.py`'s `EVENT_TYPES` registry**
  (the single source of truth) or `_persist_event` writes an unregistered type.
- Cap is **per run_id**, not global — parallel features must not block each other.

### 3.3 Bound the in-memory mirror (`bus.emitted`)

Currently a plain list that grows for the process lifetime. Replace with
`collections.deque(maxlen=…)` (default e.g. 2000). The mirror is only used by tests and
the dashboard's live view — a bounded ring is sufficient. Update any code that indexes it.

### 3.4 `meta.pending_runs` retention

Every run leaves a row forever. Add `TTL created_at + INTERVAL 180 DAY` to the
`meta.pending_runs` bootstrap DDL (it is the run registry; 180 days is plenty and it
keeps the Inspect "Runs" table small).

### 3.5 Optional (low priority)

- TTL on `meta.context_snapshots` / `meta.insights` (append-only, but tiny — skip unless
  judges mention storage).
- A `count()`-based soft warning in `/api/event-log` when the table exceeds N rows
  (observability nicety, not required).

---

## 4. Wave C — Trace completeness

### 4.1 Fix `tool.called` trace_id (one-line + test) — **highest priority**

`mcp_server.py` `call_tool` currently calls `self._tool_called(name, arguments)` with no
trace_id. Change to:

```python
self._tool_called(name, arguments, trace_id=getattr(self.tracer, "trace_id", "") or "")
```

- Effect: every `tool.called` row in `atlys.event_log` links to the trace (or is empty
  for out-of-run calls — acceptable).
- Test: after a `run_spec` + one read tool, the `tool.called` rows for the run carry the
  same trace_id as the run's other events.

### 4.2 Trace read-only exploration as `explore:*`

When an MCP read tool is invoked **outside** an active spec-run trace (no trace started),
start a lightweight trace so the PM's ad-hoc questions are replayable in Langfuse.

- In `call_tool`'s dispatch path: if `tracer.trace_id` is falsy (or the current trace is
  not tied to an active run), wrap the call in
  `tracer.start(f"explore:{tool_name}", session_id=None)`.
- Do **not** reuse the last run's trace (stale-trace bug); a fresh short-lived trace per
  read call, or one per chat series, is cleaner. Prefer one per **read call** for
  simplicity in MVP; revisit if Langfuse UI gets noisy.
- Spans inside `db_read` handlers already exist (`mcp_tool:db_schema`, etc.) — they just
  need a parent trace.

### 4.3 Enrich playbook spans (`service/agents/analytics.py`)

`run_playbook` currently does `self._span("playbook:" + q["kind"], label=q["label"])`.
Add output metadata so the judges' favourite spans carry the numbers:

```python
with self._span("playbook:" + q["kind"], label=q["label"],
                output={"row_count": len(rows), "elapsed_ms": <ms>, "error": err.get("error")}):
```

- Requires `tracing.py` `span()` to pass `output` through to Langfuse (it already accepts
  `**meta` and forwards `input`/`output` kwargs — verify `NullTracer` prints them too).

### 4.4 Add missing spans

| Where | New span name | What it records |
|---|---|---|
| `agents/context.py` `seed_if_empty` | `context:seed` | rows seeded, findings count |
| `agents/mv.py` `create_mv_funnel_daily` / `create_feature_rollup` | `mv:create` | DDL (truncated), success/failure |
| `migration_journal.py` `begin_apply`/`finish_apply` | `migration:<status>` | plan_hash, table, applied list, error |
| `bus.py` `_persist_event` | `bus:persist` | event_type, aggregate_id, persist ok/fail |
| `api.py` dashboard read endpoints | `rest:<endpoint>` | row counts, elapsed |

- All are optional-on-failure (never break the pipeline) — mirror the existing
  `_span()` pattern (nullcontext when tracer is None).

### 4.5 `progress_hub` trace linkage (small)

- `mcp_server.call_tool` publishes `tool_call`/`tool_done` to `progress_hub` — add the
  `trace_id` to those dicts so the UI chips can render a trace link if desired (Wave A
  tool-calls view can read it from the event log instead; this is a nicety).

---

## 5. Wave D — Refresh & staleness UX

### 5.1 Goal

The dashboard should never silently show stale data, and refreshes should never blank the
screen. Every tab shows *when it was last refreshed* and *how stale it is*.

### 5.2 Per-tab refresh policy

| Tab | Auto-refresh | On chat completion | Manual button | Rationale |
|---|---|---|---|---|
| Insights | none (or 60 s optional) | ✅ (existing refreshTrigger) | ✅ | Insight cards only change on run completion |
| Schema | none | ✅ | ✅ | Changelog only changes on DDL |
| Context | none (version-pinned by design) | ⛔ (stop auto-reset) | ✅ | Version dropdown = explicit pin; don't yank it under the user. **Wave D must also stop `Dashboard.jsx` from resetting `selectedVersion` to null on `refreshTrigger`** — today a chat-triggered refresh silently jumps the viewer back to the latest version, contradicting the pin. Manual refresh only, and only refetches the pinned version. |
| Events | ✅ 5 s poll (existing) | ✅ | ✅ | Live feed; keep 5 s |
| **Inspect (new)** | ✅ 10 s poll on Runs/chain; tool-calls on-demand | ✅ | ✅ | Run state machine is the one thing that *can* change mid-turn (running→approved) |

- Keep the existing `refreshTrigger` (chat-finished) as the *primary* invalidation
  signal; polling is a secondary safety net, not the source of truth.

### 5.3 "Last refreshed" indicator (the explicit ask)

- New shared component `LastRefreshed({ at, state, intervalMs })`:
  - Renders `Updated 2s ago` / `Updated 3:41:07 PM` (live-ticking every second until
    `>60s`, then `Updated 5m ago`).
  - States: `fresh` (green dot), `refreshing` (spin, keeps old data visible),
    `stale` (amber — exceeds threshold, e.g. 2× the poll interval for polling tabs),
    `error` (red — last fetch failed; show "Last refresh failed — retry").
- Place it in the dashboard tab bar right of the refresh button, plus per-section in the
  Inspect tab (each section fetches independently).
- Implementation: `Dashboard` keeps `lastRefreshedAt` + `lastError` per tab (a small
  `useRef` map or a `refreshMeta` state object); the ticking text uses a
  `useInterval(1s)` that only re-renders the timestamp chip, not the whole panel.

### 5.4 Stale-while-revalidate (kill the flicker)

Current behavior replaces content with a spinner on every fetch. Change to:

- On refetch: keep rendering the previous data; show `refreshing` state in the chip;
  swap in new data when the response arrives.
- Only show the full-screen spinner on first load of a tab (no data yet) or after an
  explicit user click with no cached data.
- `Dashboard.jsx` restructure: `const [data, setData] = useState(null)` +
  `const [meta, setMeta] = useState({state:'idle', at:null})` per tab; do not clear
  `data` when starting a fetch.

### 5.5 Change detection (avoid pointless refetches)

Cheap server-side version header instead of always refetching:

- `api.py`: each dashboard read sets a response header `X-Atlys-Updated` = the newest
  `created_at` (or a monotonically increasing `meta` version) across the returned rows.
- Client: store the header per tab; on the next scheduled poll, if the header is
  unchanged and age < threshold, skip the state update (still update "last checked").
- **Scope the header check to Insights / Schema / Context.** Events and Inspect poll
  precisely because data *is* changing every poll during a run — header-skipping adds
  complexity on the one tab where it rarely helps. Leave Events/Inspect on naive polling.
- Optional `/api/dashboard-version` endpoint: single cheap query
  `SELECT max(created_at) FROM atlys.event_log UNION ALL …(insights, changelog)` → a
  1-row poll target for all tabs. **Stretch** — the header approach covers the demo.

### 5.6 Race/cancellation hygiene

- Use an `AbortController` per fetch; abort the previous tab's fetch on tab switch.
- Ignore stale responses via a request sequence number (or compare
  `meta.state.seq`), so a slow Events poll can't clobber a fresh chat-triggered refetch.

### 5.7 Error states

- On fetch failure: keep old data, mark chip `error`, show a non-blocking inline banner
  ("Couldn't refresh — showing data from 3:41 PM"). Do not nuke the panel.
- Distinguish network failure vs 4xx/5xx in `client.js` (throw typed errors with the
  endpoint name so the chip can label it).

---

## 6. Acceptance criteria

**Wave A**
- [ ] `/api/event-log` accepts `run_id`/`event_type`/`actor`/`before`/`after`/`count` and
      stays backward-compatible.
- [ ] `/api/runs` and `/api/runs/{run_id}` return correct chains incl. an edge run with
      no `pending_runs` row (`state: unknown`).
- [ ] Inspect tab renders Runs, Event chain, Tool calls, Pending runs; payloads expand;
      large payloads (> ~2000 chars) are truncated with a show-more control;
      trace links open Langfuse (project-scoped when `langfuse_project_id` is set).

**Wave B**
- [ ] `atlys.event_log` has `TTL created_at + INTERVAL 90 DAY` in bootstrap DDL.
- [ ] Bus enforces per-run cap; over-cap run is aborted with a persisted
      `run.aborted (reason=event_cap)` event; other runs unaffected.
- [ ] `bus.emitted` is a bounded deque (mirror behavior unchanged for tests).
- [ ] `meta.pending_runs` has TTL.

**Wave C**
- [ ] `tool.called` rows for a run carry the run's `trace_id` (unit test).
- [ ] A `db_schema`/`aggregate` call outside a run produces an `explore:*` trace with
      non-empty trace_id; no stale-trace reuse.
- [ ] Playbook spans include `output.row_count`/`elapsed_ms`; `NullTracer` prints them.
- [ ] New spans (seed, mv, migration, bus persist, rest) never break the pipeline when
      tracing is off or failing.

**Wave D**
- [ ] Every tab shows a live "Updated …" chip with fresh/refreshing/stale/error states.
- [ ] Refetch keeps old data visible (no spinner flash) after first load.
- [ ] Chat-triggered refresh keeps the selected Context version pinned (no auto-reset
      of `selectedVersion` to the latest).
- [ ] Tab-switch abort + seq guard: a slow old fetch cannot overwrite new data.
- [ ] Events tab still polls at 5 s; Inspect at 10 s; no tab polls harder than today.

---

## 7. Test plan

| # | Area | Case | Expected |
|---|---|---|---|
| 1 | API | `/api/event-log?run_id=<x>` | Only that run's events, chronological |
| 2 | API | `/api/event-log?before=<cursor>` | Older page only; `next_cursor` present |
| 3 | API | `/api/runs` empty DB | `[]` |
| 4 | API | `/api/runs/{unknown}` | 404 with `{error}` |
| 5 | Bus | spec emitting > cap events | `run.aborted` event persisted; handler dispatch stops |
| 6 | Bus | two features in parallel | Each capped independently |
| 7 | Tracing | read tool outside run | `explore:*` trace, trace_id on `tool.called` row |
| 8 | Tracing | playbook span | `output.row_count`/`elapsed_ms` present (NullTracer prints) |
| 9 | UI | slow refetch on Insights | Old cards stay visible; chip spins; new data swaps in |
| 10 | UI | Events poll while on another tab | No network churn; no stale overwrite (abort+seq) |
| 11 | UI | backend down | Chip → error; panel keeps last data; banner shown |
| 12 | E2E (dry-run) | full spec run → open Inspect | Chain matches chat's narrated steps; trace links resolve |

Existing dry-run suite (`Atlys/tests/`) is the harness — new tests: `test_event_log_ttl`
(DDL contains TTL), `test_bus_event_cap`, `test_tool_called_trace_id`,
`test_explore_trace`, `test_event_log_filters`.

---

## 8. Implementation order & effort

| Step | Work | Est. | Depends on |
|---|---|---|---|
| W0 | Wire `trace_id` into `_tool_called` + unit test | 0.5 h | — |
| W1 | Event-log TTL + pending_runs TTL + bounded deque + bus cap + tests | 2–3 h | — |
| W2 | `/api/event-log` filters + `/api/runs` + `/api/runs/{id}` + `/api/tool-calls` | 2–3 h | W1 (for sane data) |
| W3 | InspectTab + EventChain + client fns + CSS | 4–5 h | W2 |
| W4 | LastRefreshed chip + stale-while-revalidate refactor of Dashboard | 2–3 h | — |
| W5 | explore:* traces + playbook span output + missing spans | 1–2 h | W0 |
| W6 | Header-based change detection (optional) | 1–2 h | W4 |
| W7 | E2E dry-run pass + docs update | 1–2 h | W2–W5 |

**MVP cut:** W0 → W1 → W2 → W3 → W4 (the demo-visible wins). W5–W6 polish; W7 mandatory
before the unseen spec.

---

## 9. Open questions (decide at implementation)

1. **Inspect tab polling**: 10 s for Runs is fine, but should the event chain auto-poll
   when a run is in `running` state? (Proposal: yes, only while running.)
2. **`explore:*` trace granularity**: one trace per read call vs one per chat series?
   (Proposal: per read call for MVP; revisit if Langfuse gets noisy.)
3. **TTL values**: 90 days event log / 180 days pending_runs — confirm acceptable for the
   cluster's storage credits.
4. **Should `/api/runs` also power the existing Events tab** (migrate Events → Inspect)
   or stay separate? (Proposal: keep Events; Inspect is the richer sibling.)
