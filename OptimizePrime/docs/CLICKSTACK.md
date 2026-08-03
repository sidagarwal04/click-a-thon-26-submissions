# CLICKSTACK — the OSS integration, and where the concurrency chart comes from

> **Summary:** ClickStack observes pipeline lag and query cost over OTLP and serves the concurrency UI.
> The 2026-08-01 live capture proves 24 sources, seven dashboards, 53 tiles and eight working filters.
> The current candidate exposes all 12 declared dataset filters and generic map-backed future fields.
> Existing named sources now converge by full-replacement PUT instead of retaining stale select SQL.
> Cloud deployment, signed-in filter verification, screenshots and a live demo/video remain required.

> **Panel reference:** [CLICKSTACK_DASHBOARDS.md](CLICKSTACK_DASHBOARDS.md) records every captured tile.

We use HyperDX built into ClickHouse Cloud: it reads `sonyliv` directly with no separate connection
string or IP allowlist. `tools/clickstack-cloud.sh` provisions the seven dashboards (headline,
drilldown, content, time-window trend, pipeline health, query cost and user-level) plus their sources
and saved searches. Its connection id comes once from the ClickStack MCP into `.env` as
`CLICKSTACK_CONNECTION_ID`; `CLICKSTACK_SKIP_APPLY=1` makes a run control-plane-only.

The local alternative is `make stack-up && make clickstack`. Both modes chart plain views from
`sql/20_views.sql` and `sql/87_viz.sql`; a chart tool cannot read an `AggregateFunction` state column.
Data ends **2026-07-26**, so the default 15-minute window is empty for dashboards 1–4 and 7; 5–6 use
operator time. Historical evidence: `evidence/clickstack-dashboards.txt` and
`evidence/clickstack/tile-verification-2026-08-01.txt` (all 53 captured tiles, signed-in).

## Why ClickStack is the chart, not just the telemetry

The statement puts polished frontends out of scope — "a minimal visualization of concurrency over
time is enough to demo" ([PROBLEM.md](PROBLEM.md), Out of scope). ClickStack is separately the OSS
integration we are asked to use. Pointing HyperDX at our own serving layer satisfies both with one
component and zero UI code, and every chart is backed by a real query against the graded service
rather than a screenshot of a number someone typed.

## Submission evidence gate added by upstream

The updated common submission README makes ClickStack evidence explicit. The submission folder must
contain the committed wiring (Compose/deployment configuration, redacted `.env.example`, collector
and integration configuration), name the ClickHouse service and tables ClickStack reads or writes,
and include screenshots of the dashboards/searches actually used. A screenshot is still insufficient
on its own: the hosted demo and the 2–3 minute video must walk through ClickStack live and explain its
role in the architecture.

The code candidate is ready for that capture, but this session deliberately did not mutate Cloud.
Before recording, an operator must run `tools/clickstack-cloud.sh`; it first converges the metadata
migrations in `sql/00_schema.sql` and `sql/10_intervals.sql` plus `sql/87_viz.sql`, then PUTs the 27
named sources and 12-filter drilldown. Verify every filter changes the concurrency curve in a signed-in
browser, then capture the UI for the submission README. Until those steps happen, only the older
24-source/eight-filter deployment is proven live.

## Bring it up

```bash
make stack-up      # ClickHouse + ClickStack; waits for /health
make clickstack    # register the team + OTLP key, then our concurrency sources
open http://localhost:8080
```

Then in HyperDX: pick source **Concurrency total (minute)**, set the time range to
**2026-07-14 → 2026-07-26**, and chart `concurrent` over `minute`.

## Option B — HyperDX built into ClickHouse Cloud (what we actually use)

ClickHouse Cloud ships HyperDX inside the service. Confirm it by looking for the internal user it
provisions:

```bash
tools/ch -c "SELECT name FROM system.users WHERE name LIKE 'hyperdx%'"   # -> hyperdx-alert-internal
```

This is the simpler path and needs **no credentials, no connection, and no IP allowlist change** —
HyperDX is already inside the service, so it reads `sonyliv` as `default` with nothing to configure.
The local `cs` container and `tools/clickstack-sources.sh` are only for Option A.

