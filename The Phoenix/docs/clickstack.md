# ClickStack integration

ClickStack (HyperDX plus the OpenTelemetry collector) running against **our** ClickHouse Cloud
service, with a live dashboard on `phoenix.concurrency_deltas` and a read-budget panel built from
`system.query_log`.

Evidence: `[V:clickstack_integration]`. Every number on this page was produced by a command this
session; the artifact records which.

## Why ClickStack and not Langfuse or LibreChat

The problem statement requires meaningfully integrating one of the three and says superficial
inclusion will not count. Two of the judging criteria are what our queries read and how far
ingest lags. Those are observability numbers, so ClickStack is the option where the integration
surfaces the thing being graded instead of sitting beside it. Langfuse is LLM observability and
this pipeline has no LLM, so any integration would have been contrived.

## Rebuild from nothing

```bash
cd docker/clickstack
docker compose --env-file ../../.env up -d     # waits for health, roughly 60 seconds
cd ../..
./scripts/clickstack_setup.sh                  # idempotent, safe to re-run
open http://localhost:8090
```

Login: `phoenix@example.com` / `PhoenixClickathon2026!` (overridable via `HDX_EMAIL` and
`HDX_PASSWORD`). This is a local container on a laptop, so the credential is a convenience, not a
secret; nothing is exposed beyond localhost. **Nobody demoing this has to type it.** The ClickStack
link in either console points at `/clickstack`, a route that signs in server-side and redirects
straight to the provisioned dashboard.

### Why a sign-in route rather than no sign-in at all

The obvious ask for a demo is to remove the login entirely. Two measurements say that costs more
than it buys:

- HyperDX enforces auth **server-side**. An unauthenticated `GET /api/dashboards` and `GET /api/me`
  both return `401` on this container, so nothing client-side can bypass it.
- Its no-login local mode is a **build-time** flag, not a runtime one:
  `NEXT_PUBLIC_IS_LOCAL_MODE=true` appears in the image's own `build:clickhouse` script, and the
  shipped bundle carries `"NEXT_PUBLIC_IS_LOCAL_MODE":"false"`. Flipping the value in the served
  `__ENV.js` changes what the browser reads and not what the API enforces.

Local mode also stores connections and sources in the browser rather than on the server, which is
exactly where `scripts/clickstack_setup.sh` puts the five provisioned tiles and the Cloud
connection. Turning it on would trade one sign-in for an empty app asking a judge to configure a
ClickHouse connection by hand.

So the login stays and the viewer is carried through it. `frontend/src/app/clickstack/route.ts`
POSTs the credential to `/api/login/password`, re-issues the returned `connect.sid` on its own
response, and redirects. It works because HyperDX scopes that cookie with `Domain=localhost` and
cookies are scoped by host, **not by port**: a cookie set on `localhost:3200` is sent to
`localhost:8090`. The dashboard id is looked up through the API rather than hardcoded, since
`clickstack_setup.sh` creates a different one per install.

Verified this session: `GET /clickstack` returns `307` to
`/dashboards/<id>`, and that cookie answers `200` on `/api/me` and returns the
`Phoenix Foreground Concurrency` dashboard from `/api/dashboards`. Every failure degrades to the
plain HyperDX URL, so a stopped container looks like a stopped container and a wrong credential
looks like a login form, rather than either becoming an error page on the console.

`scripts/clickstack_setup.sh` provisions everything through HyperDX's REST API rather than through
the UI, which is what makes this page reproducible. The panel SQL in that script is the panel
definition, not a description of one.

Verified this session `[V:clickstack_integration]`: image
`clickhouse/clickstack-all-in-one:latest`, HyperDX `2.33.0`, container health `healthy`, 5 tiles,
11 `otel_*` tables created in our service.

## The trap: a green container proves nothing

`CLICKHOUSE_ENDPOINT` points the OTel **collector** at our Cloud service, and that part works: 11
`otel_*` tables now exist in our `default` database, created by the container, not inside it.

But the HyperDX **app** ships with a connection named "Local ClickHouse" pointing at
`http://localhost:8123`, the instance bundled in the image. Listing `/api/connections` after a
clean `up -d` returned exactly that. So all of these are true simultaneously while every chart
still reads the wrong database:

- the container is healthy
- the `otel_*` tables in our service are populating
- the UI loads and charts render

`scripts/clickstack_setup.sh` therefore creates a **second** connection to
`https://${CH_HOST}:8443` and hangs the source and all five panels off that one. The artifact
records both connection hosts side by side so the distinction is visible rather than asserted.

**And the script now proves it rather than assuming it.** Step 5 runs the panel SQL through
HyperDX's *own* `/api/clickhouse-proxy`, pinned to the connection the panels use, and fails if it
does not get rows back. Running the SQL against ClickHouse directly only proves the SQL is valid;
it says nothing about which database HyperDX will choose. Measured on the run behind
`[V:clickstack_integration]`: HyperDX read **33,489** delta rows from `phoenix` and a watermark lag
of **53s** through that connection. Both figures move with the live stream and are quoted here as
the artifact recorded them, not as a current reading. If
the app ever falls back to the bundled instance, `phoenix.*` does not exist there and the setup
fails loudly instead of producing an empty dashboard.

Sample returned through the proxy, newest minutes first, which is the curve panel's own query:

```
minute                concurrent_sessions
2026-08-01 16:09:00   42
2026-08-01 16:08:00   68
2026-08-01 16:07:00   62
2026-08-01 16:06:00   63
```

Note the port. `8443` is the HTTPS interface; `CH_PORT=9440` in `.env` is the native secure
protocol port for `clickhouse-client`. Pointing an HTTPS client at 9440 is the same bug the
Next.js console shipped with, and it is why `frontend/src/lib/env.ts` now refuses to read
`CH_PORT` at all.

