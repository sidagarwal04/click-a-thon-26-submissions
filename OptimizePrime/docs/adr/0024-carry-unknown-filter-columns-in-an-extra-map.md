# ADR 0024 — Unknown filter columns are announced and carried in an `extra` Map, never dropped

> **Summary:** The judges said new filter columns WILL appear; measured on the pre-0024 loader, a
> new column loaded **silently and was discarded**, and a removed column silently became `''` on
> every row (reordering was safe — mapped by name). Now `tools/load.sh` diffs the incoming header
> before loading a row: NEW columns are announced and carried into `ev_raw.extra`
> `Map(LowCardinality(String), String)`, queryable the same day as `extra['device_type']` with no
> migration and no human awake; MISSING columns refuse unless each is named in `--allow-missing`
> (`event_timestamp`/`video_session_id` can never be defaulted). Measured on all 905,558 rows:
> empty maps cost **32,674 B compressed (+0.48%)**, a populated 2-key map **244,238 B (+3.6%)**,
> load time unchanged (~2.1 s), the 13-column path **fingerprint-identical** to the old loader, and
> the reconcile gate passes on a model built from a new-column file. Tier boundary is explicit: a
> new dim that is a function of an existing key is servable from `cc_minute_delta` today (measured
> 0.2 s, exact); an independent one needs the raw recompute (0.2–1.1 s) or a key change — which
> this ADR does NOT make. Evidence: `evidence/schema-drift/probes.txt` (30 assertions).

**Status** Accepted · 2026-08-02 · owns `tools/load.sh` + `sql/00_schema.sql`; leaves the model's
dimension keys untouched (a new first-class key is a separate decision, deliberately not taken
here). Responds to the judges' brief: *"There will be and can be more new columns for filtering.
Queries should be able to handle those use cases."*

## Context

`tools/load.sh` pinned a hard-coded 13-column `input()` schema and loaded `FORMAT CSVWithNames`.
Probed against a scratch table, the three possible header changes behaved as:

| change in the incoming CSV | pre-0024 behaviour | severity |
|---|---|---|
| new column added mid-header | loads fine, column **silently discarded** | the exact judge scenario, dimension lost |
| known column removed | loads fine, `''` **silently** on every row | dimension silently blank |
| columns reordered | loads fine, mapped by name | safe |

Both failure modes were silent. The unseen day may drop at an hour when nobody is awake, so any
answer that requires a human (or an agent session) in the loop before the data loads is not an
answer to the brief.

## Decision

1. **Detect loudly, before loading a row.** The loader parses the incoming header (python `csv`,
   already a dependency), diffs it against the expected 13 (4 for `content_dim`), and reports:
   NEW columns with where they went, MISSING columns with what it takes to proceed, REORDERED as
   a safe note, and a rename hint when NEW and MISSING appear together. Garbage headers —
   duplicates, names that are not plain identifiers — are refused outright, on the same
   injection-safety grounds as a malformed `--database` name (everything reaches ClickHouse by
   string concatenation).

2. **Carry unknown columns in a catch-all.** `ev_raw` and `content_dim` gain
   `extra Map(LowCardinality(String), String)`. The loader builds the `input()` structure from the
   actual header (known columns keep their parse types, new ones are `String`) and packs the
   leftovers: `map('device_type', device_type, …)`. An unforeseen dimension is queryable the day
   it arrives — `WHERE extra['device_type'] = 'tv'` — with **no migration and no human in the
   loop**, which is the property neither alternative has:
   - *generated `ALTER TABLE ADD COLUMN` per new column*: first-class columns, but a schema
     mutation decided by whatever garbage the day's header happens to contain, applied unattended
     to the graded database. Rejected as the default; the adoption path below keeps it available
     deliberately.
   - *documented refusal*: honest but fails the brief — the dimension is simply lost until someone
     wakes up.

3. **A missing column is a decision, not an empty string.** The load refuses and names the exact
   flag; `--allow-missing app_version` proceeds with the type default and announces the blank
   dimension. `event_timestamp` and `video_session_id` (and `content_id` for `content_dim`) can
   never be defaulted — no interval can be derived without them; no flag overrides that.

4. **Old tables refuse before they truncate.** Loading a new-column file into a pre-0024 table
   fails *before* any `--replace` truncation, printing the one `ALTER TABLE … ADD COLUMN IF NOT
   EXISTS extra …` that adopts it. `sql/00_schema.sql` carries the same ALTER after each CREATE,
   so applying the schema file converges an existing database (metadata-only, instant).

## What it costs — measured, 905,558 rows, local 26.7.1

| cost | measured |
|---|---|
| empty maps (the known 13-column file) | **32,674 B compressed** (+0.48% on a 6.87 MB table); 7.2 MB uncompressed |
| populated, 2 new columns on every row | **244,238 B compressed** (+3.6%) |
| load latency | ~2.1 s before and after — header parse is one `next(csv.reader)` |
| 13-column fidelity | order-independent `cityHash64` fingerprint over all 13 columns **identical** to the pre-0024 loader (`13118056588632894114`); reconcile gate `PASS`, 17,028 minutes, 0 mismatches, on a model built from a file carrying two unknown columns |
| filter on `extra[…]`, raw recompute | 0.2–1.1 s full-file (shipped spec rules; `evidence/schema-drift/worked-example.sql` validates the new-dim series against a platform-derived ground truth on every minute — 3,732 minutes, 0 mismatches) |

The Map subscript reads the whole `extra` column for the day being scanned — there is no skip
index on map keys here. At 100× scale that is ~24 MB compressed extra read per full-file query,
acceptable for an ad hoc dimension, not for a headline one; hence the boundary below.

## The boundary — how far a new dimension goes before the model changes

The serving tier `cc_minute_delta` is keyed `(platform, country, content_id, minute, …4 more)`.
Three cases, in descending order of what you get for free:

1. **Function of an existing key** (probe: `device_type` = a coarsening of `platform`): servable
   from the tier **today** by query-time normalisation (the ADR 0011 pattern) — measured 0.2 s,
   peak 645 exactly equal to the raw recompute. No rebuild, no new key.
2. **Independent of every key** (probe: `network_type`): the tier cannot serve it at any grain —
   its sessions are already aggregated away. The raw recompute over `extra['network_type']` is
   the no-migration path (0.23 s full-file). Fine ad hoc; it re-derives intervals per query.
3. **Promotion to first-class**: `ALTER` a real column on `ev_raw`, backfill from `extra`
   (`UPDATE`-free: `SELECT … extra['x']` into the rebuild), add it to the tier's dims and rebuild
   via `tools/build-model.sh`. That is a **dimension-key change** — other work depends on those
   keys being stable, so this ADR records the path and deliberately does not take it.

## Consequences

- The unseen day can add, drop, or shuffle columns and the load either succeeds with every known
  column intact (proven by fingerprint) and every unknown one queryable, or refuses with the exact
  command that proceeds. Nothing is silent any more.
- `--allow-missing` makes degraded loads possible but *chosen*; the blank dimension is announced.
- Pre-0024 databases (including the graded one, when its owner chooses) converge with one ALTER —
  the loader prints it, and `sql/00_schema.sql` now applies it idempotently.
- `evidence/schema-drift/capture.sh` re-proves all of the above from any later checkout (30
  assertions; pre-change loader fetched from git history at `7c74581`).
- Not changed: the tier keys, `sql/30_build_intervals.sql`, anything under `tests/` — all held by
  other work. The `extra` column rides through the model untouched; reconcile confirms the model
  neither reads nor is perturbed by it.