**It IS scriptable** — via the Cloud control-plane API, not the console session:
`/v1/organizations/{org}/services/{svc}/clickstack/{sources,dashboards,alerts,saved-searches,...}`,
HTTP basic with a Cloud API key (`CH_API_KEY_ID` / `CH_API_KEY_SECRET` in `.env`). Run
`tools/clickstack-cloud.sh`, which provisions sources, the demo dashboard and saved searches.

**The connection id, once.** A source needs a `connection` id and the REST API returns connections
only *nested inside sources* — with no `/clickstack/connections` endpoint (404s on GET and POST).
On a fresh service with zero sources there is therefore nothing to read it from. Resolve it once and
put it in `.env` as `CLICKSTACK_CONNECTION_ID`; after that the script is fully autonomous.

The cleanest way to get it is the **clickstack MCP**, whose `clickstack_list_sources` returns a
top-level `connections` array even when `sources` is empty:

```
claude mcp add clickstack --transport http https://mcp.clickhouse.cloud/clickstack \
  --header "x-service-id: <serviceId>"
```

The MCP can also create sources, dashboards and saved searches directly (`clickstack_save_source`,
`clickstack_save_dashboard`, `clickstack_save_saved_search`) and query them
(`clickstack_timeseries`, `clickstack_sql`) — which is how the numbers below were verified.

If you would rather do the first source by hand:

**ClickHouse Cloud console → HyperDX → Sources → New source**

| Field | Value |
|---|---|
| Name | `Concurrency total (minute)` |
| Database | `sonyliv` |
| Table | `v_concurrency_minute_total` |
| Timestamp column | `minute` (`DateTime`) |
| Value column to chart | `concurrent` (`UInt64`) |

Repeat with `v_concurrency_minute_stateless` for the per-platform/country/content breakdown; it has
the same `minute` timestamp column plus the three dimensions.

Then set the time range to **2026-07-14 → 2026-07-26** before concluding anything is broken.

## What the two scripts do

| Script | Job |
|---|---|
| `tools/clickstack-bootstrap.sh` | registers the team and prints `CLICKSTACK_INGESTION_KEY`. OTLP 4317/4318 do **not** bind until a team exists |
| `tools/clickstack-sources.sh` | self-hosted: registers a ClickHouse connection and converges named sources with full-replacement PUTs |
| `tools/clickstack-cloud.sh` | hosted: converges sources + dashboards and creates saved searches over the Cloud API |

## The sources

The live 2026-08-01 capture has 24 sources. The current script declares 27, adding resolution and
generic event/content-dimension surfaces. The load-bearing ones:

| Source | View | Why this shape |
|---|---|---|
| `Concurrency ACCURATE (minute)` | `v_concurrency_minute_delta_total` | the headline — gap + pause model off the delta serving path |
| `Concurrency total (minute)` | `v_concurrency_minute_total` | stateless baseline, charted beside it |
| `Concurrency NAIVE session-span (minute)` | `v_concurrency_minute_naive` (87_viz) | the third model — the over-count made visible (peak 3,743) |
| `Session minutes (drilldown)` | `v_session_minutes` (87_viz) | session-minute grain with all 12 declared filter dimensions: content_id, title, video_type, category, show_name, platform, country, app_version, audio/subtitle language, player_version and video_resolution |
| `Dynamic event/content dimensions` | `v_dynamic_*_dimension_values` (87_viz) | generic EAV fallback: a future map key is queryable before it earns a named, optimized filter |
| `Concurrency by platform/country/app_version/audio_language/subtitle_language/player_version` | `v_cc_by_*` (87_viz) | one source per dimension AT ITS OWN GRAIN, so `max()` is a genuine peak |
| `User concurrency (minute)` | `v_user_concurrency_minute_total` | value column is **`concurrent_users`**, not `concurrent` |
| `Concurrency by title/video_type/category` + `Content NOW by *` | `v_concurrency_minute_*`, `v_concurrency_*_now` (80_content) | content tier; NOW sources are timestamped by `as_of` |
| `Rolling windows (minute)` | `v_cc_rolling_total` (85_windows) | rolling 5/15/60 peaks and time-weighted averages |
| `Tumbling hour (cube)` | `v_cc_tumbling_hour` | stored hour peaks; tiles pin the cube level `('*','*',-1)` |
| `Pipeline watermark (current)` | `v_cc_watermark`, ts = **`now()`** | one-row current-state view; query-time stamp lets it share a recent range with query_log tiles |
| `ClickHouse query_log (our own queries)` | `system.query_log` | latency + bytes read, server-side truth |

