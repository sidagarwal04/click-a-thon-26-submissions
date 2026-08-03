# End-to-End Test Walkthrough: Express Checkout NDJSON

Use this walkthrough to verify the skill executes correctly from an NDJSON file (+ its
sibling `spec.md`) to a PR, producing the **ONE base table per spec** design (single JSON
column named `payload` + `ch_insert_time`) and — only when derivation says so — materialized
views that read from that single table.

---

## Inputs

| Variable | Value |
|---|---|
| `spec_name` | `01_express_checkout` |
| `ndjson_path` | `Atlys/specs/01_express_checkout/events.ndjson` |
| `spec.md` | `Atlys/specs/01_express_checkout/spec.md` (same folder) |
| `ch_database` | `atlys` (default; from `CH_DATABASE`) |
| `spec_table` | `express_checkout` |
| `frequent_filters` (Q2) | `destination`, `application_id` |
| `common_metrics` (Q3) | destination/country funnel counts; p95 payment latency |
| `ttl_days` | `90` |
| ClickHouse Cloud credentials | set via `CH_HOST`, `CH_USER`, `CH_PASSWORD` |

The NDJSON contains **5 event types** in one file; every event carries `user_id`,
`application_id`, `destination`, `geoip_country_code`, `city`, `timestamp`, and the
discriminator `event`:

```json
{"event":"express_checkout_shown","user_id":"u-90321","application_id":"ios-app","destination":"SG","city":"Mumbai","geoip_country_code":"IN","timestamp":"2026-06-08T06:00:00.000Z","shown_amount":42.5,"currency":"SGD"}
{"event":"express_payment_confirmed","user_id":"u-90321","application_id":"ios-app","destination":"SG","city":"Mumbai","geoip_country_code":"IN","timestamp":"2026-06-08T06:11:00.000Z","payment":{"amount":42.5,"latency_ms":180,"currency":"SGD"}}
```

Sample `spec.md` excerpt (drives MV derivation):

```markdown
## Questions the PM will ask
- Does Express lift checkout → success conversion (funnel counts per destination/country)?
- How much faster is Express (payment.latency_ms, p95 per destination)?
```

---

## Step 2 — Expected profile + MV derivation

```
📋 NDJSON profile: Atlys/specs/01_express_checkout/events.ndjson
─────────────────────────────────────────────────
✦ Rows scanned          : 5507
✦ Spec.md               : found
✦ Event discriminator   : payload.event
✦ Event types (in table): express_checkout_shown, express_checkout_selected,
                           saved_method_used, otp_entered, express_payment_confirmed
✦ Base table name       : express_checkout
✦ Union of all paths    : event, id, timestamp, device_type, os, app_version,
                          geoip_country_code, city, client_lib, user_id, application_id,
                          destination, eligible, shown_amount, currency, saved_method_type,
                          otp_attempts, otp_success, payment.amount/currency/latency_ms
✦ Timestamp path        : timestamp
✦ ORDER BY (≤5 cols)    : payload.event, payload.application_id, payload.destination,
                          payload.user_id, payload.timestamp
✦ Paths to TYPE in hint : event, application_id, destination, user_id, timestamp
✦ Numeric metric paths  : payment.amount / payment.latency_ms (express_payment_confirmed only)
✦ All other paths       : absorbed by the untyped `payload` JSON column
─────────────────────────────────────────────────

🧮 MV derivation
─────────────────────────────────────────────────
Signal A (Q3 metrics + spec.md) : funnel counts per destination/country (count MV);
                                  p95 payment latency per destination (quantile MV)
Signal B (NDJSON ingredients)   : metric paths={payment.latency_ms, payment.amount};
                                  dimensions={event, destination, geoip_country_code};
                                  timestamp={timestamp}
Verdict                         : MV NEEDED — destination_daily_funnel_agg (count, all events),
                                  payment_latency_daily_agg (quantile/sum, filtered to confirmed)
─────────────────────────────────────────────────
Proceeding to DDL design (ONE base table, `payload` JSON column + ch_insert_time + MVs).
```

---

## Step 3 — Expected DDL (`Atlys/schemas/01_express_checkout.sql`)

