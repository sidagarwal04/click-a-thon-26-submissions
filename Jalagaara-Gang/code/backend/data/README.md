# Data layer — tables, purpose, and how to (re)load

Six tables live in ClickHouse Cloud. Four are loaded directly from `InMobi/data/`, two are
built from those four. Schema source of truth: [`schema.sql`](schema.sql).

## Table reference

### `ad_events` — raw fact table
The event stream, unmodified. **9,000,000 rows**, Jun 1 – Jul 5 2026.

| Column | Type | Notes |
|---|---|---|
| `event_time` | DateTime | when the ad request happened |
| `app_id` | LowCardinality(String) | FK → `apps_dim.app_id` |
| `geo_device_id` | LowCardinality(String) | FK → `geo_device_dim.geo_device_id` |
| `advertiser_id` | LowCardinality(String) | FK → `advertisers_dim.advertiser_id`. **Empty on unfilled requests** |
| `ad_format` | LowCardinality(String) | banner / interstitial / native / rewarded / video |
| `is_filled` / `is_impression` / `is_click` | UInt8 | funnel flags, 0 or 1 |
| `revenue` | Float64 | earned on impressions |

Loaded once via `client.raw_insert()` streaming `ad_events.parquet` — never `file()`, which
only reads the ClickHouse *server's* disk, not ours. `ORDER BY (event_time, app_id)`.

### `apps_dim`, `advertisers_dim`, `geo_device_dim` — dimension lookups
Small reference tables. A row in `ad_events` only carries an ID; these tables are how you
turn that ID into a human-meaningful label (join on the shared key).

| Table | Rows | Columns |
|---|---|---|
| `apps_dim` | 2,000 | `app_id`, `category` (gaming/social/...), `publisher_tier` (tier_1/2/3) |
| `advertisers_dim` | 500 | `advertiser_id`, `vertical` (auto/finance/travel/...), `campaign_type` (CPM/CPC/CPI) |
| `geo_device_dim` | 5,000 | `geo_device_id`, `region` (NAM/EU/APAC/LATAM/MEA), `country`, `device_model`, `os_version` |

Loaded from the 3 CSVs the same way as `ad_events` (`raw_insert`, `CSVWithNames` format).

### `events_full` — denormalized fact + all dimensions
**9,000,000 rows.** `ad_events` LEFT JOIN'd against all 3 dimension tables, so every column
from every dimension is already flattened onto each event row. Built once via
`CREATE TABLE ... AS SELECT` — **a one-time snapshot, not a live view** — so it must be
(re)created *after* the 4 base tables are loaded, never before.

Exists so drill-down queries are a single-table `GROUP BY` with no repeated joins in the
recursion — join cost is paid once at load time, not on every query during an investigation.
`ORDER BY (event_time, country, os_version, app_id)`.

### `hourly_summary` — pre-aggregated rollup
**8,710,103 rows.** `events_full` grouped by `toStartOfHour(event_time)` **and all 11
dimensions** (`region, country, os_version, device_model, ad_format, category,
publisher_tier, vertical, campaign_type, app_id, advertiser_id`), with `requests, fills,
impressions, clicks, revenue` pre-summed per group.

Row count is close to the raw table's because dimension cardinality is high — most
hour+dimension-combo groups are only hit by a handful of events. That's expected, not a bug.
`ENGINE = SummingMergeTree`, also a one-time snapshot (same ordering constraint as
`events_full`: must be built after the base tables load).

**Ratios are never pre-stored here** — `fill_rate`, `ctr`, `ecpm`, `rpr` must always be
computed at query time as `sum(x)/sum(y)` on top of this table's raw sums (see
[`metrics.sql`](metrics.sql)). Averaging a pre-computed per-hour ratio across hours would be
mathematically wrong — it silently drops volume-weighting.

## Table relationships

```
apps_dim ─┐
advertisers_dim ─┼─ (joined into) ──▶ events_full ──▶ hourly_summary
geo_device_dim ─┘        ▲
                          │
                      ad_events
```

## How to connect + reload from a clean checkout

1. **Get ClickHouse Cloud credentials** — host/port/user/password from your service's
   Connect panel (console.clickhouse.cloud → your service → Connect / Settings).
2. **Copy `.env.example` → `.env`** at the repo root, fill in `CLICKHOUSE_HOST` (no port or
   `https://` prefix — just the hostname), `CLICKHOUSE_PORT` (`8443`), `CLICKHOUSE_USER`,
   `CLICKHOUSE_PASSWORD`.
3. **Install backend deps**: from `backend/`, `pip install clickhouse-connect fastapi
   uvicorn[standard] pydantic python-dotenv pandas langfuse jsonschema anthropic` (or use
   `uv sync` once a lockfile exists).
4. **Run the load**: from `backend/`, `python -m data.load`. This creates the 4 base tables,
   streams in the parquet + 3 CSVs, then builds `events_full` + `hourly_summary`, then runs
   sanity checks (row count = 9,000,000, `NAM` present not `NA`, zero unfilled rows with a
   non-empty `advertiser_id`).
5. **If tables already exist and only the derived ones need rebuilding** (e.g. after a schema
   tweak to `events_full`/`hourly_summary`), don't rerun the full load — that would duplicate
   the 9M rows. Instead:
   ```python
   from data.client import get_client
   from data.load import run_derived_schema, sanity_check
   client = get_client()
   client.command("DROP TABLE IF EXISTS events_full")
   client.command("DROP TABLE IF EXISTS hourly_summary")
   run_derived_schema(client)
   sanity_check(client)
   ```

## Gotchas hit while building this

- **`file()` table function doesn't work against ClickHouse Cloud** — it reads the
  *server's* local disk, which can't see your machine. Use `client.raw_insert()` to stream
  bytes over HTTP instead.
- **Unaliased qualified columns in `CREATE TABLE ... AS SELECT` keep their qualified name**
  (e.g. `e.app_id` literally becomes a column named `e.app_id`, not `app_id`) — always alias
  explicitly (`e.app_id AS app_id`) when the `ORDER BY` needs to reference it.
- **`clickhouse-connect`'s `{x:DateTime}` parameter binding silently fails to match on raw
  Python `datetime` objects** — pass `datetime.strftime("%Y-%m-%d %H:%M:%S")` strings instead.
- **`RENAME TABLE` is metadata-only** in ClickHouse — safe and instant even on 9M-row tables,
  no need to reload data just to rename something.