**Do not SUM `concurrent` across dimensions.** A session watching two content_ids appears under both;
the total view re-merges the underlying states instead, which deduplicates. This is the same trap
described in [ARCHITECTURE.md](ARCHITECTURE.md) — peak is not summable.

The three models are charted side by side — the comparison is an explicit deliverable, so they are
never merged behind one name. At the peak minute the accurate model reads **2,917** against the
stateless **2,894** and the naive span **3,708** (naive's own peak, 3,743, lands three minutes
later — it cannot see viewers leave).

The `_intervals` views expand each active interval across the minutes it covers. That is the
O(sessions × minutes) explosion the statement warns about and is **not** the serving path —
`cc_minute_delta` (TODOS H3) is. At 30,769 intervals it answers in ~60 ms, so it charts the real
model today; swap the source to the delta table when H3 lands, the columns match on purpose.

## Verified

Through HyperDX itself, not by querying ClickHouse directly.

**Hosted**, via the MCP's `clickstack_timeseries` against the provisioned source — the live-event
curve renders end to end:

```
2026-07-26 10:00 →  61      ramp
             10:30 → 1048
             10:55 → 2894   ← peak, matches the ClickHouse-side figure exactly
             11:25 →  889
             11:30 →    7   decay
28 ms · 83,648 rows read
```

**Self-hosted**, through its proxy:

```
POST /clickhouse-proxy?query=... with header x-hyperdx-connection-id
-> 200 in 0.52s
   peak 2894 concurrent @ 2026-07-26 10:56
   elapsed 0.050s · rows_read 91,292 · bytes_read 18.6 MB
```

## The dashboards (seven of them — this is the 25%-of-rubric surface a judge sees)

`tools/clickstack-cloud.sh` provisions and **converges** all seven. Verified tile-by-tile through
HyperDX's own query path — transcripts in `evidence/clickstack-dashboards.txt` and
`evidence/clickstack/tile-verification-2026-08-01.txt` (all 53 tiles, signed-in); offline demo
fallback (same numbers, no network) in `docs/artifacts/2026-08-01-clickstack-dashboards.html`,
regenerable via `tools/clickstack-artifact.sh`. Dashboards 1–3 and 7 open with a **markdown caption
tile** stating the trap a viewer would otherwise fall into (peaks not summable: +2.4% platform /
+94.7% content; title not a key; users are a set — see CLICKSTACK_DASHBOARDS.md).

