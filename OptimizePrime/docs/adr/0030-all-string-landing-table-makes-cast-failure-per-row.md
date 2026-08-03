# ADR 0030 — An all-`String` landing table makes a cast failure cost a row, not a file

> **Summary:** The loader's typed `input()` made ONE unparseable value fatal to the whole file —
> measured on the real 905,558-row file: exit 27, `ev_raw` 0 rows, `content_dim` left holding 33,464
> because it inserted first. ADR 0025's quarantine structurally cannot help, because `q_reason` takes
> an already-typed `DateTime64`. So the load is now two phases: **land** both CSVs into all-`String`
> tables (nothing can fail to parse into a String), then **cast forward per row** — clean rows to
> `ev_raw`, failures to `ev_cast_quarantine` with the raw text and a reason code. One bad row now
> costs one row. The happy path is proven byte-identical (order-free fingerprint over every column,
> both routes) and the gate still reads **17,028 · 0 mismatched · peak 2,917**. It is not free:
> **+70% bytes read, +4–19% server-side load time, +123% ingest storage.** We took that knowingly.

**Status** Accepted · 2026-08-02 · implemented in `sql/05_landing.sql` and `tools/load.sh`.

**Owns** `sql/05_landing.sql` (new), `tools/load.sh`, `tools/landing-test.sh` (new),
`evidence/landing/identity.txt`.
**Does not touch** `sql/15_normalise.sql` (ADR 0025's lane), `sql/30_build_intervals.sql`,
`sql/90_reconcile.sql`, `queries/validate_source_contract.sql`. No change to the model: this is an
ingestion boundary and nothing downstream of `ev_raw` moves.

---

## Context

`docs/codex-validation/004-triage.md` §D1 did not theorise this, it ran it. The real file, exactly
one value corrupted — data row 499,999, `event_timestamp` `1785063241252` → `NOT_A_TIMESTAMP`,
loaded by the committed loader with ADR 0024 and ADR 0025 already in place:

```
Code: 27. DB::Exception: Cannot parse input … (at row 500000)
  Column 5, name: event_timestamp, type: UInt64, ERROR: text "NOT_A_TIME" is not like UInt64

exit code                27
ev_raw after             0        rows   (of 905,558)
content_dim after   33,464        rows   ← loaded, because it inserts FIRST
retry with the good file:  REFUSED — "already holds data and INSERT APPENDS"
```

Three things follow, and the third is the one nobody had written down: the database is left
**half-populated**, and the only documented recovery is `--replace` — the destructive flag — at an
hour nobody is awake, on a file we get one shot at.

**Why ADR 0025 cannot reach this.** `q_reason(sid, uid, ts)` (`sql/15_normalise.sql:393`) takes an
already-typed `DateTime64(3)`. It is a rule over rows that are **already in `ev_raw`**. A row that
fails `input()` never gets there, so no reason code can ever fire on it. You cannot quarantine what
the type system rejected at the door. This confirms T3's own §Known gaps 1 rather than contradicting
it.

**Why this is not a hypothetical.** It is the same family as T2's seconds-vs-milliseconds finding,
and `tools/cruel-gen.sh`'s `badtypes` knob exists precisely to produce it. Measured here: against the
cruel file the old loader gives exit 27, `ev_raw` 0, `content_dim` 30.

## Decision

### 1 · Land as text first, type second

```
CSV ──► ev_landing / content_landing (all String) ──┬─► ev_raw / content_dim  (cast clean)
                                                    └─► ev_cast_quarantine    (cast failed)
```

Phase A lands **both** files. Nothing can fail to parse into a `String`, which is the entire point.
Phase B casts forward per row.

Twelve of `ev_landing`'s fifteen columns are `String` or `LowCardinality(String)`.
`LowCardinality(String)` accepts any string — it is a storage encoding, not a constraint — so the
eight repeated dimensions cost a fraction of plain `String` without giving up the property that
nothing can fail to land.

### 2 · Three fragile columns, three different answers

The bias is ADR 0025's — reject < quarantine < keep — applied one stage earlier. Only the column the
model cannot work without loses its row:

| column | uncastable → | disposition | why |
|---|---|---|---|
| `event_timestamp` | row does **not** reach `ev_raw` | `rejected` | the model is (session × time). A row with no placeable time cannot be counted at any minute. It is already `NEVER_DEFAULT` in the loader's header check. |
| `content_id` | `0`, row **does** reach `ev_raw` | `coalesced` | the viewer is real and counts in the total tier. Dropping the row would undercount concurrency to protect a dimension. `0` is what an **empty** `content_id` already became under the typed loader — the incumbent behaviour, made visible. |
| `session_start_epoch` | `1970-01-01`, row **does** reach `ev_raw` | `coalesced` | stored, never modelled (`DATA_DICTIONARY`), so it cannot move a number — and ADR 0025's `q_flags` already fires `session_start_out_of_range` on the epoch-zero value this produces. Same substitution `--allow-missing` already uses. |

`video_session_id` needs no rule: it is a `String` at both ends. An empty or unusable one is ADR
0025's `session_id_unusable`, downstream, where it already worked.

**A coalesced row is a row we changed, and a change we do not record is a change we cannot defend** —
so `ev_cast_quarantine` is a *ledger*, not only a reject bin. `disposition` says which happened.
`reason` is first-match-wins, most fatal first (the `q_reason` doctrine); `detail` names **every**
failing column with its raw text, so the ledger does not lose the second problem to the first.

### 3 · Ordering: both files land before either is typed

The brief offered two ways to stop the half-populated database. We took the first — **land both
before typing anything** — because it removes the failure rather than compensating for it: the class
that used to strike between the two typed `INSERT`s now strikes before the first one, when there is
nothing to half-populate.

Phase B then runs `content_dim` **first** and `ev_raw` **last** — the reverse of what 004 §D3
proposed. That proposal was right against the old loader and is obsolete against this one. `ev_raw`
is no longer the fragile `INSERT`; it is the one with **materialized-view side effects**
(`mv_stateless`, `mv_session_dirty`), and a rollback has to chase their target tables. Doing it last
keeps the window in which those targets can be dirty as small as it goes.

And we did the second thing as well: if phase B fails anyway — an infrastructure fault, since it can
no longer be a data one — and the typed tables started empty, they are truncated back to empty,
including MV targets **discovered from the server** rather than hard-coded, because a given database
may have more of them than this repo's `sql/` does. Under `--append` nothing is rolled back and the
loader says why: it cannot tell this load's rows from the ones the operator asked to keep, and
guessing would destroy data.

`ev_landing` and `ev_cast_quarantine` are deliberately **not** rolled back. After a failed load they
are the only record of what arrived.

### 4 · The loader applies `sql/05_landing.sql` itself

Four in-repo tools apply an *explicit subset* of `sql/` and then call the loader — `golden-gen`,
`cruel-gen`, `load-guard-test`, `unseen-run`. A loader that merely refused when `ev_landing` was
absent would break all four. The file is `CREATE ... IF NOT EXISTS` / `CREATE OR REPLACE VIEW`
throughout, so applying it is idempotent, and the loader self-guards it against destructive DDL on
the same pattern `tools/apply-sql.sh` uses — because this apply happens automatically, including
against the graded database.

It runs **after** the double-load guard, not before it. A loader that applies DDL on its way to
saying "NOTHING HAS BEEN LOADED" has created three tables in a database it just refused to touch,
and on the graded day a mistargeted run must leave no trace at all. Asserted:
`tools/load.sh` into a non-empty database exits 1 and the object count is unchanged.

`TARGET=local` sends it through `clickhouse-client --multiquery` in one shot. `TARGET=cloud` cannot:
this script talks to Cloud over HTTP by design and that endpoint rejects multi-statement queries, so
there the file is split on `;`. That is safe only because `sql/05_landing.sql` promises no string
literal in it contains a `;`, and the promise is written at the top of that file.

### 5 · Every landed row reaches exactly one terminal state, asserted at load time

`landed = typed + rejected`, checked by the loader before it reports success, per table. This is the
provable-disposition property 004 §2.1 asked for, without the batch-manifest table it also asked for
— asserted at load time rather than left in a manifest nobody reads. A mismatch is a **refusal**,
not a warning: it would mean rows went missing between landing and typing, which is exactly the
silent partial load this boundary exists to prevent.

## Proof

`tools/landing-test.sh` → `evidence/landing/identity.txt`. 22 assertions, local container only.

**The happy path is unchanged, byte for byte.** Order-free fingerprint — count, plus the sum and the
bitXor of a per-row `cityHash64` over every column including `extra` — on the real file, both routes:

```
ev_raw      pre-landing : 905558 11323271608680909621 15538575503364151543
ev_raw      landing     : 905558 11323271608680909621 15538575503364151543
content_dim pre-landing : 33464 17908377308551298947 10117155906616985401
content_dim landing     : 33464 17908377308551298947 10117155906616985401
```

The reference statement is written out in the test in full rather than fetched from git, so the
comparison keeps meaning something after the old loader scrolls out of history. The real file
produces **zero** cast-ledger rows.

**The gate still passes** on a model built through the landing table: 30,323 intervals · 28,073 delta
rows · 91,692 user buckets · `minutes_compared=17028 mismatched=0 max_abs_diff=0 peak=2917 PASS`.
`tools/golden-gen.sh` is green through the new loader too — 10 pass, 1 pre-existing known divergence
— and `tools/load-guard-test.sh` passes all 27 assertions, which also exercises the Cloud
statement-splitting path against ClickHouse Cloud 26.2.1.525 and confirms `sonyliv` was never
written.

**The defect, on the real file.** One corrupted `event_timestamp`, 905,558 rows:

| | pre-landing | landing |
|---|---:|---:|
| `ev_raw` | **0** | **905,557** |
| `content_dim` | 33,464 | 33,464 |
| exit code | 27 | 0 |

The rejected row's every field round-trips byte-for-byte out of `raw['…']`, with
`reason=cast_event_timestamp`, `disposition=rejected`,
`detail=event_timestamp=NOT_A_TIMESTAMP`.

**The full malformation sweep**, one file per class so each is measured alone — 004 §D1's table with
a second column:

| malformed `event_timestamp` | pre-landing | landing |
|---|---|---|
| `NOT_A_TIMESTAMP` | exit 27, **whole file lost** | exit 0, 1 row rejected |
| `-1` | exit 72, **whole file lost** | exit 0, 1 row rejected |
| `1785063241252.7` | exit 27, **whole file lost** | exit 0, 1 row rejected |
| `""` (empty) | exit 0, **silently 1970** | exit 0, 1 row rejected |
| `999999999999999999999999` | exit 0, **silently saturates to 9999** | exit 0, 1 row rejected |
| `1785063241` (seconds) | exit 0, **silently 1970-01-21** | exit 0, **still silent** — see below |
| `"1785063241252"` (quoted) | correct | correct |
| clean | correct | correct |

Three hard-fail classes became per-row. Two of the three *silent* classes are now caught at cast
time as well, which 004 did not ask for and is the better half of the result: an empty and an
overflowing timestamp are both uncastable, so both stop at the boundary instead of reaching the
model.

## What this deliberately does not do

- **It does not catch a castable-but-wrong value.** `1785063241` — seconds where milliseconds were
  meant — **is** a valid `UInt64`. No cast can object to it. It lands in 1970 and is caught one stage
  later by ADR 0025's `ts_out_of_range` rule, demonstrated in the evidence. The two boundaries
  compose and neither can do the other's job. **That rule only protects the model once
  `v_ev_model_input` is wired into `sql/30_build_intervals.sql` and `sql/90_reconcile.sql`** — 004
  §D2, still unowned, outside this branch's lane. Until then the seconds-class row reaches the model.
- **It does not fix a structurally broken CSV.** A row with the wrong number of fields, an
  unterminated quote — those fail in the reader, before any column has a value to hold, and still
  cost the file. This boundary converts **type** failures to per-row, not **framing** failures. It
  does improve them: they now fail in phase A, so `content_dim` is no longer left populated beside an
  empty `ev_raw` (verified).
- **It adds no ingest metadata to `ev_raw`.** 004 §E2 wanted `ingest_batch_id`, source key, checksum,
  row number. `load_id` lives on the landing tables, which are new, not on the graded `ev_raw` —
  which `docs/GRADED_INVENTORY.md` records has already drifted once.
- **It builds no batch-manifest table.** The disposition identity is asserted at load time instead
  (§5). 004 §E1 costed the full recipe at a day; this is the part that buys the unseen day.
- **It does not change the model.** Nothing downstream of `ev_raw` moves.

## Cost — measured, and not small

14 alternating loads of the real file on the same container, same page-cache state:

| | pre-landing | landing | delta |
|---|---:|---:|---|
| server-side INSERT, min of 14 | 1,507 ms | 1,572 ms | **+4.3%** |
| server-side INSERT, median of 14 | 1,907 ms | 2,274 ms | **+19.2%** |
| bytes read per load | 333.07 MiB | 564.90 MiB | **+69.6%** |
| statements per load | 2 | 6 | |
| ingest storage on disk | 6.98 MiB | 15.56 MiB | **+122.9%** |

Wall clock is not the headline number: this container is shared with nine other worktrees and swings
about 2× run to run — the first measurement taken for this ADR read 4× and was wrong, confounded by
one route running cold and the other warm. The min-of-14 is the least-contended estimate; the median
is the honest one to plan with.

**The storage is the real price.** `ev_landing` (8.13 MiB) is *larger* than `ev_raw` (6.62 MiB),
because `LowCardinality` + `DateTime64` typing compresses better than text, and it is **46% of the
whole built model**. It is reclaimable in one statement once a load is verified — `TRUNCATE TABLE
ev_landing` — and `--replace` already truncates it, which matters because `tools/golden-gen.sh`
reloads in a loop. What truncating gives up is the raw text of the rows that **did** type; the rows
that did not are in the ledger, which is tiny.

Round trips were cut where they were free to cut: the pre-load guard and the post-load disposition
check each went from four or five separate queries to one, and the local schema apply from eleven
`docker exec` calls to one `--multiquery`. That is not a saving over the old loader, it is a saving
against a naive version of the new one.

## Consequences

- A file with a bad row now **succeeds**, where it used to fail loudly. `tools/unseen-run.sh` asserts
  `ev_raw count == CSV data rows` and would die on the difference — correctly, as a stop-and-look,
  but it is now an assertion about a case that produces a usable database. That script is not in this
  lane; its owner should decide whether the assert becomes `landed == CSV rows`.
- `tools/cruel-gen.sh`'s `badtypes` knob is documented as "the DESIGNED outcome is a loud parse
  failure with zero or partial rows". That expectation is now stale: the loader takes it cleanly, 36
  of 37 rows, with two coalesced `content_id`s and one rejected timestamp in the ledger. Also not in
  this lane.
- Reading the ledger is the first thing after a load on the unseen day, beside
  `v_quarantine_summary`: `SELECT * FROM v_cast_quarantine_summary`. The loader prints it
  automatically whenever it is non-empty, and stays silent when it is not — which on the provided
  file is always.
- `sql/05_landing.sql` is picked up by `tools/apply-sql.sh`'s bare `sql/*.sql` glob in lexical order,
  between `00_schema` and `10_intervals`. It has no dependency on either.
