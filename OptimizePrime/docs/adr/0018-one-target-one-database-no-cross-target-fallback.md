# ADR 0018 — One target, one database: no cross-target fallback, no server default

> **Summary:** Three layers answered "which database?" three ways. Go read `CH_DATABASE` — the
> graded Cloud database — even for local work, so `sonyliv verify -target local` 404ed; `tools/ch`
> sent no database at all locally and inherited the server default; and the deployed local schema
> had drifted (`uniq` vs `uniqExact`, `UInt64` vs `Int64` deltas) because `IF NOT EXISTS` never
> migrates. Decision: **each target owns its variables — cloud = `CH_HOST`+`CH_DATABASE`, local =
> `CH_LOCAL_URL`+`CH_DATABASE_LOCAL` — both always sent explicitly, environment beats `.env`,
> missing config dies at startup.** Drift vs intent is tabulated below; the column-diff found 4
> drifted columns, all rebuilt; **0 remain** (`evidence/target-resolution.txt`).

**Status:** accepted · **Date:** 2026-08-01
**Evidence:** [`evidence/target-resolution.txt`](../../evidence/target-resolution.txt)
**Extends** [ADR 0005](0005-heartbeat-lease-semantics.md) (which mandated `uniqExact` — the drift
this ADR repairs was a stale deployment of exactly that decision) and the bug-11 database-resolution
work in `tools/apply-sql.sh` / `tools/load.sh` (docs/SESSION-2026-08-01.md §4), which this ADR
promotes from a two-script fix to the rule every layer follows.

## Context

The same intent — "run this against local" — resolved to three different answers depending on which
layer executed it:

| Layer | Host came from | Database came from | Failure mode |
|---|---|---|---|
| Go `internal/config` | `CH_LOCAL_URL` ✓ | **`CH_DATABASE`** (= `sonyliv`, the graded Cloud DB), else literal `default` | `verify -target local` 404ed looking for `sonyliv` on localhost |
| `tools/ch` (local) | `CH_LOCAL_URL` ✓ | **nothing sent** → server default for the `app` user | worked by coincidence; broke the moment the default changed, and broke silently from any CWD other than repo root (it read `./.env`) |
| `tools/apply-sql.sh`, `tools/load.sh` | per-target ✓ | `CH_DATABASE_LOCAL` chain (bug-11 fix) — but `.env` did not define it, and `.env.example` did not mention it | fell through to `CH_DATABASE` |
| deployed local schema | — | — | `uniq`/`UInt64` where Cloud has `uniqExact`/`Int64`: a local check can disagree with Cloud for reasons unrelated to the change under test |

The stakes are not hypothetical: earlier today a mistargeted model build left the **graded**
database serving two model generations for ~2 hours. This repo's whole scoring path depends on
"which database did that command touch" having exactly one answer.

## Decision

**Resolution rule, every layer:**

```
TARGET=cloud   host CH_HOST:CH_PORT    database  $CH_DATABASE        > .env CH_DATABASE        > die
TARGET=local   host CH_LOCAL_URL       database  $CH_DATABASE_LOCAL  > .env CH_DATABASE_LOCAL  > die
```

1. **A target only reads its own variables.** `CH_DATABASE` names the graded Cloud database and is
   invisible to the local target — pinned by `TestLoadLocalNeverReadsCloudDatabase`.
2. **The database is always sent explicitly.** No query rides the server's default database.
3. **The environment beats `.env`** (capture before `set -a && . .env`, which otherwise overwrites).
4. **`TARGET` is read from the environment on every layer, and an unrecognised value dies.**
   Added 2026-08-01 after the first cut of this ADR shipped: `tools/ch` assigned `TARGET=local`
   unconditionally and switched to Cloud only on a positional `-c` flag, so
   `TARGET=cloud tools/ch "…"` silently queried **local** while the file's own header documented
   `TARGET=cloud (-c)` as equivalent spellings. Every other tool here (`build-model.sh`,
   `apply-sql.sh`, `reconcile.sh`) takes `TARGET=`, so `tools/ch` was the odd one out and the
   divergence was invisible at the call site. The reproduction returned
   `Database sonyliv does not exist`, which reads as the graded database having been dropped —
   it had not been; the query was simply on the wrong server. A typo like `TARGET=Cloud` now
   dies rather than falling through to local, because silently defaulting is the whole failure
   class this ADR exists to remove.
