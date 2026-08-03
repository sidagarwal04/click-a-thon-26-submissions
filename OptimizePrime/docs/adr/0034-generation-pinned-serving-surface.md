# ADR 0034 — A half-built model must be unservable, not silently servable

> **Summary:** On 2026-08-02 a graded rebuild died at stage 4/6 AFTER the delta insert and left
> `cc_minute_delta` holding 56,146 rows instead of 28,073, serving a peak of **5,834 against a true
> 2,917**; the build's own reconcile sits at the end of the script and never ran, and an external
> audit found it hours later. Fix: every derived tier is stored **generation-keyed** (`generation`
> leading both PARTITION BY and ORDER BY), an append-only `model_generation` table names the
> committed generation, and four pinned base views filter to it. A build writes a new generation and
> commits it **only after its gates pass**, so a build that dies leaves the previous generation
> serving, whole. Reproduced both ways in scratch: today's design serves 5,834; this design serves
> **2,917**, whether the build is killed after staging or runs to completion with the corruption.
> Measured cost on the 13 benchmark shapes: **+0.0% rows read, +16.7% bytes read, +1.4 ms/query
> (literal pin) to +3.5–5.8 ms/query (control-table pointer)**. ADR 0023's rejection of generation
> gating is **overturned on its own terms** — it holds only while `generation` is payload.
> Status: accepted 2026-08-02, **implemented and proven in scratch, not applied to `sonyliv`**.
> Evidence: `evidence/generation-pinning/`. Answers Codex 008 §9 P0.

**Status** Accepted · 2026-08-02 · amends [ADR 0012](0012-rebuild-owns-every-tier-and-the-last-any-leaves.md)
and [ADR 0023](0023-publish-visibility-contract-and-one-block-correction.md); answers
`docs/codex-validation/008-current-main-genericity-and-upstream-closure.md` §9 P0
("generation-pinned publication"). Implemented in `sql/95_generations.sql`,
`tools/generation-install.sh` and `tools/build-generation.sh`; proven in the scratch databases
`gp_ctl` / `gp_pin` on local ClickHouse 26.7.1.1315. **Nothing here has been applied to the graded
database**, and the tooling refuses to.

## Context — the incident, in the only detail that matters

`tools/build-model.sh` runs six stages and then three reconcile gates. Stage 3 truncates
`cc_minute_delta` and re-inserts it; stage 4 rebuilds `cc_hour_agg`. On 2026-08-02 stage 4 died on a
missing `cube_level` column (ADR 0022 added it and did not add a migration step). `set -e` aborted
and returned non-zero — correctly. But by then:

- `cc_minute_delta` held **56,146 rows** — exactly 2 × 28,073 — because two full inserts had landed;
- the delta model is additive, so every served number was **exactly doubled**: peak **5,834**;
- `cc_hour_agg` still held the *previous* build's correct 2,917, so the tiers disagreed;
- the three gates that catch all of this run **after stage 6** and were never reached.

The exit code was right and the database was wrong, and nothing connected the two. That is the
failure class: **a build's blast radius is the thing everyone reads.** Every mitigation added since
(the `REBUILD_GRADED` guard, the `on_exit` trap that prints a warning, `readonly GRADED_DB`) makes
the mistake louder. None of them makes it impossible, because they all leave the build writing
directly into the serving tables.

Codex 008 §9 P0 named the structural answer independently: *"A full rebuild writes a new generation,
reconciles it, then flips the active pointer… rerunning a direct additive INSERT cannot silently
join the active generation; rollback is a pointer change."*

## The obstacle ADR 0023 found, and why it does not apply

ADR 0023 rejected generation gating for the *publisher*, with a measured, correct reason:

> `cc_hour_agg` and `cc_user_minute` are `ReplacingMergeTree(computed_at)` read through FINAL — and
> **FINAL resolves before WHERE**. An uncommitted newer row does not sit invisibly behind a filter:
> it *replaces* the committed row at read time, and the generation filter then discards the
> survivor, leaving *no row* — worse than the lag it was meant to hide.