## Source registration

| Field | Value |
|---|---|
| Name | `Phoenix concurrency deltas` |
| Kind | `log` |
| Connection | `Phoenix ClickHouse Cloud` |
| Table | `phoenix.concurrency_deltas` |
| Timestamp expression | `minute` |
| Default select | `minute, platform, country, video_type, app_version, content_id, delta` |

Kind `log` because HyperDX's kinds describe its own OTel schemas and `log` is the one that accepts
an arbitrary table with a time column. The delta table is not a log; the kind is a container for
"time-series rows", nothing more.

## Panel definitions

Every panel is a `configType: "sql"` tile, so the SQL below is what runs. Two rules apply to all
of them, both required by the delta model:

**`sum(delta)` with a running total, seeded from the first minute of the series.** A row in
`concurrency_deltas` is a *change*, not a level. Plotting `delta` directly plots the first
derivative and reads as noise around zero. Starting the cumulative sum at the panel's own time
bound instead of the start of the series makes the curve begin at zero and undercount every
session that was already watching.

**No `FINAL`.** `concurrency_deltas` is a `SummingMergeTree`, so `sum(delta)` is correct whether
or not a merge has run. `FINAL` would force merge-on-read across the whole part set, which is the
cost this schema exists to avoid.

### 1. Concurrent sessions per minute

```sql
SELECT minute,
       toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent_sessions
FROM (SELECT minute, sum(delta) AS d FROM phoenix.concurrency_deltas GROUP BY minute)
ORDER BY minute ASC
```

### 2. Event watermark lag

```sql
SELECT dateDiff('second', max(event_timestamp), now()) AS event_watermark_lag_seconds,
       max(event_timestamp)                            AS newest_event,
       count()                                         AS rows_held
FROM phoenix.raw_events
```

Measured 1 second behind wall clock across 1,013,988 rows while the replay was running
`[V:clickstack_integration]`.

Reads `raw_events` and not the delta table, because the question is about arrival and the delta
table is one derivation step behind it. It uses `event_timestamp` and **not** `ingested_at`:
`ingested_at` was added by a later `ALTER`, ClickHouse does not rewrite existing parts, so for the
905,558 pre-`ALTER` rows its `DEFAULT now()` is evaluated at read time and equals the reading
query's own wall clock. A lag panel built on it reports a confident, meaningless zero. Proven in
`[V:ingested_at_nondeterminism]`.

### 3 and 4. Peak by platform, peak by country

```sql
SELECT platform, max(c) AS peak_concurrent_sessions
FROM (
    SELECT platform, minute,
           toInt64(sum(d) OVER (PARTITION BY platform ORDER BY minute ASC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
    FROM (SELECT platform, minute, sum(delta) AS d
          FROM phoenix.concurrency_deltas GROUP BY platform, minute)
)
GROUP BY platform
ORDER BY peak_concurrent_sessions DESC
```

Country is the same query over `country`. `PARTITION BY` is load-bearing: peak per platform is not
a slice of the global peak, because platforms peak at different minutes. That is the same property
`sql/queries/serving/test_peak_is_not_a_rollup.sql` asserts for the serving layer.

Measured top platform `ANDROID_PHONE` at 1,743 `[V:clickstack_integration]`.

### 5. What the serving queries read

```sql
SELECT query_id, toStartOfMinute(event_time) AS minute,
       read_rows, read_bytes, toUInt64(query_duration_ms) AS elapsed_ms, tables
FROM clusterAllReplicas(default, system.query_log)
WHERE type = 'QueryFinish'
  AND event_time > now() - INTERVAL 6 HOUR
  AND hasAny(tables, ['phoenix.concurrency_deltas', 'phoenix.user_concurrency_deltas',
                      'phoenix.session_minute_runs', 'phoenix.user_minute_runs'])
ORDER BY event_time DESC
LIMIT 200
```

This is the read-budget panel, carrying `read_rows`, `read_bytes` and `elapsed_ms` keyed by
`query_id`. 4,340 matching rows in the trailing 6 hours `[V:clickstack_integration]`.

`clusterAllReplicas` because we are on Cloud: `system.query_log` is per-replica, and a bare read
returns only whichever replica answered, which silently omits queries served elsewhere.

## Live here, frozen in the console: a deliberate split

These panels carry **no** `frozen_before` predicate. The Next.js console does. That is a decision,
not an inconsistency:

| Surface | Reads | Answers |
|---|---|---|
| ClickStack (this) | live, unfiltered | is the pipeline healthy right now |
| Next.js console | frozen to `event_timestamp < 2026-08-01` | what is the graded number |

A watermark-lag panel cannot be frozen, because freezing it is what makes lag unobservable. A
graded average cannot be live, because `concurrency_deltas` does receive live rows (measured this
session), so the headline number would drift away from every committed artifact between two page
refreshes. Recorded in `docs/DECISIONS.md`.

## What is not done

- No alerting on the watermark-lag panel. HyperDX supports it; the threshold is a product decision
  nobody has made, and inventing one would be a recommendation presented as a finding.
- Panels are not parameterised by a dashboard-level filter widget. Platform and country are covered
  by dedicated grouped panels instead, which was cheaper and is demoable; a filter widget is the
  better answer if this outlives the submission.
- Spans are not pushed through OTLP on 4317/4318. `system.query_log` already holds `read_rows`,
  `read_bytes` and `elapsed_ms` on the same service, so emitting spans would duplicate data that
  is already queryable. Stated as a deviation from TASK.md 2.1 layer 3 rather than a completion of
  it. Owner: unassigned.
