# Atlys — agents that instrument, analyze, and explain

A feature spec goes in. A production ClickHouse table, a refreshed context layer, and
PM-readable insights come out — in one traced run.

```bash
python run_pipeline.py --spec ../specs/05_instant_forex/spec.md \
                       --events ../specs/05_instant_forex/events.ndjson
```

Nothing in the pipeline is written against a known spec. Everything — the column types,
the entity key, the funnel order, the segment dimensions — is derived from the events at
runtime. `tests/test_generalization.py` enforces that as a hard test.

**Just want to run it?** → [`RUN.md`](RUN.md) (prerequisites, env vars, one command,
troubleshooting).

For a tour of the code itself — module responsibilities, how a request flows through the
three agents, why the context layer is a ClickHouse table and not a vector store — see
**[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**. For how every claim this system
makes is actually checked — the layered verification stack, every statistical formula
used and where, and a real run of the eval harness with its results — see
**[`docs/EVALUATION.md`](docs/EVALUATION.md)**.

---

## Setup (fresh clone)

**Prerequisites**

| Tool | Why | Check |
|---|---|---|
| Docker | Runs ClickHouse (and optionally LibreChat) | `docker --version` |
| `git-lfs` | The `../data/*.parquet` files (~253MB) are LFS pointers in git | `git lfs version` |
| Python 3.12 or 3.13 | Pinned in `pyproject.toml`; 3.14 has wheel gaps for some deps | `python3.12 --version` |
| [Claude Code CLI](https://claude.com/product/claude-code), logged in | The pipeline runs LLM calls through `claude -p` on your subscription — **no API key needed** (see `ATLYS_LLM_BACKEND` below) | `claude --version` |
| A [Langfuse](https://cloud.langfuse.com) project (free tier) | Optional but expected by judging — every LLM call is traced | — |

**One command, from this directory (`Atlys/solution`):**

```bash
make init
```

This runs, in order: `setup` (venv + editable install), `lfs` (pull the parquet files),
`ch-up` (provision a fresh `atlys-ch` ClickHouse container), `seed` (load the 8 production
tables), `bootstrap` (parse `../base_context.md` into the versioned context layer),
`verify-stack` (a real smoke test against ClickHouse + Langfuse), and `test` (the fast,
no-LLM suite). It's idempotent — safe to re-run if it stops partway (e.g. no `git-lfs`
installed yet, or Docker not started).

Then add Langfuse credentials to `.env` (written for you from `.env.example` on first
`make setup`) — `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` — and run one
spec end to end:

```bash
./.venv/bin/python run_pipeline.py \
    --spec   ../specs/05_instant_forex/spec.md \
    --events ../specs/05_instant_forex/events.ndjson
```

**What `make init` does manually, step by step** (useful if it fails partway and you want
to resume from the failing step, or you're setting this up without `make`):

```bash
# 1. venv + deps (editable install; also copies .env.example -> .env if missing)
python3.12 -m venv .venv && ./.venv/bin/pip install -e '.[dev,mcp]'

# 2. pull the real parquet files (LFS pointers in git are ~130 bytes each)
git lfs pull --include="Atlys/data/*.parquet"      # run from repo root, or anywhere — git-lfs
                                                     # patterns are repo-root-relative regardless of cwd

# 3. ClickHouse, from scratch — container `atlys-ch`, db/user/password `atlys`/`atlys`/`atlys`
docker network create atlys-net 2>/dev/null || true
docker compose -f deploy/docker-compose.ch.yml up -d

# 4. load the 8 production tables (~2.5M rows)
cd ../data && CH='docker exec -i atlys-ch clickhouse-client' DB=atlys ./load.sh && cd -

# 5. seed the context layer from base_context.md (no LLM — deterministic markdown parsing)
./.venv/bin/python bootstrap_db.py --reset

# 6. confirm everything is real, not assumed
./.venv/bin/python -c "import tracing; print(tracing.verify())"   # -> (True, 'authenticated against ...')
./.venv/bin/python -m pytest tests/ -q                            # -> 135 passed
```

Run `make help` for the full command list (chat/UI/eval/legacy-projection targets, etc.).

---

## Testing it yourself

Everything below is run from this directory (`Atlys/solution`).

### 1. Fast checks — no LLM, ~2 seconds

```bash
./.venv/bin/python -m pytest tests/ -q
```

135 tests. The two that matter most:

- `test_generalization.py` — the **grep guard**. Fails if any source file names a known
  spec or a column unique to one. This is the artifact to look at if you suspect we
  tuned to the five specs we were given.
- `test_grounding.py` — locks in a real defect from our first end-to-end run (below).

### 2. Confirm the environment

```bash
./.venv/bin/python -c "import tracing; print(tracing.verify())"   # -> (True, 'authenticated against ...')
./.venv/bin/python -c "import llm; print(llm.backend_info())"     # -> claude CLI (subscription auth)
```

`tracing.verify()` does a real auth round-trip. Worth running before any demo: a wrong
Langfuse region fails silently at export time, not at startup.

### 3. Seed the context layer

Already done if you ran `make init`. To re-run by hand:

```bash
./.venv/bin/python bootstrap_db.py --reset
```

Parses `../base_context.md` into 43 versioned entries in ClickHouse. No LLM call.

### 4. Full pipeline run — ~10 minutes

```bash
./.venv/bin/python run_pipeline.py \
    --spec   ../specs/05_instant_forex/spec.md \
    --events ../specs/05_instant_forex/events.ndjson --rebuild
```

Nearly all of that is three Sonnet calls (design the schema, plan the queries, interpret
the results). The ClickHouse work is seconds; profiling the raw events is 0.09s.

**It will pause and ask you to approve the schema.** After the DDL proposal dry-runs
clean — proven runnable, but nothing executed or loaded yet — the pipeline prints the
DDL and rationale and stops:

```
Proceed with this schema? [y/N]
```

Nothing downstream (execute, load, MV measurement, context reconcile, analytics) runs
until you answer. Add `--yes` to skip the prompt and auto-approve (what `make sim-all`
and the eval harness's regression path use — a real demo/review run should not).
Launched non-interactively (e.g. by the Streamlit console, §10) the same gate polls the
`pipeline_approvals` table instead of stdin, for up to `--approval-timeout` seconds
(default 1800) before giving up and exiting declined (exit code 3) — nothing executed
or loaded either way.

### 5. Inspect what happened

Progress is written to ClickHouse as it runs, so you can watch from a second shell:

```sql
-- stage-by-stage timeline, including the context version each stage saw
SELECT stage, status, context_version, detail FROM pipeline_runs ORDER BY ts;

-- what the Context Agent caught, with the SQL that proves each one
SELECT kind, title, verified, verification_sql FROM contradiction ORDER BY detected_at;

-- findings with confidence
SELECT headline, metric, confidence, severity FROM insights_log ORDER BY ts;

-- the generated schema, self-documenting: every column comments its source JSON path
SHOW CREATE TABLE f_instant_forex_events;
DESCRIBE TABLE f_instant_forex_events;
```

Artifacts land in `artifacts/runs/<run_id>/`: `insight_report.md`, `schema.sql`,
`proposal.json` (DDL + rationale per decision), `context_diff.md`, `semantics.json`,
`trace_url.txt`.

### 6. Ask the PM questions interactively — ~40s per question

```bash
./.venv/bin/python ask.py                             # pick a spec, then ask
./.venv/bin/python ask.py --spec ../specs/<dir> --list # show that spec's PM questions
./.venv/bin/python ask.py --spec ../specs/<dir> --question "where do users drop off?"
```

Type a number to ask one of the spec's own PM questions, or ask anything in your own
words. Fast because the table already exists: semantics derive in ~0.1s, the template
suite runs once and is cached for the session, and each question is a single LLM call
over already-computed aggregates.

Every figure in an answer is checked against the query results the answer cites, and the
footer reports the real scan ratio (~2.5M rows read in ClickHouse → ~250 rows to the
model) plus a trace link.

### 7. Eval harness (no LLM)

```bash
./.venv/bin/python -m evalharness --all --out out/eval
```

Writes `out/eval/results.md`: 5 known specs from run history + 4 mock topologies
exercised fresh on the deterministic path. See that file for the measured table.

### 8. Legacy projection remediation (T4)

```bash
./.venv/bin/python legacy.py --table destination_card_clicked
```

Detects id-leading sort keys on the 8 production tables, adds a `(toDate(timestamp),
device_type, user_id)` projection, and writes `out/legacy_projection.md` with real
`read_bytes` before/after and the EXPLAIN that shows `ReadFromMergeTree (p_funnel)`.

### 9. MCP + LibreChat (T6)

```bash
# Prerequisites: local Ollama running with gemma4:e4b (or similar)
#   ollama pull gemma4:e4b
make up          # attach atlys-ch to atlys-net + start mcp-clickhouse
make mcp         # terminal 1: atlys-mcp on :8100 (Claude subscription)
make chat        # LibreChat on :3080 — opens the browser
```

Verified live: LibreChat initializes **2 MCP servers / 10 tools**
(`atlys`: ask, list_features, explain_metric, … · `clickhouse`: run_query, …).

In the UI: register → pick **Ollama Cloud** or **Ollama (local)** / a model → enable MCP
servers **atlys** + **clickhouse**. Try: `what is our conversion rate?` — should come
back DISPUTED with both definitions.

Auth split (important): LibreChat's *chat* model is independent of everything else —
either **Ollama Cloud** (`https://ollama.com/v1/`, needs a real `OLLAMA_API_KEY`) or
**Ollama (local)** (`host.docker.internal:11434`, no key). Tool calls always hit host
`atlys-mcp`, which uses your Claude Code subscription via `claude -p`, regardless of
which chat model is driving the conversation. Do **not** set `ANTHROPIC_API_KEY` in
`.env` — that breaks the subscription path.

**Ollama Cloud key**: `/v1/models` on `ollama.com` is a *public, unauthenticated*
catalog listing — a 200 from it proves nothing about your key. The real test is a
completions call:

```bash
curl https://ollama.com/v1/chat/completions \
  -H "Authorization: Bearer $OLLAMA_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss:20b","messages":[{"role":"user","content":"pong"}]}'
```

If that 401s, the key itself is invalid/expired — get a fresh one from
[ollama.com/settings/keys](https://ollama.com/settings/keys) and update `OLLAMA_API_KEY`
in `.env`; nothing in `deploy/librechat.yaml` needs to change.

**After changing `.env`, recreate the container — do not `docker restart` it.**
`docker restart` reuses the container's existing environment and will keep serving the
old key, and the failure is deceptive: LibreChat's `/api/models` will still list the
full Ollama Cloud catalog (that upstream endpoint is public), so the stack *looks*
configured right up until an actual chat turn returns 401.

```bash
set -a; source .env; set +a
docker compose -f deploy/docker-compose.yml --profile librechat up -d --force-recreate librechat
docker exec atlys-librechat printenv OLLAMA_API_KEY   # must match .env
```

`make chat` does this correctly on its own. **Ollama (local)** needs no key either way.

**Do not** `docker compose up` a fresh ClickHouse. The Makefile attaches the already
populated `atlys-ch` container.

### 10. Console (dashboard + pipeline trigger)

```bash
./.venv/bin/streamlit run ui/app.py
```

One place to run the whole system instead of juggling terminals:

- **Run pipeline** — pick one of the 5 known specs or upload a new `spec.md` +
  `events.ndjson`, then trigger instrumentation → **approval** → seeding → context
  reconcile → analytics in one click. By default the run pauses after the DDL dry-runs
  clean: the proposed schema and its rationale render inline, and nothing executes or
  loads until you click Approve (or Reject, which stops the run there — nothing
  executed, nothing to undo). Check "Auto-approve" before launching to skip the review
  (the UI equivalent of `run_pipeline.py --yes`). Live stage-by-stage status, findings,
  context changes and a Langfuse trace link land on the same page as the run finishes —
  sourced from `pipeline_runs`/`pipeline_approvals`, so a second person watching the
  dashboard sees the identical state a CLI run would show, including the same pending
  approval if one is open. First-time setup (seed the 8 base tables, bootstrap the
  context layer) is one click each if they haven't run yet.
- **Schema changes over time, Insights + confidence, Context layer diff, Runs** — the
  original read-only dashboard views: schema history, findings with their four
  confidence components, a version-over-version context diff (now with an entries- and
  contradictions-over-time chart), and per-run trace links.
- **Chat** — LibreChat embedded inline (falls back to a plain link + setup instructions
  if `make chat`/`make mcp` aren't running).

Every view except **Run pipeline** reads only from ClickHouse; that one launches
`run_pipeline.py` as a real subprocess and reads its progress back out of
`pipeline_runs`, same as everything else — see the module docstring in `ui/app.py`.

---

## What to look at, and why

**Schema.** `SHOW CREATE TABLE f_status_sharing_events` is the interesting one — the
dual-sided spec. `ORDER BY (event, timestamp, share_id)`: the entity key was *derived*
as `share_id`, not assumed to be `user_id`, because two of its five event types are
anonymous recipient events carrying no user at all. No `Nullable` anywhere;
`LowCardinality` on enums but plain `String` on identity keys; `id` typed `String`
rather than `UUID` because the raw ids are 32-char hex without dashes — `UUID` would
have failed the load outright.

The legacy tables sort by `ORDER BY (id, timestamp, user_id)`. `id` is unique per row,
so that index prunes nothing, and `instrumentation_notes.md` admits queries never filter
on it. Every generated table states this contrast in its rationale. The Context Agent
flags those sort keys as `stale_entry`; `legacy.py` prices and fixes one with a
projection (measured 1.16× fewer bytes on `destination_card_clicked`).

New tables also get a **schema bake-off** after load: the agent's `ORDER BY` is measured
against a timestamp-first straw-man on the same funnel query, and the ratio is appended
to `rationale["order_by"]`. At sample volume (~6k rows) both layouts often read the same
bytes — that is reported honestly, and the straw-man is dropped either way.

**Token discipline.** The insight report header carries `rows_scanned_in_clickhouse` vs
`rows_sent_to_llm` — 62,370 vs 240 on the control spec. Computed, not claimed.

**Materialized views** are kept or dropped on a *measured* reduction factor, reported
either way: `mv_instant_forex_addon_value_daily: 6,237 -> 42 rows (148.5x) KEPT`.

**Context freshness** is mechanical, not asserted. `llm.complete_json()` cannot be called
without a `context_version` argument, so every LLM span in the trace records which
snapshot fed it. Analytics deliberately reads the snapshot taken *after* reconciliation,
so the trace shows it reasoning on v2 while the run started on v1.

**The empty-string trap.** House rules forbid `Nullable` on hot columns, so identity
columns default to `''`. A bare `uniq(user_id)` would then count the empty string as a
user — on the sharing spec that would inflate distinct users by 40%. Every template uses
`uniqIf(col, col != '')`, and a test asserts no bare `uniq` on an identity column exists.

---

## Numeric grounding — why it exists

On the first clean end-to-end run the Analytics Agent produced this, at 0.77 confidence:

> Median `addon_value_inr` is $0 in every segment

The queries it cited *in the same finding* returned 37,536 / 29,926 / 26,127. It had
conflated the whole-column data-quality probe (which scans all rows by design) with the
scoped distribution query, and wrote a plausible mechanism to justify a number that did
not exist.

A wrong number delivered fluently is worse than no finding, because a PM would act on it.
So `grounding.py` checks every finding's asserted value against the numbers actually
present in the queries it cites, and demotes anything that fails to informational with an
`UNVERIFIED` caveat. It is deterministic Python rather than a second LLM call — cheap,
fast, and re-runnable by a judge.

It discriminates rather than trivially passing: the hallucination above is demoted, while
a true claim citing the *same* queries survives untouched. See `tests/test_grounding.py`.

---

## Layout

| Path | Role |
|---|---|
| `contracts.py` | Every pydantic model. The interface all components code against. |
| `profile.py`, `mapping.py` | Deterministic inference: field types, entity key, funnel order. No LLM. |
| `agents/instrumentation.py`, `ddl.py` | Spec → DDL proposal → lint → dry-run → **human approval gate** → execute → load → measure MVs. |
| `agents/context_agent.py`, `contextlayer/` | Versioned context layer; six contradiction checks, each carrying its verification SQL. |
| `queries/templates.py` | T01–T12, parameterized by `FeatureSemantics` — never by a feature name. |
| `queries/stats.py` | Statistical reference implementation (tested, not imported by the live pipeline — see `docs/EVALUATION.md` §3). |
| `agents/analytics.py`, `confidence.py` | Plan → execute → interpret; the load-bearing four-component confidence score. |
| `grounding.py` | Numeric grounding guard. |
| `metric_policy.py` | Refuses unqualified answers to metrics with an open definition conflict. |
| `bakeoff.py`, `legacy.py` | Measured `ORDER BY` bake-off on new tables; projection remediation on the legacy ones. |
| `evalharness.py` | T8 eval harness — known-spec regression table + fresh mock-topology table. |
| `house_rules.md` | Schema conventions, fed verbatim into the designer prompt. |
| `run_pipeline.py` | The entrypoint. Five stages, one trace. |
| `ask.py` | Interactive Q&A over an already-instrumented feature. |
| `atlys_mcp/`, `deploy/` | MCP tool server + LibreChat/ClickHouse docker-compose for chat-driven access. |
| `ui/app.py` | Streamlit console: dashboard views + a spec-in/pipeline-trigger UI + embedded LibreChat. |
| `docs/ARCHITECTURE.md` | Full code overview: data flow, module map, design rationale. |
| `docs/EVALUATION.md` | Verification methodology, every statistical formula used, and a real eval run's results. |
| `docs/SCHEMA_CATALOG.md` | Generated (`make schema-doc`) from the live DB: every table/column, plus MVs measured and **rejected**. |
| `tools/schema_catalog.py` | The generator behind it — read-only over `system.*` + run artifacts. |

See `docs/ARCHITECTURE.md` for how these fit together. Runs on a Claude subscription via
the authenticated `claude` CLI — no API key. Set `ATLYS_LLM_BACKEND=api` to use the
Anthropic SDK instead.
