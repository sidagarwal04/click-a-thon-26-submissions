# ADR 0021 — Keep `proj_by_session`, and regularise the DDL that created it

> **Summary:** `proj_by_session` — the session-ordered projection on `ev_raw` that WALKTHROUGH §5
> and ADR 0013 record as "measured and NOT shipped" — has in fact been live on the graded database
> since 2026-08-01 10:12 (system.mutations). Re-measured in a scratch DB on a settled part set: the
> finalizer's windowed derive reads **106,497 → 8,193 rows (13.0×)**, dashboards byte-identical,
> cost +3.38 MiB (+92% of ev_raw). Decision: **keep it**, and fix `sql/60_projection.sql` to name
> no database (ADR 0010 pattern) — the hard-coded `sonyliv.` meant *any* application of that file,
> even `--database scratch`, mutated the graded table. Status: accepted, 2026-08-01.

**Status** Accepted · 2026-08-01 · regularises a deployed-but-undocumented state · see also ADR 0002, ADR 0010, ADR 0013

## Context

ADR 0002 moved `ev_raw`'s sort key to `(toStartOfHour(event_timestamp), platform,
video_session_id, event_timestamp)` — 17.3× better on the dashboard shape, per the official rule
`schema-pk-cardinality-order` (CRITICAL). Its Consequences section named the remedy for the access
pattern it gave up: *"If a 'single session lookup' access pattern ever becomes hot, add a
PROJECTION ordered by video_session_id rather than reverting the key."*

That pattern **is** hot: the incremental finalizer (ADR 0013) and the straggler/late-arrival path
(ADR 0006) fetch every event of a *named* set of sessions, windowed to those sessions' event-time
span. The projection was written (`sql/60_projection.sql`), measured in the H4 worksheet, recorded
as *shelved* ("1.00× for +94% storage" — measured on a shape that full-scanned), then re-measured
by ADR 0013 PHASE 10 at **12.8×** on the finalizer's actual `IN (subquery) + window` shape.
Both ADR 0013 and WALKTHROUGH §5 state it was **not shipped**.

## The discovery this ADR regularises

It *was* shipped. `system.mutations` on the graded database:

```
ADD PROJECTION IF NOT EXISTS proj_by_session (...)   2026-08-01 10:12:11   is_done=1
MATERIALIZE PROJECTION proj_by_session               2026-08-01 10:12:13   is_done=1
```

`system.projection_parts` confirms it is materialized and active: 905,558 rows, **3.42 MiB**.
The H4 measurement session ran its ALTERs directly against `sonyliv` (the file hard-codes
`sonyliv.`), recorded the *decision* as shelved, and never dropped the *object*. Every benchmark
number in `evidence/benchmark/` was captured with it present — harmless there, because none of the
13 shapes reads `ev_raw` — but the deployed schema and the documentation have disagreed all day.

The hard-coding is not cosmetic. `tools/apply-sql.sh --database anything sql/60_projection.sql`
would still have ALTERed + re-MATERIALIZEd the **graded** table — a mutation on the database this
repo forbids writing to. It is the same defect class ADR 0010 fixed in `sql/80_content.sql`, and
the reason `tools/publish-test.sh` PHASE 10 had to issue its ALTER by hand.

## Measurements (scratch DB `sonyliv_q25`, clone of the graded data, settled part set)

Probe = the derivation's own read (`uniqExact(video_session_id), min/max(event_timestamp)`), the
finalizer's scope form (`video_session_id IN (subquery)`), 3 runs each, caches off, Cloud
26.2.1.525. `optimize_use_projections=0` vs `1` on the identical table — same data, same parts.

| shape | without projection | with projection | factor |
|---|---|---|---|
| windowed derive (what `tools/publish.sh` runs) | 106,497 rows / 7.20 MB | **8,193 rows / 614 KB** | **13.0×** |
| session-only `IN` (no time window) | 299,351 rows / 20.1 MB | 38,946 rows / 2.61 MB | 7.7× |
| dashboard hour+platform slice (ADR 0002's shape) | 303,104 rows / 22.0 MB | 303,104 rows / 22.0 MB | unchanged |
| storage, `ev_raw` total | 3.68 MiB | 7.06 MiB (projection 3.38 MiB) | +92% |

This agrees with ADR 0013 PHASE 10 (104,640 → 8,193 on an *unsettled* part set): the win is part-
layout-independent. EXPLAIN attributes it to binary search on the projection's
`(video_session_id, event_timestamp)` key — 1 of 104 granules read for a one-session derive.

## Decision

**Keep the projection**, and make the repo match reality:

1. `sql/60_projection.sql` now **names no database** (ADR 0010 pattern) and documents the measured
   trade in its header. Applying it to a scratch DB was validated end-to-end
   (`tools/apply-sql.sh --database sonyliv_q25` — the graded DB's mutation log did not move).
2. No write to `sonyliv` was made or is needed: the object already exists there and matches the file.

Why keep rather than propose a drop:

- The 13 benchmark shapes never read `ev_raw`; the projection cannot move a graded number.
- The straggler path is exactly what the unseen day stresses; 13× on its read for 3.38 MiB is a
  good trade at any scale we have measured (at 100×, `ev_raw` is 785 MiB — the projection roughly
  doubles raw-event storage; that knob stays a human's call *before* applying it to a 100× table).
- The gate is green **with it deployed**: reconcile PASSED, 17,028 minutes, 0 mismatched, re-run
  after this ADR's measurements.
- Dropping it would itself be a write to the graded database, forbidden to this session.

The reversal path, should storage ever matter, is one statement, run by a human:
`ALTER TABLE ev_raw DROP PROJECTION proj_by_session` (metadata + part cleanup; the base table is
untouched).

## Consequences

- `tools/unseen-run.sh` does **not** apply `sql/60_projection.sql`, so an unseen-day database will
  not carry the projection unless a human applies it — which the fixed file now makes safe. The
  finalizer met its 3.4 s straggler target *without* the projection (ADR 0013), so this is an
  optimisation, not a dependency.
- WALKTHROUGH §5's "not shipped" and ADR 0013's "ships neither" describe the *decision record*,
  not the deployed schema; both predate this discovery. Proposed one-line corrections are listed in
  `evidence/query-performance.md` for their owners (those files are held by other agents today).
- The benchmark bundle's `meta.env`/`runs.tsv` numbers need no re-run: verified via
  `system.query_log` that no benchmark query touches `ev_raw`.
