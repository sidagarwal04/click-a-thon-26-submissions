# Minute serving tier — additive only

**Status:** reviewed and rescoped. Not applied. No schema changes made.
**Scope:** database `sonyliv`. Additive only — nothing is deleted, rebuilt, or migrated.
**Clock:** code freeze 12:00 IST Sun 2 Aug 2026, no extensions. Written at 04:41 IST.

> **This was a consolidation plan. It is not one any more.**
> The review kept its findings and inverted its scope. Original premise: delete
> `concurrency_day_anchor` and `concurrency_bucket_net`, rebuild `concurrency_deltas`, and
> take the read path from 26ms to 1-2ms. Two problems. Both deletions turned out to be
> unsafe (§2). And no judging axis distinguishes 26ms from 2ms, while the **mandatory**
> ClickStack/LibreChat integration sits unimplemented with ~7h to freeze.
>
> **The minute table still gets built — for a different reason.** A flat one-table read
> surface is what makes a LibreChat + ClickHouse MCP text-to-SQL layer answerable, and that
> is a scored deliverable. Latency is a side effect, not the justification.

---

## 1. What this builds

One new table, `concurrency_minute_versions`, populated from `active_intervals`. Nothing else
changes. Serving reads may move to it; the existing deltas + bucket_net + day_anchor chain stays
exactly as it is and keeps working.

```
active_intervals ─┬─► concurrency_deltas ──► bucket_net ──► day_anchor   [UNCHANGED]
                  │
                  └─► concurrency_minute_versions  [NEW]  ──► LibreChat / MCP
                        dense minutes, no cumsum at read
```

---

## 2. Why the deletions were dropped

### `concurrency_day_anchor` — keep it

The original claim was "structurally dead, all 430,584 rows are zero." The rows *are* all zero.
The reason given was wrong: it cited `docs/DESIGN.md` ("intervals are split at day boundaries"),
which is the **legacy non-authoritative draft**. `011_build_active_intervals.sql` contains no
splitting logic, and `010_active_intervals.sql:44-49` argues the opposite:

```
-- stage 02 needs intervals that OVERLAP a service day ... a 43-hour session
-- starting on the 24th still contributes to the 26th.
```

Zero intervals cross midnight because **88% of this extract sits in a 2-hour window at 10:00 UTC**,
nowhere near midnight. Coincidence, not invariant. A 2-hour interval starting 23:30 on a match
night crosses. The anchor is **untested, not dead** — its code path has never produced a non-zero
value, so nobody knows whether it works.

### `concurrency_bucket_net` — keep it

It is `day_anchor`'s only producer (`022_populate_serving.sql:187,212`). Keeping the anchor keeps
this too.

### `concurrency_deltas` mask drop — deferred

Mask 12 is genuinely redundant (`video_type` is functionally determined by `content_id`: 33,464
titles, **zero** with more than one video_type; mask 12 vs mask 4 is **0 mismatches across 63,881
rows**). But removing it means rebuilding a SummingMergeTree, and a re-run **silently doubles the
peak while every balance invariant still passes** (`022:102`, and `CLAUDE.md:105` says this already
cost a day). Not worth it with hours left. See §7.

**Mask 15 must NOT be dropped** — an earlier draft said it could. Mask 15 minus `video_type` is
mask **7**, which is *not* materialized. Mask 15 ≡ mask 5 only while `country` has one value, and
`TODOS.md` names mask 15 as the finest-grain donor for re-deriving unmaterialized masks.

---

## 3. The table

Adopts `solution/sql/00_schema.sql:510` rather than inventing a parallel one — it already carries
`minute_peak`, `active_entity_ms`, `ending_concurrency`, and the `entity` column that `DECISIONS.md`
D4 commits to for user-level concurrency. **Two corrections to that definition:**

```sql
CREATE TABLE IF NOT EXISTS sonyliv.concurrency_minute_versions
(
    generation            UInt64,
    policy_version        LowCardinality(String),
    pipeline_run_id       UUID,
    source_delta_snapshot UInt128,
    entity                Enum8('session' = 1, 'user' = 2),
    rollup_mask           UInt16,
    service_date          Date,
    minute_start          DateTime64(3, 'UTC'),
    platform              LowCardinality(String),
    country               LowCardinality(String),
    video_type            LowCardinality(String),
    content_id            Int64,          -- CORRECTED: Int32 in 00_schema.sql
    minute_peak           UInt64,
    active_entity_ms      UInt64,
    ending_concurrency    UInt64,
    source_boundary_points UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(service_date)
ORDER BY (generation, policy_version, pipeline_run_id, source_delta_snapshot,
          entity, rollup_mask, service_date, platform, country, content_id, video_type, minute_start)
SETTINGS non_replicated_deduplication_window = 1000,
         replicated_deduplication_window = 1000,
         replicated_deduplication_window_seconds = 2592000;

ALTER TABLE sonyliv.concurrency_minute_versions
  MODIFY SETTING non_replicated_deduplication_window = 1000,
                 replicated_deduplication_window = 1000,
                 replicated_deduplication_window_seconds = 2592000;
```