```sql
-- Schema: 01_express_checkout
-- Source NDJSON: Atlys/specs/01_express_checkout/events.ndjson
-- Database: atlys
-- Base table: express_checkout  (ONE table per spec — all event types land here)
-- MVs: destination_daily_funnel_agg, payment_latency_daily_agg
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)

CREATE DATABASE IF NOT EXISTS atlys;

CREATE TABLE IF NOT EXISTS atlys.express_checkout
(
    payload JSON(
        event          LowCardinality(String),
        application_id LowCardinality(String),
        destination    LowCardinality(String),
        user_id        String,
        timestamp      DateTime64(3, 'UTC')
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.application_id, payload.destination, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 16384, ttl_only_drop_parts = 1;

-- ── Materialized views (Step 2d verdict = MV NEEDED) ──────────────────────────

CREATE TABLE IF NOT EXISTS atlys.destination_daily_funnel_agg
(
    day                Date,
    event_type         LowCardinality(String),
    destination        LowCardinality(String),
    geoip_country_code LowCardinality(String),
    event_count        AggregateFunction(count)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (destination, geoip_country_code, event_type, day)
TTL day + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192, ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.destination_daily_funnel_mv
TO atlys.destination_daily_funnel_agg
AS SELECT
    toDate(payload.timestamp)                              AS day,
    COALESCE(CAST(payload.event AS String), '')            AS event_type,
    COALESCE(CAST(payload.destination AS String), '')      AS destination,
    COALESCE(CAST(payload.geoip_country_code AS String), '') AS geoip_country_code,
    countState()                                           AS event_count
FROM atlys.express_checkout
GROUP BY day, event_type, destination, geoip_country_code;

CREATE TABLE IF NOT EXISTS atlys.payment_latency_daily_agg
(
    day                Date,
    destination        LowCardinality(String),
    geoip_country_code LowCardinality(String),
    latency_p95        AggregateFunction(quantile(0.95), UInt32),
    total_amount       AggregateFunction(sum, Float64),
    payment_count      AggregateFunction(count)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (destination, geoip_country_code, day)
TTL day + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192, ttl_only_drop_parts = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.payment_latency_daily_mv
TO atlys.payment_latency_daily_agg
AS SELECT
    toDate(payload.timestamp)                              AS day,
    COALESCE(CAST(payload.destination AS String), '')      AS destination,
    COALESCE(CAST(payload.geoip_country_code AS String), '') AS geoip_country_code,
    quantileState(0.95)(CAST(payload.`payment.latency_ms` AS UInt32)) AS latency_p95,
    sumState(CAST(payload.`payment.amount` AS Float64))    AS total_amount,
    countState()                                           AS payment_count
FROM atlys.express_checkout
WHERE payload.event = 'express_payment_confirmed'
GROUP BY day, destination, geoip_country_code;
```

> `shown_amount`, `otp_attempts`, `payment.amount`, `payment.latency_ms`, etc. are **not**
> typed on the base table — they live in the `payload` column (present only for some event
> types) and are read by the MVs via `payload.\`payment.latency_ms\`` etc.

---

## Step 4 — Expected chdb output

```
  ✅ CREATE DATABASE + base table + MVs
  ✅ INSERT 5 wrapped rows (one per event type)
  ✅ SELECT count() = 5
  ✅ ORDER BY paths (payload.event, payload.application_id, payload.destination, payload.user_id, payload.timestamp) are not NULL
  ✅ ch_insert_time auto-populated

============================================================
✅ BASE TABLE + MVs PASSED
```

Against the full file (5507 rows), the MVs aggregate as:

```
destination_daily_funnel_agg  → per event_type: shown 1650, selected 1007, saved 1007, otp 1007, confirmed 836
payment_latency_daily_agg     → payment_count 836 (confirmed only), p95 latency ≈ 3827 ms
```

---

## Step 5 — Expected cloud smoke test output

```
name                            engine                sorting_key
express_checkout                MergeTree             payload.event, payload.application_id, payload.destination, payload.user_id, payload.timestamp
destination_daily_funnel_agg    AggregatingMergeTree  destination, geoip_country_code, event_type, day
payment_latency_daily_agg       AggregatingMergeTree  destination, geoip_country_code, day

✅ Base table + MVs verified on ClickHouse Cloud
✅ ch_insert_time auto-populates on insert
```

---

## Step 6 — Expected file

```
tillthelastrow/Atlys/schemas/01_express_checkout.sql
```
✅ File exists · `CREATE DATABASE IF NOT EXISTS` present · **exactly one** base table with a
single `payload` JSON column + `ch_insert_time` · ORDER BY has 5 columns (discriminator first,
timestamp last) · MVs read from the base table (payment MV filtered by `payload.event`) · no
Distributed/Replicated/storage_policy · no escaped double-quoted literals.

---

## Step 7 — Expected git commands

```bash
git checkout "$CH_TARGET_BRANCH" && git pull
git checkout -b ch-schema/01_express_checkout-1785230625
git add Atlys/schemas/01_express_checkout.sql
git commit -m "feat(schema): generate ClickHouse DDL from 01_express_checkout ndjson"
git push --set-upstream origin ch-schema/01_express_checkout-1785230625
```

---

## Step 8 — Expected PR

- Title: `feat(schema): ClickHouse DDL for 01_express_checkout`
- Base: `$CH_TARGET_BRANCH`
- Created on `$GH_TARGET_HOST` (derived from `CH_TARGET_REPO`); if `gh` is authed to a
  different/enterprise host, the compare URL is printed instead.
- Body includes: base table + MVs list + derivation verdict, chdb output, cloud test output,
  source NDJSON path.

---

## Negative case (no MV expected)

If `spec.md` only asks "show the raw checkout events for a given session" and the NDJSON has
no numeric metric paths, Step 2d must output:

```
🧮 MV derivation
Verdict : NO MV — spec has only raw-lookup questions; no aggregation over time/dimensions.
```

and the generated `.sql` file contains **only** the single base table (`-- MVs: none`).
```