4. **Missing config dies at startup, naming the variable** — in `tools/ch` before any request; in Go
   at `config.Load`. Never a confident query against the wrong database.
5. **`.env` resolves relative to the repo root**, not the CWD (`tools/ch` used to silently lose all
   configuration when invoked from a subdirectory).
6. `CH_DATABASE_LOCAL=default` is **required** in `.env` (documented in `.env.example`).

## Intentional differences vs drift

The durable part. When local and Cloud disagree, check this table before debugging the model.

**Intentional (do not "fix"):**

| Difference | Why |
|---|---|
| Database name: local `default`, Cloud `sonyliv` | The container's initdb loads into `default`; the venue provisioned `sonyliv`. Encoded per target in `CH_DATABASE_LOCAL` / `CH_DATABASE`. |
| Local carries a subset of objects (6 tables; no serving views, hour tier, or publish machinery) | Local exists for fast iteration; tiers are built on demand by `tools/build-model.sh` / `tools/apply-sql.sh`. An absent object locally is "not built yet", not drift. |
| Users/auth: local `app` + `CH_PASSWORD_LOCAL` over HTTP :8123, Cloud `default` + `CH_PASSWORD` over HTTPS :8443 | Different security postures; both explicit in `.env`. |
| Cloud-only extra databases (`sonyliv_pub*`, `sonyliv_verify`, `sonyliv_unseen`, local `tie0014`, `csv_audit`) | Scratch/verification/publish spaces, each created deliberately by a tool that names its database. |

**Drift (found by the column diff, repaired 2026-08-01, local rebuild only):**

| Column | Was (local) | Is (both) | Damage window |
|---|---|---|---|
| `cc_minute_stateless.active_state`, `mv_stateless` | `AggregateFunction(uniq, String)` | `AggregateFunction(uniqExact, String)` | Zero **today** — at 1× cardinality (peak 2,894/min) `uniq` still answers exactly, all 3,860 minutes agreed. It starts lying silently at the 100× scale test. The type is the bug, not today's numbers. |
| `cc_minute_delta.starts`, `.ends` | `SimpleAggregateFunction(sum, UInt64)` | `…(sum, Int64)` | Local table was empty; unsigned would have corrupted ADR 0006's negative late-arrival corrections on first local build. |

Root cause of both: `CREATE TABLE IF NOT EXISTS` is a no-op on an existing table, so a git-side type
change never reaches an already-initialized local volume. Detection is one rerunnable diff of
`system.columns` across targets (commands in the evidence file); repair is DROP + re-apply the git
SQL + backfill, verified 0/3,860 minutes disagreeing with `ev_raw`.

**Known residue (owned elsewhere, flagged not fixed):** the local chains in `tools/apply-sql.sh` and
`tools/load.sh` still fall back to `CH_DATABASE` after `CH_DATABASE_LOCAL`. Dead in practice now
that `.env` must define `CH_DATABASE_LOCAL`, but the fallback steps should be deleted to match this
rule. Those files are owned by another workstream.

## Consequences

- `sonyliv verify -target local`, `tools/ch`, and the bug-11 scripts now resolve identically; the
  proof run in the evidence file shows the same command returning `default`/`sonyliv` with the same
  91,292 rows and peak 2,894 on both targets.
- A fresh clone without `.env`, or an `.env` missing a database variable, fails with a message
  naming the variable — on every layer.
- Local reconciliation is now trustworthy: a local/Cloud disagreement means the change under test,
  not an estimator or a signedness mismatch.
- Cost: one more required variable in `.env`. Deliberate — a guessed database was the incident.