**`content_id Int64`, not `Int32`.** Max observed id is 2,078,177,474 — **96.8% of Int32 max**, and
the catalogue carries a negative id (`-987654322`) stored unsigned upstream.
`ingest/sql/001_content.sql:24-31` documents this by name. Int32 has 3.2% headroom before the
unseen day silently corrupts the join key.

**The `SETTINGS` block and its `ALTER` are mandatory**, not optional — `CLAUDE.md:98`: *"Every new
MergeTree table in this project must carry all three settings"*, because `CREATE TABLE IF NOT
EXISTS` is a no-op against an existing table and the correction would never arrive.

**`generation` is first in the ORDER BY and this table is plain `MergeTree`, not Replacing.** So
`WHERE generation = {g}` returns *only* rows written at generation g. Corrections must therefore
write a **complete** generation, never a sparse patch — a sparse correction makes every uncorrected
minute vanish from the answer. Reads pin a generation; no `FINAL`, no dedup at read.

---

## 4. The producer — two sources, one row

Neither source alone is sufficient. This was missed until review:

| Column | Source | Why |
|---|---|---|
| `active_entity_ms` | `active_intervals`, dense | An interval 10:02→10:47 contributes to all 46 minutes |
| `ending_concurrency` | `active_intervals`, dense | Level at the minute's end |
| `minute_peak` | **boundary sweep over `concurrency_deltas`** | Max *instantaneous* level inside the minute; containment cannot give this |
| `source_boundary_points` | boundary sweep | Provenance / audit |

**Dense, not sparse.** Building minute rows only where a boundary falls would omit **14,226
minutes where concurrency was greater than zero** (measured, mask 0; worst gap **9,823 consecutive
minutes**). `max(minute_peak)` survives that — the level only changes at boundaries, so the peak is
always attained at one. **`sum(active_entity_ms)` does not**, and the time-weighted average would be
badly under-reported with no invariant failing.

Sizing, measured from `active_intervals` (unclipped): mask 0 → 3,662 rows, mask 1 → 5,073,
mask 4 → 73,035, mask 5 → 85,553, mask 8 → 4,187, mask 9 → 6,272, mask 15 → 85,553.
**~272K rows per clip variant, ~544K both** — smaller than the 1,274,172-row `concurrency_deltas` it
sits alongside.

---

## 5. The read

```sql
SELECT max(minute_peak)                                                   AS peak_concurrency,
       sum(active_entity_ms) / (dateDiff('second', {from}, {to}) * 1000.0) AS avg_concurrency
FROM sonyliv.concurrency_minute_versions
WHERE generation = {g} AND policy_version = {pv} AND pipeline_run_id = {run}
  AND source_delta_snapshot = {snap} AND entity = 'session'
  AND rollup_mask = {mask} AND platform = {platform}
  AND minute_start >= {from} AND minute_start < {to};
