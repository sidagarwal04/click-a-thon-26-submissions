---
name: atlys-ndjson-profiling
description: Profile an Atlys NDJSON events file before designing any ClickHouse DDL — detect the event-type discriminator, union-scan every JSON path across all event types, locate the identity and timestamp paths, flag numeric metric paths and boolean/hot-filter paths for indexing, parse the spec's "Questions the PM will ask" into candidate frequently-used queries/metrics, and rank ORDER BY candidates. Apply on every onboarding so the schema is derived from the file, never assumed.
always-apply: true
---

# Skill: NDJSON Profiling

Drive everything from the file. There is **no hardcoded schema** — profile the input, then
design. Read both the NDJSON and its sibling `spec.md` before writing any DDL.

## Resolve the inputs (via the `filesystem` MCP)

There is **no shell and no cloned repo** in this environment. The spec files are exposed
read-only through the `filesystem` MCP, rooted at `/app/specs`. Read them with the
filesystem MCP tools (`read_file` / `list_directory`) — never a shell path.

```
spec_name    → user answer (Q1)
ndjson_path  = /app/specs/{spec_name}/events.ndjson
spec_md_path = /app/specs/{spec_name}/spec.md
```

If the named spec folder is missing, `list_directory /app/specs` to show what IS available
and stop. The `spec.md` may be absent — handle gracefully (MV derivation then relies on
Q3 + the NDJSON profile only).

## Profile every event type dynamically

1. **Detect the event-type discriminator key** (commonly `event`, `type`, or `eventType`)
   and list its distinct values. This does **not** create multiple tables — there is exactly
   ONE base table. The discriminator becomes the typed path `payload.event`, used in ORDER BY
   and MV filters. If no discriminator exists, the key simply omits it.
2. **Union-scan ALL rows across ALL event types** — collect every JSON path (top-level and
   nested), and for each: value samples, whether it is ever null/absent (paths only some event
   types emit ARE expected), and approximate distinct-value count.
3. **Common identity paths — always present.** `user_id` (high-card) and `application_id`
   (low/medium-card) appear on **every** event. Treat them as guaranteed, non-null typed paths
   available to ORDER BY.
4. **Locate the event's own timestamp path** (e.g. `timestamp`, `ts`, `eventTime`). It becomes
   the last element of ORDER BY.
5. **Rank candidate ORDER BY paths** (see `atlys-schema-design` for the ordering rules), then
   cap the key at **up to 5 columns (don't pad)**: discriminator → optional Q2 frequent dims →
   `user_id` → timestamp. Extra hot filters go to skip indexes, not the key.
6. **Flag numeric metric paths** (amounts, latencies, durations, counts) and which event types
   carry them (e.g. only `express_payment_confirmed` has `payment.*`). These feed the MV
   derivation in `atlys-materialized-views`.
7. **Flag boolean-valued paths** — paths whose samples are only `true`/`false` (or `0`/`1`,
   `"yes"`/`"no"`), e.g. `otp_success`, `eligible`. These are candidates to type as `Bool`/
   `UInt8` and to filter on efficiently (see `atlys-schema-design` indexing).
8. **Flag hot filter paths NOT in the ORDER BY** — paths the PM questions or Q2 filter on that
   don't make the ≤5-column key (e.g. `device_type`, `os`, `geoip_country_code`, a text/id
   field). Note, per path, the filter shape (equality/`IN`, range, or text-search) so
   `atlys-schema-design` can attach the right **data-skipping index**.

## Parse the spec's PM questions into frequently-used queries / metrics

The `spec.md` section **"Questions the PM will ask"** is the primary source of the queries this
spec must serve. **Treat each PM question as a frequently-used query**, and extract from it:

- the **candidate metric** it implies (a count, rate/conversion, percentile, latency, adoption
  share, …),
- the **event pair or event type** involved (e.g. `express_payment_confirmed` ÷
  `express_checkout_shown`),
- the **numerator / denominator paths** where computable,
- the **dimensions** it slices by (`device_type`, `os`, `geoip_country_code`, `destination`, …),
- whether the formula is **clear** or **ambiguous** (needs one confirmation from the user).

Record these as a candidate metric list and hand it to `atlys-materialized-views`, which
confirms ambiguous formulas, decides MV-need, and writes the metrics manifest.

> The Q2 "frequently filtered fields" answer is **optional**. If the user does not supply it,
> derive the frequent filters from the dimensions named across the PM questions plus the
> low-cardinality paths in the profile. Never block onboarding on Q2.

## Output a profile summary before proceeding

```
📋 NDJSON profile: {ndjson_path}
─────────────────────────────────────────────────
✦ Rows scanned          : {N}
✦ Spec.md               : {found / not found}
✦ Event discriminator   : {payload.<key>, or "none"}
✦ Event types (in table): {list of distinct event types — ALL share one base table}
✦ Base table name       : {spec_table}
✦ Union of all paths    : {count} paths across all event types
✦ Timestamp path        : {path chosen for ORDER BY tail}
✦ ORDER BY (≤5 cols)    : {discriminator, frequent dims, user_id, timestamp}
✦ Paths to TYPE in hint : {only ORDER BY / PARTITION BY paths}
✦ Numeric metric paths  : {candidate aggregation targets + which event type carries them}
✦ Boolean paths         : {paths with only true/false samples — candidates for Bool/UInt8}
✦ Skip-index candidates : {hot filter paths NOT in ORDER BY + suggested index type}
✦ PM-question metrics   : {each PM question → candidate metric (clear | AMBIGUOUS-confirm)}
✦ Frequent filters      : {Q2 answer, or "derived from PM-question dimensions"}
✦ All other paths       : absorbed by the untyped `payload` JSON column
─────────────────────────────────────────────────
```

Then hand the profile to `atlys-schema-design` (DDL) and `atlys-materialized-views` (MV
derivation).

## Rules

- **Always** read and profile the NDJSON + `spec.md` before designing — never summarise from
  memory or assume the shape.
- **Always** treat `user_id` (String) and `application_id` (LowCardinality(String)) as present
  on every event and typed for ORDER BY.
- Sparse paths (present on only some event types) are **expected**, not errors — the `payload`
  column absorbs them.
- Do **not** stream raw event rows into your answer — a profile is metadata, not a row dump.
