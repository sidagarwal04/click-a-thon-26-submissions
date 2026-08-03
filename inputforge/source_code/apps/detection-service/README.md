# Detection service

The detection service is Sentinel's ClickHouse-native Stage 1 pipeline. It
turns ad events into anomaly evidence and canonical incidents; it does not run
an LLM, poll for incidents, call webhooks, or start investigations. The
dashboard and incident-detail page are the entry points for investigation.

## Runtime model

```
inmobi.ad_events
  → metrics_hourly / segment_metrics_hourly     (reactive MVs)
  → metric_zr_hourly                             (refreshable MV)
  → inmobi.anomalies / inmobi.segment_anomalies  (refreshable MVs)
  → mv_incidents                                 (refreshable MV)
  → inmobi.incidents
  → Sentinel dashboard
```

Two execution models, on purpose — see `sql/mv/README.md` for the full
reasoning (including a real production bug that drove this split):

- **Reactive.** Only the two single-hop rollups — `ad_events` →
  `metrics_hourly` (`sql/mv/01`) and `ad_events` → `segment_metrics_hourly`
  (`sql/mv/07`) — fire directly on `INSERT` into `ad_events`. Proven
  reliable even under a large bulk load.
- **Refreshable.** Everything downstream of the rollups reschedules itself
  inside ClickHouse (`REFRESH EVERY ...`, chained via `DEPENDS ON`) and
  recomputes full history on every cycle rather than reacting to inserts:
  the seasonal z-residual (`sql/mv/02`), the consolidated global detection
  ensemble (`sql/mv/03`, `trend_seasonal` + `proportion` + `day_level` →
  `anomalies`), the daily noise baseline (`sql/mv/06`), the consolidated
  segment detection ensemble (`sql/mv/08`, `trend_seasonal` + `proportion`
  → `segment_anomalies`), and canonical incidents (`sql/mv/12`,
  `anomalies` → `incidents`). A **cascaded** reactive MV (one sourced from
  another MV's target table, not `ad_events` directly) was found to
  silently stop firing on a large bulk `INSERT` — refreshable sidesteps
  that failure mode entirely by not depending on triggering at all.

All detection work runs in ClickHouse. There is no long-running Node
process, no cron poller, and no outbound webhook — `index.ts`,
`lib/incremental/scheduler.ts`, and `lib/webhook.ts` have been removed.
`lib/clickhouse.ts` is a thin wrapper around the official
[`@clickhouse/client`](https://clickhouse.com/docs/integrations/language-clients/javascript)
Node.js SDK, used only by the local setup/inspection scripts now. Postgres
stores only the dashboard's durable agent analysis output (`incident_analysis`)
— it is not part of anomaly detection or incident qualification.

## Editing the detection logic

**Edit the `.sql` files directly, then re-run `npm run setup:local`** (MVs
use `CREATE MATERIALIZED VIEW IF NOT EXISTS`, so re-running setup is
idempotent, but changing an MV's query means dropping and recreating it —
see `sql/mv/README.md`). To change a threshold, edit
`sql/01_detection_config_seed.sql` and re-run setup — `detection_config` is
read live by the MVs on every firing, no redeploy needed for a threshold-only
change.

The `sql/` files here originated from exploration in a separate repo
(`click-a-thon-2026/InMobi/detection/`, kept as the dataset-exploration
record — see its README for the full method-by-method rationale and
validation walkthrough). **This copy is now the one that runs; edit here
going forward, the two will drift otherwise.**

## Incident qualification

Only adverse (`z < 0`) anomalies from enabled methods are reportable. Every
hourly `trend_seasonal`/`proportion` row qualifies its hour independently; a
completed `day_level` row qualifies all 24 hours of that day independently.
Adjacent or overlapping qualified units are grouped afterward into one
notification window. There is no consecutive-hour or duration requirement.

CTR and render rate retain a 4-sigma evidence threshold at the hourly grain
and 3 sigma at the completed-day grain. They are reporting-only metrics: their
qualified rows stay in the anomaly audit table for secondary correlation and
diagnosis, but `incident_enabled=0` prevents them from opening a page. RPR and
total revenue remain incident-enabled. Positive movements also stay in the
audit table as informational evidence but cannot open an incident.

## Segment-level attribution (`sql/mv/07`-`08`)

Global metrics can hide a real, severe incident that's localized to one
segment but cancels out in the aggregate — confirmed on this dataset:
`native` ad_format eCPM rose ~7% and `interstitial` fell ~9% for 3 straight
days (6/16-6/18), completely invisible in global daily eCPM (flat at 2.475
the whole time) because the two roughly cancel out. `sql/mv/08` runs the
same `trend_seasonal` + `proportion` methods one level deeper, grouped by
`(dimension, segment)` instead of just global, and caught it cleanly (native
z≈+3.8, interstitial z≈-3.2, ~90% of hours across all 3 days).

Swept dimensions: `ad_format`, `category`, `publisher_tier`, `region`,
`country`, `vertical`, `campaign_type` — 46 segment values total, chosen
because they're low-cardinality enough that 5 weeks of trailing history still
gives each `(segment, dow, hod)` cell real statistical power. Deliberately
**not** swept: `app_id` (2000) and `advertiser_id` (500) — too many cells for
the trailing-baseline approach to have any power, and too expensive to
blanket-sweep on every insert. Those stay Stage 2's targeted per-anomaly
drill-down.

Two things don't carry over 1:1 from the global chain, both baked into
`sql/mv/08`:

- Only `trend_seasonal` + `proportion` run per segment, not `day_level` —
  never built per segment (46× the state) even in the old batch design, no
  validated case for it yet. (`cusum` is gone from the pipeline entirely,
  global and segment alike — see above.)
- `vertical`/`campaign_type` only exist on **filled** events (`advertiser_id`
  is empty until a request fills — see `metrics_glossary.md`), so `fill_rate`
  and `rpr` are skipped for just those two dimensions; they don't have a real
  top-of-funnel request denominator to divide by.

Output lands in `inmobi.segment_anomalies` — a **separate table**, not
folded into `anomalies`, because a segment-level row means something
different (localized, not global) and a consumer needs to be able to tell
them apart rather than guess from shape. Both `anomalies` and
`segment_anomalies` ship in the webhook payload
(`anomalies`/`segmentAnomalies` fields, see below).

One gotcha hit and fixed while this was still a batch job, carried forward
into the MV: the `proportion` method is degenerate when a segment's trailing
baseline rate is exactly 0 or 1 (e.g. a low-traffic country with zero clicks
in every trailing week) — `sqrt(p0·(1-p0)/den)` is 0, so `z` comes out
`±inf`. Both `sql/mv/03` (global) and `sql/mv/08` (segment) guard with
`p0 > 0 AND p0 < 1 AND den > 0`; only the segment sweep actually hits this in
practice (sparse per-country cells), global volume never gets that sparse.

## `anomalies`/`segment_anomalies`/`metric_zr_hourly` table semantics

All three are plain `MergeTree`, not `ReplacingMergeTree` — each has exactly
one writer (its refreshable MV: `sql/mv/03`, `sql/mv/08`, `sql/mv/02`
respectively), which fully replaces the table's content every refresh
cycle, so there's nothing to dedupe. **Do not query any of them with
`FINAL`** — ClickHouse Cloud's `SharedMergeTree` rejects `FINAL` outright on
a non-Replacing table (`ILLEGAL_FINAL`), it does not silently no-op.
`anomalies` still functions as an audit trail, just a continuously
recomputed one — it always reflects what qualifies under the **current**
`detection_config`, not whatever config was active when an hour was first
scored. See `sql/mv/README.md` for the full reasoning.

## Repository layout

| Path                               | Purpose                                                           |
| ---------------------------------- | ----------------------------------------------------------------- |
| `sql/00_schema.sql`                | ClickHouse target tables and supporting schema.                   |
| `sql/01_detection_config_seed.sql` | Enabled methods, thresholds, and incident policy.                 |
| `sql/mv/`                          | Reactive and refreshable ClickHouse materialized views.           |
| `sql/incremental/`                 | Local recompute and analysis queries, not a production scheduler. |
| `db/migrations/`                   | Postgres control-plane schema (dashboard agent analysis results). |
| `scripts/`                         | Setup, recompute, migration, and inspection commands.             |
| `docker-compose.yml`               | Local Postgres and ClickStack OpenTelemetry Collector.            |

## Configuration

Create `apps/detection-service/.env.local` with ClickHouse credentials:

```dotenv
CLICKHOUSE_URL=https://your-clickhouse-host:8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=default
```

The scripts use the local Postgres default below unless `DATABASE_URL` is set:

```text
postgres://detection:detection@localhost:55432/detection_registry
```

Keep `.env.local` out of version control. The service has no webhook-related
environment variables.

## Local setup

From `apps/detection-service`:

```sh
# Start only the local database.
docker compose --env-file .env.local up -d postgres

# Create the Postgres tables required by the dashboard.
npm run db:migrate

# Create the ClickHouse schema, detection configuration, and materialized views.
npm run setup:local
```

Confirm Postgres is ready:

```sh
docker compose --env-file .env.local exec -T postgres \
  pg_isready -U detection -d detection_registry
```

## Local operations

| Command                   | Purpose                                                                                                                                                         |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run setup:local`     | Idempotently create the ClickHouse schema, configuration, and materialized views.                                                                               |
| `npm run db:migrate`      | Apply Postgres migrations, including `incident_analysis`.                                                                                                       |
| `npm run recompute:local` | Force every refreshable MV to run now instead of waiting for its schedule. Not destructive — it's the same full-history recompute the schedule would do anyway. |
| `npm run sweep:local`     | Print recent global and segment anomalies plus canonical incidents.                                                                                             |
| `npm run incidents:local` | Print canonical rows from `inmobi.incidents`.                                                                                                                   |
| `npm run check-types`     | Typecheck the TypeScript utilities.                                                                                                                             |

There is deliberately no long-running `start` process: ClickHouse owns the
detection and incident lifecycle.

## Working with the detection logic

Edit SQL directly, then run `npm run setup:local`. Threshold-only changes go
in `sql/01_detection_config_seed.sql`; materialized-view query changes may
require dropping and recreating the affected view as described in
[`sql/mv/README.md`](sql/mv/README.md).

`inmobi.anomalies`, `inmobi.segment_anomalies`, and `inmobi.metric_zr_hourly`
are plain `MergeTree` — each has exactly one writer (its refreshable MV),
which fully replaces the table's content every cycle, so there's nothing to
dedupe. **Never query them with `FINAL`** — ClickHouse Cloud's
`SharedMergeTree` rejects `FINAL` outright on a non-Replacing table
(`ILLEGAL_FINAL`), it does not silently no-op. `inmobi.incidents` is the
canonical reportable-incident table consumed by the dashboard.

## ClickStack collector

The optional local collector accepts OTLP/gRPC on `4317` and OTLP/HTTP on
`4318`, then stores telemetry in the configured ClickHouse service:

```sh
docker compose --env-file .env.local up -d clickstack-otel-collector
```

It is observability infrastructure for Sentinel's web and agent telemetry; it
does not trigger detection or investigation.