| Dashboard | Time range to set | What it proves |
|---|---|---|
| **SonyLIV concurrency** | 2026-07-14 → 07-26 | the three models side by side — accurate **2,917** vs stateless 2,894 vs naive **3,743** — the over-count VISIBLE, never merged behind one name |
| **SonyLIV drilldown — sessions & users** | 2026-07-14 → 07-26 | Live capture: **8 working filters**. Candidate: all **12 declared dimensions**, adding `video_resolution`, `show_name`, `video_type` and `category`, pending deployment/capture. All use `appliesToSourceIds`; generic map-backed sources support later unknown keys. |
| **SonyLIV content** | 2026-07-14 → 07-26 | title / video_type / category curves + the NOW panel (`v_concurrency_*_now`) |
| **SonyLIV time-window trend** | 2026-07-14 → 07-26 | rolling 5/15/60 peaks & averages; tumbling 15-min via a **raw-SQL tile** calling the parameterised view; tumbling 1-hour straight from `cc_hour_agg` |
| **SonyLIV pipeline health (cloud)** | **last 24 h** | watermark lag (source stamped `now()`), build-stage timing & rows from `system.query_log` (the exact `internal/pipelinehealth` filters), reconcile-gate runs |
| **SonyLIV query cost** | **last 24 h** | p95/p50/max latency AND **bytes read** of our own queries, plus heaviest query shapes |
| **SonyLIV user-level** | 2026-07-14 → 07-26 | signed-in concurrency via `uniqExact` — peak users **2,844** vs sessions 2,917, the multi-session gap (**73** at 10:56, ratio 1.0257) via raw-SQL joins, and per-dimension user counts as `count_distinct(user_id)` over session-minutes (never the by-dimension source's `max()` — that is the 285-vs-1,837 trap) |

**The drilldown arithmetic rule, learned by measurement:** `max(concurrent)` over a view grained
finer than the tile's `groupBy` is the max single *combination*, not the group total — the first
by-platform tile showed **285** where the truth was **1,837**. Breakdown tiles therefore read
per-dimension views (`sql/87_viz.sql` sums deltas at that grain, THEN running-sums), and the
filterable drilldown counts `count_distinct` over session-minute rows (`v_session_minutes`) — the
one aggregation correct under ANY filter combination. Filters name ONLY the session-minute source:
sources without the column would error rather than no-op.

**Hosted has no OTLP path** (no `otel_*` tables — verified), so pipeline health here is
cloud-native; the OTLP-fed twin from `sonyliv observe` lives on the local stack
([OBSERVABILITY.md](OBSERVABILITY.md)).

**Alerts: three, on concurrency decline** — `tools/clickstack-alerts.sh`, an eighth dashboard and its
own document, [DECLINE_ALERTING.md](DECLINE_ALERTING.md). This file previously said *"No alerts,
deliberately: the dataset is frozen, so a threshold alert either never fires or fires forever"*. That
holds only for an alert anchored to `now()`; these anchor every window to
`v_cc_watermark.sealed_watermark`, the data's own clock, which is the correct anchor on a frozen file
and on a live stream alike.

A re-run sends a full-replacement **PUT for every existing named source and dashboard** rather than
skipping it, so a stale select expression or hand-edit cannot silently outlive the committed
definition. It runs each dashboard payload through `POST /clickstack/dashboards/validate` *before*
creating, so a malformed tile fails with a JSON path rather than as a blank panel mid-demo.

Schema notes, from the spec rather than guesswork: `ClickStackCreateDashboardRequest` requires
`{name, tiles}`; each `ClickStackTileInput` requires `{name, x, y, w, h}`; a line tile's
`ClickStackLineBuilderChartConfig` requires `{displayType, sourceId, select}`. There is also a
raw-SQL variant (`ClickStackLineRawSqlChartConfig`) needing `{configType:"sql", connectionId,
sqlTemplate, displayType}` if a tile ever outgrows the builder.

## Gotchas

- **Empty chart?** Time range. The data is July 2026, not now. This costs everyone ten minutes once.
- The API serves **no route at `/`** and answers 404 there. Readiness is `/health` — probing `/` with
  `curl -f` waits out the full timeout against a server that was up the whole time.
- Registration lives at the **root** (`/register/password`), not under `/api`.
- The `cs` container needs a TTY or it boots fully and then exits 129 — `tty: true` in compose.
- ClickStack bundles its **own** ClickHouse 26.5.6 for otel data. That is not our database; do not
  build the project on it. Our connection points at Cloud explicitly.
- The Cloud API has **no connections endpoint** — `/clickstack/connections` 404s on GET and POST and
  no `ClickStackConnection` schema exists. Opening HyperDX once in the console is unavoidable.
- `-u "$ID:$SECRET"` must be **quoted at the call site**. zsh does not word-split an unquoted
  variable holding `-u id:secret`, so curl gets one argument and the API returns
  `401 "Key is not found"` — which reads exactly like a bad key and sends you debugging the wrong thing.
- **Create and update validate against different schemas.** `filters[]` on POST/validate is
  `ClickStackFilterInput`, which *forbids* `id`; on PUT it is `ClickStackFilter`, which *requires*
  it. The script emits both shapes from one definition.
- `/clickhouse-proxy` requires **POST** with the query in the URL. GET returns 405; a missing
  `x-hyperdx-connection-id` header returns a Zod validation error.
- A dashboard **PUT regenerates every tile id** (verified). Dashboard ids and URLs are stable
  across re-runs; tile deep-links are not.
- A builder select with `aggFn: count` must **omit** `valueExpression` — the validator rejects the
  pair outright.
- `v_user_concurrency_minute*` exposes **`concurrent_users`**, not `concurrent` (renamed on dev).
  The user sources/tiles were silently broken until this was caught by querying the tile, not by
  the 200 the provision call returned — verify tiles by executing them, not by creating them.
- Raw-SQL tiles should include `WHERE $__timeFilter(col)` or they ignore the dashboard time picker
  (the API warns but accepts).
- A dashboard's **default time range is not settable via the API** — setting 2026-07-14 → 07-26
  before a demo is a human step, every time.
