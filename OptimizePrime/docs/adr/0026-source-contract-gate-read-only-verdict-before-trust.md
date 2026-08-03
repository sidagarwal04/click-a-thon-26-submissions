# ADR 0026 — A read-only source-contract gate reports before anything is trusted

> **Summary:** `tools/validate-source-contract.sh` + `queries/validate_source_contract.sql` assert
> what is true about `ev_raw`/`content_dim` in any database — SELECTs only, changing nothing — and
> print one screen: a FAIL/WARN/INFO table of counts plus a verdict. FAIL = the file is not the
> protocol we modeled, stop; WARN = unusual, proceed with eyes open against the committed baseline
> (`evidence/source-contract/`). The vocabulary contract is `evidence/liveness/vocabulary.tsv`
> (47 pairs, doubts/11) — unknown events fail OPEN in the model, and only this gate can see them.
> Origin: `feat/problem-space-research` (design-bakeoff cherry-pick #1). Status: accepted, 2026-08-02.

**Status** Accepted · 2026-08-02 · runs as step zero of [RUNBOOK_UNSEEN.md](../RUNBOOK_UNSEEN.md)

## Context

`docs/design-bakeoff.md` rejected the `feat/problem-space-research` architecture and voted to
cherry-pick its source-contract acceptance gate — "exactly the fail-closed front door the unseen
day needs. The incumbent has nothing equivalent." That branch's `queries/validate_source_contract.sql`
(10 checks, its ADR 0013) is the origin of this work; the SQL was re-derived against what this repo
has since measured, not merged.

The unseen day is the one moment where a wrong assumption about the *file* costs the whole score:
a new event value silently extends activity on both sides of the reconcile at once (doubts/11), a
missing CSV column silently loads as `''`, a doubled file produces a plausible curve. The 17,028
green minutes of `sql/90_reconcile.sql` cannot see any of this — the gate and the model share the
same vocabulary and the same rows by construction.

## Decision

A **read-only report**, not an acceptance test. The gate never modifies, cleans, rejects or
quarantines a row, and refuses to run if its own query file ever grows a write keyword.

**The severity split is the design.** The unseen-day answer will not be "clean" — it will be
"clean except these four things", and the operator must see the four and decide in under a minute:

- **FAIL** (6 probes) — *this file is not what we think it is*: empty `ev_raw`, timestamps outside
  2020–2035 (epoch-zero / millis-not-divided), epoch-zero `session_start_epoch`, empty
  session/user identity, an `event_type` outside the seven, a missing expected column. Stop
  before the load costs the hour. A gate that FAILs on everything unusual gets bypassed the first
  time it fires under pressure, so FAIL is reserved for protocol breaks alone.
- **WARN** (14 probes) — *unusual; proceed with eyes open*: vocabulary drift against the 47-pair
  contract, reused session ids, events before declared start, future-dated events, end-before-start,
  multiple ends, tied dimensions at one (session, timestamp) — the rarity ADR 0009's vote assumes,
  now measured per file — retry duplicates, `content_id = -1` sentinel collisions (ADR 0022),
  literal `*` dimensions, unresolvable/conflicting `content_dim`, all-empty dimension columns.
- **INFO** (5 rows) — volume, sessions/users, span, `event_type` histogram, distinct dimensions —
  so a truncated or doubled file is visible at a glance against the baseline.

**The baseline is what makes the report interpretable.** The graded file's verdict is committed
(`evidence/source-contract/baseline-sonyliv-2026-08-02.txt`: 0 FAIL, 3 explained WARNs); the
unseen day is read as a *diff* against it, per the three questions in
[evidence/source-contract/README.md](../../evidence/source-contract/README.md). The gate has also
been **seen firing**: a hostile scratch database with one designed violation per probe FAILed both
phases (`selftest-hostile-2026-08-02.txt`).

**Shape is probed before the report.** A missing column would kill the report query with a server
error precisely when the file is most wrong, so the runner checks the 13-column shape in a separate
first query and prints a readable FAIL verdict on its own.

## What the gate does NOT do

Three components touch incoming data and the boundaries are deliberate. `tools/cruel-gen.sh` (T2)
*generates* hostile data; `sql/15_normalise.sql` (T3) *decides treatment* — reject, quarantine,
normalise; this gate *asserts and reports*, changing nothing. Two components both "handling" bad
data is how they end up disagreeing. Likewise the loader's positional CSV-header check (T1,
`tools/load.sh`) owns *source-file* shape — the gate's column probes see only DDL-level drift and
the all-empty-column symptom of a dropped CSV field, and its notes say which owner acts.

It also does not adjudicate semantics: a WARN on tied dimensions or duplicates states rarity on
*this* file; whether the model's treatment (ADR 0009 vote, dedup policy) is right remains the
doubts/ axis.

## The `ingested_at` decision — and what checking it uncovered

The origin branch's clock-skew check compared `event_timestamp` against an `ingested_at` column.
That check is **replaced by a wall-clock probe** (`> now() + 5 min`, WARN): `ingested_at` is not in
the source contract or `sql/00_schema.sql`, and this pipeline does not stream — an ingestion-time
comparison is only meaningful under real streaming ingestion. For rows loaded before such a column
exists, a `DEFAULT now64(3)` is computed at *read* time anyway, so the comparison would degrade to
wall clock regardless.

Verifying that decision uncovered an incident: `sonyliv.ev_raw` **does** carry `ingested_at` today.
`system.query_log` shows `ALTER TABLE sonyliv.ev_raw ADD COLUMN IF NOT EXISTS ingested_at …` at
**2026-08-01 19:16:50**, followed at 19:17:41–42 by `TRUNCATE TABLE sonyliv.session_intervals` and
`sonyliv.cc_minute_delta` — the rejected branch's `materialize.sh --replace` foot-gun the bake-off
warned about (§4), run against the graded database. The data state was rebuilt afterwards
(reconcile PASSED at the 2026-08-02 inventory), but the schema drift persists and
`evidence/graded-inventory/09-ddl-history-sonyliv.txt` predates it. The gate's first real run
caught this on its own — the shape probe is not hypothetical.

## Consequences

- The unseen file cannot *silently* broaden the model's meaning: new vocabulary, new shape, new
  sentinel collisions and volume anomalies are surfaced before any derived number exists, with
  named owners for the response.
- The gate is evidence, not enforcement — the operator can override nothing because there is
  nothing to override; the verdict informs the §5 human decisions in the runbook.
- `evidence/liveness/vocabulary.tsv` is now load-bearing: it is the definition of "unknown".
  A deliberate vocabulary extension must update the TSV in the same commit (doc-self-heal rule).
- The wall-clock future-dating probe WARNs on synthetic rehearsal days by design; the note says so,
  and the baseline diff makes it unambiguous.
- Whether `sonyliv.ev_raw`'s stray `ingested_at` column should be dropped is a graded-DB write and
  therefore **explicitly not this gate's call** — flagged to the operator instead.
