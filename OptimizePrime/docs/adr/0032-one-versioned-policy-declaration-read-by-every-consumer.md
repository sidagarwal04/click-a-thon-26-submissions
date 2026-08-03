# ADR 0032 — One versioned policy declaration, read by every consumer

> **Summary:** The constants that decide what our number MEANS — `GAP_S=150`, `TAIL_S=60`,
> `UNCLOSED_PAUSE_TO_RUN_END=1`, `POINT_ACTIVITY_COUNTS=0` — were literals in six files across three
> languages, including the reconcile gate, the reference oracle and both data generators, so **every
> instrument we own for detecting a wrong answer was calibrated with the number under suspicion**.
> They are now declared once in `policy/model.policy`, rendered to SQL as the view `v_model_policy`
> (generated, drift-gated), and read by the model, the gate, the oracle, the fixtures and the
> publisher. **No value changed**: two full local builds before and after agree on peak 2,917, 30,323
> intervals and a `cityHash64` fingerprint of all four derived tiers ([evidence/policy/](../../evidence/policy/README.md)).
> Status: **accepted and applied**, 2026-08-02. Implements ADR 0028 item 4 and Codex validation 008 P1
> "one versioned model policy". This ADR does **not** decide any value — see ADR 0028 for that.

**Status** Accepted · 2026-08-02 · implements [ADR 0028](0028-fitted-parameters-are-declared-inputs-not-derived-per-run.md)
item 4 · evidence [evidence/policy/](../../evidence/policy/README.md) · inventory
[docs/DYNAMIC_PARAMS.md](../DYNAMIC_PARAMS.md) · sensitivity [evidence/params/](../../evidence/params/README.md)

## Context

Two independent reviews landed on the same gap.

[Codex validation 008](../codex-validation/008-current-main-genericity-and-upstream-closure.md) §9 P1:
*"Create one declared policy source … Build SQL, reconcile SQL, publisher templates, golden
generators, and result metadata must all name that version."*

[docs/DYNAMIC_PARAMS.md](../DYNAMIC_PARAMS.md) §4, measured rather than asserted:

> `GAP_S` and `TAIL_S` are written in **six places** across three languages, in **three different
> encodings** (`150`/`60`, `+241`, `INTERVAL 300 SECOND`) — and the model, the gate, the reference
> interpreter and both data generators all share the fitted value. **A mis-fitted `GAP_S` goes green
> on the reconcile gate, green on the property suite, and green on the scale test, simultaneously and
> by construction.**

### What this ADR is NOT

It is not adaptivity. ADR 0028 already rejected deriving these per run on three measured grounds and
that decision stands: the derivation rule is *less stable than the constant* (p99 swings 3.4× on
whether 55.75% same-second pairs count as arrivals), a derived parameter makes two runs incomparable
under fixed judge spot-check semantics, and `arraySplit` needs the parameter before the distribution
that would produce it exists, so it costs a second full pass — ~6.5 GiB of extra reads at 100×.

It is also not a retune. The measured sensitivity says `GAP_S` sits on a flat region (±20% → 10
viewers, 0.34%) while `TAIL_S` is a straight ramp at +2.41 viewers per tail-second, 7.2× more elastic.
Both keep their shipped values here. What changes is their **status**: from buried literals to one
declaration that an answer can be traced to.

## Decision

### 1 · `policy/model.policy` is the declaration

Plain `KEY=VALUE`, so it is `.`-sourceable by POSIX shell with no parser at all, with a `#:` line
above each key carrying the SQL type and a note. Thirteen keys in two tiers: `model` (moves the
answer) and `publish` (moves safety and freshness, never the answer).

### 2 · `sql/01_policy.sql` is generated from it, and drift is a gate

`tools/policy.sh gen` renders two views. `v_model_policy` is **one row, wide** — `gap_s`, `tail_s`,
… — plus `policy_version` and a `policy_hash`. `v_model_policy_kv` is the long form for humans and
evidence, and it is derived FROM the wide view, so a value exists exactly once even inside the
generated file.

