# tools/

> **Summary:** Scripts the agent built to make its own job easier. When a manual sequence repeats
> three times, it becomes a script here. Everything reads `.env`. **Which database a tool writes is
> resolved and printed — see [Which database](#which-database-am-i-writing) below; `load.sh` and
> `apply-sql.sh` obey `--database`, then the environment, then `.env`, and refuse rather than guess.**

| Tool | Does |
|---|---|
| `fetch_data.sh [--force\|--verify]` | download the provided CSVs into `data/`, sha256-pinned. Run this before `load.sh` |
| `ch [-c] "SQL"` | run a query — local by default, `-c` for Cloud |
| `stats "SQL"` | run a query and print `X-ClickHouse-Summary` (rows/bytes/ms) — no `FLUSH LOGS` |
| `load.sh [--database N] [--replace\|--append] [raw.csv] [content.csv]` | load the datasets, converting epoch **millis** → `DateTime64(3)`. Two phases since [ADR 0030](../docs/adr/0030-all-string-landing-table-makes-cast-failure-per-row.md): **land** both files as all-`String` rows, then **cast forward per row** — so one unparseable value costs that row, not the whole file. Failures land in `ev_cast_quarantine` with their raw text; the loader prints them when there are any. **REFUSES if the tables already hold rows** — a re-load appends and doubles `ev_raw` silently |
| `landing-test.sh` | proves ADR 0030: the real file through the landing table is byte-identical in `ev_raw`/`content_dim` to the pre-landing typed `input()`, the gate still reads 17,028 / 0 / 2,917, one corrupted timestamp costs one row instead of 905,558, a phase-B fault rolls back, and the cost is stated. Local only, `landtest_*` databases. Writes `evidence/landing/identity.txt` |
| `policy.sh {get\|env\|version\|hash\|stamp\|list\|gen\|check}` | **the one declaration** ([ADR 0032](../docs/adr/0032-one-versioned-policy-declaration-read-by-every-consumer.md)). `policy/model.policy` holds every tuned constant once; `gen` renders it to `sql/01_policy.sql` (the view `v_model_policy`, which SQL reads), `get`/`env` serve shell, `tools/policy_reader.py` serves Python, `stamp` is the one-line evidence header, and `check` is a **gate**: stale rendering, a cover below `TAIL_S + 60`, a TTL that drifted from `QUEUE_TTL_DAYS`, or a consumer that grew its own literal back all fail. Needs no ClickHouse unless given `--database` |
| `build-model.sh` | **the RECOMPUTE path.** Rebuild the model in order: intervals + user tier -> deltas -> hour tier -> views, then reconcile all three tiers. TRUNCATEs first — deltas double if you do not, and the user tier drifts silently upward (ADR 0012) |
| `generation-install.sh --database N` | **one-way conversion** to the generation-pinned serving surface ([ADR 0034](../docs/adr/0034-generation-pinned-serving-surface.md)): applies `sql/95_generations.sql`, then drops the four tier tables and re-creates their names as views over the `gen_*` tables, pinned to the committed generation. Every downstream view and benchmark query keeps working unedited. Refuses `sonyliv` (no override) and refuses a tier that holds rows. The destructive half lives here and not in `sql/`, because `apply-sql.sh` applies every file in that directory |
| `build-generation.sh --database N` | **the SAFE RECOMPUTE path.** Wraps `build-model.sh` unchanged: builds into a disposable `<db>_bld_gG`, stages the four tiers into the serving database as generation G (invisible), re-runs the gates against G *as staged*, and only then commits — one INSERT that flips all four tiers together. A build that dies leaves the previous generation serving, whole. `KILL_AFTER=` and `DOUBLE_DELTA=` reproduce the 2026-08-02 doubling; `KEEP=` (default 2) sets how many generations stay rollback-able. Proof: [evidence/generation-pinning/](../evidence/generation-pinning/) |
| `publish.sh --database N [--loop S]` | **the INCREMENTAL path** — one publication batch. Claims the sessions that received events since its cursor, re-derives only those, appends `-deltas(old) + deltas(new)`. Never truncates. `--sessions a,b` forces a correction; `--status` prints freshness. Refuses `sonyliv` unless `PUBLISH_ALLOW_PROD=1`. See [ADR 0013](../docs/adr/0013-continuous-publication-by-incremental-finalizer.md) |
| `publish-test.sh` | proves the above: builds through the incremental path, lands three shapes of late arrival including a 46-minute-late straggler, and compares against a from-scratch rebuild on every minute. Two scratch databases, `sonyliv` read-only. Writes `evidence/publish.txt` |
| `reconcile.sh` | **THE GATE** — recompute concurrency from `ev_raw` and compare. Exits 1 on any mismatch; writes `evidence/reconcile.txt` |
| `bench.sh` | **THE BENCHMARK EVIDENCE** — run the reconstructed benchmark set (`evidence/benchmark/*.sql`, peak/avg × minute/hour/day × filters) against the graded Cloud database, READ-ONLY. Warm-up discarded, query caches off, median of 3, every run tagged with a `log_comment` and its `query_id` recorded. Writes `evidence/bench.txt` + `evidence/benchmark/results/` via `bench_report.py` |
| `bench_report.py` | formats `evidence/bench.txt` from `bench.sh`'s raw capture — pure formatting, no recomputation. Driven by `bench.sh`, not run by hand |
| `apply-sql.sh [--database N] [file...]` | apply `sql/*.sql` to local or `TARGET=cloud`. initdb only runs on first boot; Cloud has no mount at all |
| `load-guard-test.sh` | negative tests for the two above: makes them refuse a double load and proves a load lands in the database that was asked for. Own scratch databases, dropped on exit; never writes `sonyliv` |
| `clickstack-bootstrap.sh` | headless ClickStack setup; prints the OTLP ingestion key |
| `clickstack-sources.sh` | point the SELF-HOSTED HyperDX at our concurrency views. Idempotent: existing named sources converge by full-replacement PUT |
| `clickstack-cloud.sh` | provision the HyperDX built into ClickHouse Cloud — 27 sources, seven dashboards, saved searches — via the Cloud API. Idempotent: existing sources and dashboards converge by PUT |
| `clickstack-static-test.py` | offline gate: all 12 declared dataset filters exist in `v_session_minutes`, both source definitions and the hosted dashboard; both provisioners PUT existing sources instead of retaining stale selects |
| `clickstack-alerts.sh [--validate\|--verify]` | concurrency-**decline** detection + the three-way ended/broken/boring classifier: one dashboard, one webhook, 3 alerts on hosted HyperDX. Idempotent. `--validate` regenerates every threshold's evidence read-only; `--verify` reads the alerts back signed-in. Read-only against ClickHouse ([docs/DECLINE_ALERTING.md](../docs/DECLINE_ALERTING.md)) |
| `clickstack-artifact.sh` | regenerate the offline demo fallback `docs/artifacts/2026-08-01-clickstack-dashboards.html` from live serving-view data |
| `../evidence/capture.sh` | the evidence harness — parts, compression, pruning, latency, MV cost |
| `scale-test.sh [N...]` | **THE SCALE EVIDENCE** — run the model at 1x/10x/100x the provided file and write `evidence/scale.txt`. Local only, own scratch databases, drops them after. `KEEP=1` to inspect |
| `scale-gen.sql` | fits the generator's vocabularies (`gen_lut`, `gen_content`, `gen_ev`, `gen_start`) off the **real** file. Driven by `scale-test.sh`, not run by hand |
| `scale-load.sql` | the generator itself — `INSERT ... SELECT FROM numbers_mt`, all server-side. Deterministic: every draw is `cityHash64(session, salt)`, so `(S, SEED)` regenerates the same stream |
| `scale-fidelity.sql` | real vs synthetic on the shape metrics the model reads. This is what makes the scale timings falsifiable |
| `unseen-run.sh <raw.csv> <content.csv\|none>` | **THE UNSEEN-DAY RUN** — whole path in an isolated scratch DB (`UNSEEN_DB=`, pick a FRESH name), ends on the verbatim gate and asserts its SUMMARY against the day's spine. Peak minutes resolve per ADR 0014. See [docs/RUNBOOK_UNSEEN.md](../docs/RUNBOOK_UNSEEN.md) |
| `contract-runner-agreement.sh [fixture...]` | **THE TWO ENTRY POINTS MUST AGREE** — feeds the same CSV to the contract gate (RUNBOOK §0) and to `unseen-run.sh`, and fails if the gate PASSES a file the runner then REFUSES. Carries both-refuse controls so agreement cannot be earned by a guard that stopped guarding. Own scratch DBs. See [evidence/q37/](../evidence/q37/) |
| `unseen-gen.sh` | manufacture a synthetic unseen day (every trap designed in, per-minute answer known analytically) → `data/unseen-synthetic-*.csv` + `evidence/unseen/designed-truth.tsv` |
| `unseen-verify.sh` | compare the serving layer against the generator's designed truth (a third implementation of the counting spec) and probe each trap. Writes `evidence/unseen/verify.txt` |
| `../demo/chaos.sh <beat>` | demo fault injection (`stall_mv`, `stall_ingest`, …) |

## Loading twice

`INSERT` appends. `sql/00_schema.sql`'s claim that `non_replicated_deduplication_window` makes a
replayed batch idempotent is **false on Cloud** (that setting is for non-replicated MergeTree; Cloud
runs SharedMergeTree). Measured: the identical 30,097-row CSV loaded twice left `ev_raw` at **60,194
rows**, no error — RUNBOOK [A4](../docs/RUNBOOK_UNSEEN.md#a4). So `load.sh` **refuses** to load into
tables that already hold rows:

| You want | Type |
|---|---|
| a clean load into an empty database | `tools/load.sh …` |
| to redo a load that looked wrong | `tools/load.sh --replace …` — TRUNCATEs both tables, printing the row counts it destroys |
| to add a second day-file on purpose | `tools/load.sh --append …` — prints what it is adding to |

Refusal is the default because on the graded day the second run is nearly always "redo it" (one
flag), while a stray re-run must never be able to double the day or destroy a good load. It exits
**1** and loads nothing. `tools/unseen-run.sh` is unaffected: it drops its scratch database first.

## Which database am I writing?

`CH_DATABASE` used to be read *after* `. ./.env`, and `set -a` makes the file overwrite the
environment — so `CH_DATABASE=scratch tools/load.sh` wrote to whatever `.env` said, usually the
graded database (bug 11). The local branches passed no `--database` at all, so every local load and
every local `apply-sql.sh` landed in `default` regardless of configuration.

`load.sh` and `apply-sql.sh` now resolve one name, print it with its source, and refuse to guess:

```
TARGET=cloud   --database  >  $CH_DATABASE  >  .env CH_DATABASE  >  hard error
TARGET=local   --database  >  $CH_DATABASE_LOCAL  >  $CH_DATABASE
                           >  .env CH_DATABASE_LOCAL  >  .env CH_DATABASE  >  hard error
```

A `--database` that contradicts an exported `CH_DATABASE` is an error, not a preference. A database
that does not exist on the target is an error *before* anything is written.

**`CH_DATABASE_LOCAL` is new and you probably need it.** `CH_DATABASE` names the *Cloud* database
(`.env.example` groups it under Cloud), while the local container keeps its data in `default`. Put

```
CH_DATABASE_LOCAL=default
```

in `.env` — without it a local `tools/build-model.sh` / `make model` now resolves to the Cloud name,
does not find it locally, and says so instead of quietly writing to `default`. **`.env.example` does
not carry this line yet** (that file is owned elsewhere); add it by hand when you copy it.

Not every tool is fixed: `tools/ch`, `reconcile.sh`, `build-model.sh` and `truncation-test.sh` still
`cd` to the repo root and let `.env` win, and `tools/ch`'s local branch still has no database
parameter at all — so the local gate reads `default` whatever you set. Point them at another database
by editing `.env`.