Reproduced, verbatim, in `evidence/generation-pinning/10-final-vs-where.txt` — a table keyed
`ORDER BY (k)` with `generation` as payload, holding a committed row and an in-flight one, answers
`SELECT … FINAL WHERE generation = 1` with **0 rows**.

That is a property of `generation` being **payload**, not of generation gating. Put it in the sort
key and `(1, k)` and `(2, k)` are different keys, so FINAL has nothing to collapse across. The same
test on `ORDER BY (generation, k)` returns the committed row every time, and the in-flight
generation remains readable by name for inspection. ADR 0023's item 3 is therefore **not a reason to
reject this design** — it is a specification for how to build it. Its items 1 and 2 (every serving
view changes; every read pays a subquery) are real and are costed below.

## Decision

**Serving reads a committed generation. A build never writes a table anyone reads.**

**1 · Every derived tier is generation-keyed.** `sql/95_generations.sql` declares
`gen_session_intervals`, `gen_cc_minute_delta`, `gen_cc_hour_agg`, `gen_cc_user_minute` — each the
canonical definition with `generation UInt32` prepended as the first column, leading the ORDER BY
and leading the PARTITION BY.

- **Leading the ORDER BY** is what makes FINAL safe (above).
- **Leading the PARTITION BY** makes retirement `ALTER TABLE … DROP PARTITION` — metadata only,
  measured **40 ms** on a 1M-row generation — and makes a pinned read prune to exactly one
  generation's parts.
- **The rest of each key is unchanged**, so every prefix every existing view and benchmark query
  was written against still holds, `generation` being pinned to a constant on every read. ADR 0008's
  "one more dimension is a metadata-only ALTER at the tail of the sort key" survives untouched.

**2 · One append-only control table is the pointer.** `model_generation` records one row per state
transition (`building` → `committed` | `abandoned`), never updated — a mutation is asynchronous, and
a commit must be instantaneous and atomic; an INSERT of one row is both. `v_active_generation`
reads the newest generation whose *last* status is `committed`, via `argMax(status, at)` rather than
`max(generation) WHERE status = 'committed'` — the latter cannot express a rollback, because the
`abandoned` row it needs to notice is filtered out before the max is taken.

**3 · Four pinned base views are the entire serving contract.** One per tier:
`SELECT * EXCEPT generation FROM gen_<tier> [FINAL] WHERE generation = (SELECT generation FROM
v_active_generation)`. `tools/generation-install.sh` re-points the canonical names
(`cc_minute_delta`, `session_intervals`, `cc_hour_agg`, `cc_user_minute`) at these. **No downstream
view, query, dashboard tile or benchmark file is edited** — measured: after conversion, `gp_pin`
answers `SELECT max(concurrent) FROM v_concurrency_minute_delta_total` = 2,917 and
`SELECT count() FROM cc_minute_delta` = 28,073, identical to the unconverted `gp_ctl`.

**4 · The build protocol makes the gates unskippable by construction.**
`tools/build-generation.sh`:

| # | phase | what it does | what dying here leaves |
|---|---|---|---|
| 1 | `next` | allocate G, record `building` | previous generation, whole |
| 2 | `build` | **`tools/build-model.sh`, unchanged**, into a disposable database `<db>_bld_gG` | previous generation, whole |
| 3 | `stage` | copy the four tiers into `<db>.gen_*` tagged G — on disk, invisible | previous generation, whole |
| 4 | `verify` | re-run the gates **against generation G as staged**, in the serving database | previous generation, whole |
| 5 | `commit` | **one INSERT** into `model_generation` | committed, or not — one row has no half |
| 6 | `retire` | `DROP PARTITION` for generations older than `KEEP` (default 2); drop the build db | — |

Phase 2 is the existing build script, byte for byte, including all three of its reconcile gates. It
is not made safer; it is made *unable to damage anything*. Phase 4 is the check the real incident
never reached, and here it cannot be skipped, because passing it is the only route to being served.