```

One range scan, `max()` and `sum()`, no window function. ~3,662 rows for a global query against
73,728 today.

> **Partial-minute edges.** `minute_start >= {from} AND < {to}` truncates to minute boundaries. For a
> range not minute-aligned, the edge minute's `minute_peak` may have occurred *outside* the window
> and `sum(active_entity_ms)` over-counts the same way. Minute-aligned ranges only; fall back to the
> delta path otherwise. Enforce with a `throwIf`, as `32_dashboard_queries.sql` already does.

**Free correctness win, two lines.** The same functional dependency that makes mask 12 ≡ mask 4
makes **mask 13 ≡ mask 5**. An alias view answers an unmaterialized mask at zero cost. Masks 6, 7,
10, 11, 14 stay genuinely unanswerable — `TODOS.md`: peaks do not sum.

---

## 6. Verification — C4 is the gate

| # | Check | Expected | Gating |
|---|---|---|---|
| **C4** | `sum(active_entity_ms)` vs interval durations clipped to range | equal within rounding | **YES — must throw** |
| C1 | `max(minute_peak)`, mask 0, full span | 2,305 | yes |
| C2 | `ending_concurrency` at 10:55 | 2,285 | yes |
| C3 | Per-minute series vs the existing delta path, all masks | 0 mismatched minutes | yes |
| C9 | **Doubling check** — re-run the producer, assert peak unchanged | 2,305, not 4,610 | **YES** |
| C10 | **Midnight crossing** — synthetic interval 23:30→00:30, assert both days correct | non-zero anchor produced | **YES** |
| C7 | Every combo closes to net zero | 0 of 15,378 non-closing | no — blind to a scalar multiple |

**C4 is the only reference-free conservation check** — it compares the new table against
`active_intervals` rather than against a hardcoded number, so it is the one that still works on the
unseen day. C1 and C2 are tuning-day constants and are worthless once the data changes.
C7 cannot detect a doubled curve: doubling both sides keeps the balance.

*(The earlier C5 row-count check asserted ~121,558 sparse rows. Dense is ~272K per variant. That
check would have failed on a correct build — removed.)*

---

## 7. NOT in scope

| Deferred | Why |
|---|---|
| Deleting `concurrency_day_anchor` | Not dead, untested. §2 |
| Deleting `concurrency_bucket_net` | Produces the anchor. §2 |
| Dropping rollup mask 12 | Needs a SummingMergeTree rebuild; silent-doubling risk, no time |
| `PARTITION BY` on the existing serving tables | Same rebuild, same risk |
| `policy_version` bump / migration | Only needed for the mask change |
| Merging `solution/` and `pipeline/` | Real, large, out of scope |
| **ClickStack / LibreChat** | **NOT deferred — this is the next task and it is mandatory** |

## 8. What already exists

| Thing | Reused or rebuilt |
|---|---|
| `concurrency_minute_versions` (`00_schema.sql:510`) | **Reused**, with `content_id` and `SETTINGS` corrected |
| `active_intervals` | Reused as the dense source — already the agreed source of truth |
| `concurrency_deltas` | Reused for the `minute_peak` sweep; not modified |
| Generation pinning (`32_dashboard_queries.sql`) | Reused, including the `throwIf` range guard |
| The "minutes" stage | Already named in `TODOS.md`'s target runbook: `load → intervals → deltas → minutes → benchmark` |

## 9. Failure modes

| Path | Failure | Test? | Handled? | Visible? |
|---|---|---|---|---|
| Producer re-run | Peak doubles, average doubles | C9 | policy_version / generation | **silent without C9** |
| Sparse build | `active_entity_ms` under-counts | C4 | dense by construction | **silent without C4** |
| Interval crosses midnight | Anchor non-zero, path never exercised | C10 | anchor kept | **silent without C10** |
| `content_id` > Int32 max | Join key corrupts | — | Int64 | silent — **fixed by type** |
| Non-aligned range | Peak from outside the window | — | `throwIf` | loud |
| Sparse correction generation | Uncorrected minutes vanish | — | write full generations | **silent — write the rule down** |

Three critical gaps, all closed by C4, C9, C10 being gating.

## 10. Implementation Tasks

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — schema — create `concurrency_minute_versions` with `content_id Int64` and the three dedup settings + `ALTER`
  - Surfaced by: outside voice — `00_schema.sql:523` Int32 vs `ingest/sql/001_content.sql:24-31`; `CLAUDE.md:98`
  - Verify: `SHOW CREATE TABLE`; assert Int64 and all three settings present
- [ ] **T2 (P1, human: ~3h / CC: ~30min)** — producer — dense fill from `active_intervals` + `minute_peak` sweep from `concurrency_deltas`
  - Surfaced by: Test review — 14,226 minutes missing where level > 0
  - Verify: C4 (gating), C1, C2, C3
- [ ] **T3 (P1, human: ~1h / CC: ~10min)** — verification — make C4, C9, C10 gating and throwing
  - Surfaced by: outside voice — C4 is the only reference-free check and was not gating
- [ ] **T4 (P3, human: ~15min / CC: ~3min)** — serving — alias view for mask 13 ≡ mask 5
  - Surfaced by: outside voice — free correctness win from the same functional dependency

_No new tasks from Performance review._

## 11. Parallelization

Sequential. T1 → T2 → T3 all touch `pipeline/sql/` and each depends on the previous. T4 is
independent and can run in any lane. Not worth a worktree split at this size.

---

*Measured 2026-08-02 against ClickHouse 26.2.1.525, database `sonyliv`, read-only over HTTPS.*

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES_FOUND → RESOLVED | 6 issues, 3 critical gaps, all folded |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**CROSS-MODEL:** Outside voice (Claude subagent — Codex not installed) raised 10 findings. Eight
confirmed and folded: `content_id Int32`, missing dedup `SETTINGS`, generation-first ORDER BY vs the
correction model, `minute_peak` unobtainable from containment alone, `sum(active_ms)` not
duplication-safe, C4 not gating, C5 wrong by design, mask 13 ≡ 5. The tenth — that the plan itself
was miscalibrated against a 7-hour clock with a mandatory integration at zero — was accepted and
inverted the plan's scope from consolidation to additive-only. My review had reviewed the plan on its
merits and never questioned whether it should exist.

**VERDICT:** ENG CLEARED — additive-only scope, 3 critical gaps closed by gating checks C4/C9/C10.
Ship T1-T3, then pivot to the mandatory ClickStack/LibreChat integration and the submission
checklist (team name still `TBD`).

NO UNRESOLVED DECISIONS