`tools/policy.sh check` regenerates and diffs; a hand-edited `sql/01_policy.sql` fails
([evidence/policy/](../../evidence/policy/README.md) §2 C4). It runs as the `policy` suite in
`tools/test-all.sh` and at stage 0/6 of `tools/build-model.sh`, which refuses to build on a stale
rendering.

### 3 · Consumers read the declaration, in whichever of the three languages they live in

| consumer | before | after |
|---|---|---|
| `sql/30_build_intervals.sql` | `150 AS GAP_S` ×4 | `(SELECT gap_s FROM v_model_policy) AS GAP_S` ×4 |
| `sql/90_reconcile.sql` (the gate) | its own copy of all four | the same four scalar subqueries |
| `tools/reference_interpreter.py` (the oracle) | `GAP_S = 150` | `policy_reader.get_int("GAP_S")` |
| `tools/golden-gen.sh` | a copy + a regex scraping `sql/30` | `policy_reader`, and a structural assertion that `sql/30` still reads the view |
| `tools/cruel-gen.sh` | `GAP_S, TAIL_S = 150, 60` | `policy_reader` |
| `tools/scale-load.sql`, `tools/timespan-gen.sh` | hardcoded `150 +` | `(SELECT gap_s FROM v_model_policy) AS GAP_S` |
| `tools/publish.sh` | `:-5`, `:-900`, `:-60`, `:-2` | `:-$(tools/policy.sh get …)`; env override still wins |
| `tools/publish.sh` covers | `+241`, `+7201`, `INTERVAL 300 SECOND` | declared `PUBLISH_*_COVER_S`, asserted `>= TAIL_S + 60` |
| `sql/12_publish.sql` lag view | `604800` ×3, `INTERVAL 60 SECOND` | derived from `queue_ttl_days` / `publish_lease_ttl_s` |

Three readers, one file: SQL through the generated view, shell through `tools/policy.sh`, Python
through `tools/policy_reader.py`. The two hash implementations are cross-checked — both produce
`e965954b23d4` for v1.

### 4 · A view, not a table and not a UDF

- **Not a key/value table.** A missing row resolves to a default, so a database that never got the
  policy would build with `GAP_S = 0` and say nothing. A missing *column* on a *view* is a query
  error. Fail loud beats fail plausible, and this repo has already been burned by plausible.
- **Not a SQL UDF.** ClickHouse SQL UDFs are **server-wide**. Applying a scratch policy on the Cloud
  service would have silently redefined the graded database's semantics. A view is per-database.
- **A view, so applying it is non-destructive.** `CREATE OR REPLACE VIEW` only: no data, no `DROP`,
  no `TRUNCATE`. It passes `apply-sql.sh`'s graded-destructive scanner without an override, which
  matters because the graded database needs it before the next build there.

### 5 · Declared-and-verified where injection is impossible

A ClickHouse `TTL` must be a deterministic expression over the table's own columns; it cannot read
another relation. So `sql/12_publish.sql`'s three 7-day queue TTLs keep their literal, and
`tools/policy.sh check` asserts the file carries exactly three `INTERVAL <QUEUE_TTL_DAYS> DAY` TTLs
and no bare `604800` anywhere else. Everything in that file that *can* read the view — the retention
columns, the lease-liveness window — now does.

### 6 · The version is stamped into the answer

`v_model_policy` carries `policy_version` (bumped by hand) and `policy_hash` (sha256 of the sorted
`KEY=VALUE` canonical form, first 12 hex — impossible to forget). The gate's own SUMMARY row now ends
with `policy=v1/e965954b23d4`, and `evidence/reconcile.txt` records both what the **tree** declares
and what the **database** was built with, because those can differ and that difference is exactly the
"someone forgot to apply it" failure.

## Consequences