**5 · Rollback is an insert.** `INSERT INTO model_generation VALUES (G, 'abandoned', …)` and
`v_active_generation` names G−1 again — all four tiers together, in one statement, with no rebuild.
`KEEP=2` is what makes that possible; it is the cost of the guarantee.

## The proof, against the actual incident

`evidence/generation-pinning/40-killed-build.sh`, full transcript in `40-killed-build.txt`. Two
scratch databases hold the same data and the same model (peak 2,917, 28,073 delta rows): `gp_ctl`
built the way the graded database is built today, `gp_pin` through this design.

**Case A — today's design.** Truncate `cc_minute_delta`, run the delta insert twice, then die where
stage 4 died. Stages 5–6 and all three gates never run. One second later a dashboard reads:

```
   gp_ctl   served peak 5834    delta rows 56146   hour-tier peak 2917    intervals 30323
```

The incident, reproduced exactly: **5,834 served against a true 2,917**, 56,146 rows against 28,073,
and the hour tier still on 2,917 so the two tiers disagree — the only visible symptom, and nothing
was watching for it.

**Case B1 — this design, build killed after staging.** `DOUBLE_DELTA=yes KILL_AFTER=stage`. The
build stages 56,146 doubled delta rows as generation 2 and is killed (exit 137) before the verify
phase — the closest analogue of the real crash, which also died after the delta insert and before
the gates. One second later:

```
   generation  status     is_active
     2         building     0
     1         committed    1
   gen_cc_minute_delta:  generation 1 -> 28073 rows,  generation 2 -> 56146 rows
   gp_pin   served peak 2917    delta rows 28073   hour-tier peak 2917    intervals 30323
```

**Case B2 — this design, build runs to completion with the corruption.** The failure mode where
nothing crashes and the model is simply wrong. The verify phase fires:

```
   row counts             FAIL  1 of 4 tiers differ from gp_pin_bld_g3
   delta vs intervals     FAIL  3732 of 17030 minutes disagree, served peak 5834 vs true 2917
   hour vs minute peak    FAIL  hour peak 2917 != minute peak 5834
   == GENERATION 3 FAILED ITS GATES — NOT COMMITTED.
   gp_pin   served peak 2917    delta rows 28073   hour-tier peak 2917    intervals 30323
```

**Verdict.**

| | served peak | delta rows |
|---|---|---|
| today (`gp_ctl`), build killed after the delta insert | **5,834** | 56,146 |
| ADR 0034 (`gp_pin`), killed after staging | **2,917** | 28,073 |
| ADR 0034 (`gp_pin`), run to completion, corrupt | **2,917** | 28,073 |

The corrupt generations stay on disk and stay readable *if asked for by name*. That is deliberate:
they are inspectable and they are not served. Retiring one is
`ALTER TABLE gen_cc_minute_delta DROP PARTITION (2,20260714)` — metadata, per day partition.

## The cost, measured

All 13 benchmark shapes (`evidence/benchmark/b*.sql`), **unmodified**, three ways on the same server
and the same data: `gp_ctl` (today), `gp_pin` with the control-table pointer, `gp_pin` with the
generation baked into the four views as a literal. Caches off, one discarded warm-up, median of 3
server-side `elapsed_ns`. `gp_pin` deliberately holds **three** generations — 2.9× `gp_ctl`'s rows —
which is the pessimistic case. Full table: `evidence/generation-pinning/50-bench-cost.tsv`.

| | total time, 13 queries | rows read | bytes read |
|---|---|---|---|
| today | 78.70 ms | 219,832 | 4,274,245 |
| pinned, control-table pointer | 123.65 ms (**+57.1%**) | 219,897 (**+0.0%**) | 4,987,770 (**+16.7%**) |
| pinned, literal | 97.52 ms (**+23.9%**) | 219,832 (**+0.0%**) | 4,986,925 (**+16.7%**) |

Per query: **+3.46 ms** with the pointer (a second run measured +5.76 ms — the pointer's cost is
noisy because it is evaluated once per tier reference, and the range-window views reference a tier
several times), **+1.45 ms** with the literal (stable across both runs). Worst single query,
pointer: b03 9.26 → 16.61 ms.

Three things that number is made of, separated:

1. **Rows read do not move at all** — +65 rows across 13 queries, and those 65 rows *are* the
   control table (5 per query). Holding three generations costs a pinned reader nothing, because
   `generation` leads the partition key. Confirmed independently in `20-pointer-cost.txt` on a
   3M-row table: literal pin 1.00 M rows / 11.44 MiB, pointer pin 1.00 M / 11.44 MiB, unpinned
   3.00 M / 22.89 MiB. A scalar subquery is evaluated during analysis and substituted as a constant,
   so pruning is identical to a literal.
2. **Bytes read rise 16.7%, and that is the `generation` column.** +713,525 bytes over 219,832 rows
   is 3.2 bytes/row — a `UInt32` per row, read to satisfy the predicate. It is the irreducible
   storage cost of pinning and it is present in both pinned modes.
3. **The rest is the pointer indirection**, ~2 ms/query, entirely avoidable by baking the literal.

**Context for the percentages.** These are 2.6–10 ms local queries; a +1.5–3.5 ms fixed cost is
large as a ratio and small as a number. On the graded Cloud service the same shapes measure 7–135 ms
with the *same query* varying 18.9 / 44.5 / 134.6 ms across three consecutive runs
(`evidence/bench.txt`). The pinning overhead is inside Cloud's own run-to-run variance. It is not
free, and it should not be reported as free.

**Storage.** `KEEP=2` doubles the derived tiers: on this dataset `gp_pin` at three generations holds
90,969 intervals / 5.22 MiB against `gp_ctl`'s 30,323 / 1.74 MiB. The raw tier (`ev_raw`, 905,558
rows) is not duplicated. Two generations is the minimum that makes rollback possible.

**Build time.** The build database is a copy: `INSERT INTO <build>.ev_raw SELECT * FROM <serving>.ev_raw`
re-reads the raw tier once per build. At 100× that is a 90 M-row copy and should be replaced by
pointing the derivation at `<serving>.ev_raw` directly — a cross-database read costs nothing in
ClickHouse. It is left as a copy here so that `tools/build-model.sh` stays byte-for-byte the script
that runs today; noted as the first thing to change before this runs at scale.

**Commit window** (`60-commit-window.txt`, n=10, includes HTTP round trips):

| | duration | window in which tiers disagree |
|---|---|---|
| control-table pointer (1 INSERT) | median 74.5 ms | **none, by construction** |
| baked literal (4 × CREATE OR REPLACE VIEW) | median 79.0 ms | the whole span |

For scale: ADR 0023 measured today's cross-tier disagreement, with no pinning at all, at **3.8 s
(hour tier) to 7.3 s (user tier)**. Either option here is two orders of magnitude better.

**Recommendation:** ship the control-table pointer. It is the one that makes the commit atomic
across all four tiers, which is the property Codex 008 asked for and the reason a view-pin was
preferred over shadow-table renames in the first place. If the ~2 ms indirection ever shows up on
the hot path, the escape hatch is already measured: bake the literal at commit time *in addition to*
the control row, keeping the table as the audit trail and rollback source, and accept a ~79 ms
cross-tier window. Do not do that pre-emptively.

## What this does NOT solve

Stated plainly, because an unlisted limitation is how the next incident gets found by an auditor
instead of by us.

1. **It does not make the incremental publisher atomic.** ADR 0023's mid-publish dip (−87.8% for
   13.6 s) is untouched. Generation pinning is **rebuild-granularity**: `tools/publish.sh` appends
   corrections into the *active* generation and would need a one-line change to write
   `gen_cc_minute_delta` with `generation = (SELECT …)`. Giving each publish its own generation
   would mean copying every tier per minute, which is not affordable. ADR 0023's one-block
   correction remains the right fix for that window and is still not applied.
2. **It does not detect a wrong model that passes its gates.** Pinning turns "wrong and served" into
   "wrong and rejected" only for defects the verify phase can see: doubling, a missing tier, a bad
   copy, cross-tier disagreement. A logic change that is uniformly wrong on both sides of every gate
   commits cleanly. Pinning buys *rollback*, not *detection*; gate quality is still the ceiling.