**A policy change is one edit.** `POINT_ACTIVITY_COUNTS` 0 → 1 was a six-file change with a comment
in `sql/30` telling you to remember `sql/90`. It is now `policy/model.policy` plus
`tools/policy.sh gen`; the gate, the oracle and both generators follow.

**The gate is independent again on everything except the parameter.** ADR 0028's framing was right:
sharing the *constant* is correct, sharing the *implementation* is not. The gate still re-derives
truth from `ev_raw` with window functions against the model's `arraySplit`, and the divergence
tripwires still fire — measured, not assumed: a model built at `GAP_S=180` served under a 150 policy
gives 102 mismatched minutes, `max_abs_diff` 14.

**The circularity is not gone; it is now a single visible fact.** Every instrument still shares one
value. What changed is that it is *one* value with a name and a version instead of six numbers that
happened to agree, so "the fixtures and the model use the same GAP_S" is now a property you can read
off the declaration rather than a discovery you make by grepping. Detecting a *mis-fit* still needs
the sensitivity sweep (evidence/params/) and mentor answers, not this ADR.

**The publisher's silent staleness is now loud.** `PUBLISH_MINUTE_COVER_S >= TAIL_S + 60` is asserted.
Before, raising `TAIL_S` above 240 under-covered the touched-minute window and left `cc_user_minute`
buckets stale with no error — a latent cross-file break DYNAMIC_PARAMS §A2 found and nothing enforced.

**The graded database needs one apply.** `TARGET=cloud tools/apply-sql.sh --database sonyliv
sql/01_policy.sql` before the next build there. Not done in this change: this branch does not write to
`sonyliv`. Until it lands, `sql/30` and `sql/90` fail there with `Unknown table expression identifier
'v_model_policy'` — loudly, which is the intended failure mode, not a silent wrong answer.

**A per-query cost that measures as zero.** Four scalar subqueries over a one-row view fold to
constants. Two full builds, before and after, on 905,558 rows: 2.7 s vs 4.8 s wall for the whole
six-stage scratch build, inside run-to-run noise on a shared box, and every output byte identical.

## What was deliberately NOT centralised

- **Physical/schema constants** (Tier B in DYNAMIC_PARAMS): `ORDER BY (toStartOfHour(ts), platform,
  …)`, `PARTITION BY toYYYYMMDD(…)`, `bloom_filter(0.01)`, `index_granularity`,
  `min_bytes_for_wide_part`. They cost latency and bytes, never correctness; they live in `CREATE
  TABLE` where nothing can read a view; and changing one requires a schema migration anyway, so a
  declaration would be a second place to edit rather than the only one.
- **The window frames `240 / 840 / 3540 PRECEDING`** in `sql/85_windows.sql`. These are *defined by
  the problem* — `(N×60)−60` because `RANGE` is inclusive of the current row — not fitted. Declaring
  them would invite tuning something that is arithmetic.
- **The 12 generator constants in `tools/scale-load.sql`** (`BURST_MEAN`, `SESS_MEDIAN`, `P_PAUSE`,
  …). They are fitted to this file's *shape*, not to the model's semantics, and they belong to the
  fixture rather than the answer. Only the one that is a model constant in disguise — the hardcoded
  gap threshold — was pulled into the declaration.
- **`tools/publish.sh`'s environment overrides.** `PUBLISH_SETTLE_S=…` from the environment still
  wins over the declaration. An operator turning a knob at 3am should not have to edit and regenerate
  a file; the declaration supplies the *default*, which is what "declared" needs to mean for an
  operational constant.
- **`PUBLISH_LEASE_TTL_S` remains fixed.** ADR 0028 item 6 argues it *should* adapt to measured phase
  duration — at 100× a phase can exceed 60 s and the lease expires under a live publisher, the exact
  failure it exists to prevent. That is a behaviour change to the publisher, not a config refactor,
  and it is out of scope here. Declaring it at least puts the number where the argument can be read.