3. **It does not protect anything upstream of the model.** A bad load into `ev_raw`, a schema drift
   in landing, a wrong dictionary — the generation is built faithfully from whatever is there.
   `ev_raw` has no generation.
4. **It does not give a dashboard a coherent multi-query snapshot.** A single query resolves the
   pointer once and is internally consistent. A dashboard firing eight queries across a commit can
   straddle it: panel 1 on G−1, panel 2 on G. The mitigation is available but not implemented —
   expose the generation and let a client pin it explicitly (`SETTINGS param_generation=…`), which
   is also what "evidence can name the exact generation it certified" needs.
5. **It does not survive an operator with a keyboard.** `TRUNCATE gen_cc_minute_delta`, `DROP
   TABLE`, or a hand-written `INSERT INTO model_generation … 'committed'` all bypass everything
   here. The guards in `tools/generation-install.sh` and `tools/build-generation.sh` (a `readonly`
   graded-database refusal, a non-empty-tier refusal) are the same class of guard that already
   failed once by being the *only* line of defence.
6. **It adds a silent trap of its own, and this is the one to watch.** `SELECT … FROM <normal view>
   FINAL` does **not** propagate FINAL to the view's underlying table, and does not error — it is a
   silent no-op returning un-deduplicated rows (measured: 2 rows / v=30 where the truth is 1 row /
   v=20, `10-final-vs-where.txt` test 3). Every pinned base view over a Replacing tier must
   therefore carry FINAL *itself*. Downstream `FINAL` becomes inert — harmless, verified still
   correct — but it can no longer be relied on. A future pinned base view that forgets FINAL breaks
   every reader beneath it without a single error message.
7. **Conversion is a one-way door for a database.** After `tools/generation-install.sh`, re-applying
   `sql/10_intervals.sql` fails: its `ALTER TABLE cc_minute_delta … MODIFY ORDER BY` cannot run
   against a view, and `tools/apply-sql.sh` with no arguments (which applies every file in `sql/`)
   errors on a converted database. Intended — the tier DDL now lives in `sql/95_generations.sql` —
   but it is a real constraint on any tool that assumes a bulk apply works everywhere.
8. **It has not been run on Cloud, and it has not been run on the graded database.** Every number
   here is local ClickHouse 26.7.1.1315. Cloud is 26.2.1.525 and a Replicated database, where
   `CREATE OR REPLACE VIEW` is a Keeper-coordinated DDL — the control-table pointer avoids relying
   on that, which is a second reason to prefer it, but the claim is untested there. Applying this to
   `sonyliv` means rebuilding its four tiers into the new shape, which is exactly the destructive
   operation the incident came from, and is **an operator decision, not an agent one**.

## Consequences

- `tools/build-model.sh` is unchanged and keeps working exactly as it does today. This design wraps
  it rather than replacing it; the migration is additive at the tooling level even though it is
  destructive at the schema level.
- `sql/95_generations.sql` is safe to apply anywhere — it only CREATEs. The destructive half lives
  in `tools/generation-install.sh`, deliberately outside `sql/`, because `tools/apply-sql.sh`
  applies every file in that directory and a `DROP TABLE cc_minute_delta` there is a graded outage
  waiting for someone to type `TARGET=cloud`.
- ADR 0023's rejection of `generation_id` is superseded **for the rebuild path only**. Its analysis
  was correct for the design it examined; the sort-key placement it did not consider is what changes
  the answer. Its rejection stands unchanged for the publisher, for the reason in limitation 1.
- Codex 008 §9 P0 is answered: generations exist, the pointer is one row, rollback is a pointer
  change, and `model_generation.git_commit` / `gate_verdict` let a piece of evidence name the exact
  generation and gate result it was certified against.
- The scratch databases are disposable: `DROP DATABASE gp_ctl`, `DROP DATABASE gp_pin`,
  `DROP DATABASE gp_probe`.
