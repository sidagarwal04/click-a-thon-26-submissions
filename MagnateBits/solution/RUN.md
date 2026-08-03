# RUN.md — how to run this

Local setup, from a clean clone to a traced end-to-end pipeline run.

Everything below runs from **`Atlys/solution/`**. Every command is copy-pasteable and
was executed as written.

> **ClickHouse target.** This guide runs ClickHouse locally in Docker. Nothing in the
> code hardcodes a host — `ch.py` reads every connection parameter from the environment
> (`CH_HOST`/`CH_PORT`/`CH_USER`/`CH_PASSWORD`/`CH_DATABASE`/`CH_SECURE`) and
> `../data/load.sh` already accepts a `--secure` client — so pointing at ClickHouse
> Cloud is a `.env` change rather than a code change. That path is **not exercised
> here**, and we have not tested it.

---

## 1. Prerequisites

| Tool | Why | Check |
|---|---|---|
| Docker | Runs ClickHouse (and optionally LibreChat) | `docker --version` |
| `git-lfs` | `../data/*.parquet` (~253 MB) are LFS pointers in git | `git lfs version` |
| Python **3.12 or 3.13** | Pinned in `pyproject.toml` (`>=3.12,<3.14`) — 3.14 has wheel gaps | `python3.12 --version` |
| [Claude Code CLI](https://claude.com/product/claude-code), logged in | LLM calls run on your **subscription** via `claude -p` — no API key needed | `claude --version` |
| A [Langfuse](https://cloud.langfuse.com) project (free tier) | Tracing. Judged — *"no trace, no credit"* | — |

Ports used: **8123**/9000 (ClickHouse), 8100 (atlys-mcp), 8000 (mcp-clickhouse),
3080 (LibreChat), 8501 (Streamlit console).

## 2. One command

```bash
cd Atlys/solution
make init
```

That runs, in order: `setup` (venv + editable install, and copies `.env.example` →
`.env` if absent) → `lfs` (pull the parquet files) → `ch-up` (provision the `atlys-ch`
container) → `seed` (load the 8 production tables, ~2.5M rows) → `bootstrap` (parse
`../base_context.md` into the versioned context layer) → `verify-stack` (a real smoke
test) → `test` (241 tests).

It is **idempotent** — safe to re-run if it stops partway (no `git-lfs` yet, Docker not
started, etc.).

<details>
<summary>Manual equivalent, if you'd rather not use <code>make</code></summary>

```bash
python3.12 -m venv .venv && ./.venv/bin/pip install -e '.[dev,mcp]'
cp .env.example .env

git lfs pull --include="Atlys/data/*.parquet"   # patterns are repo-root-relative

docker network create atlys-net 2>/dev/null || true
docker compose -f deploy/docker-compose.ch.yml up -d      # atlys-ch on :8123

cd ../data && CH='docker exec -i atlys-ch clickhouse-client' DB=atlys ./load.sh && cd -
./.venv/bin/python bootstrap_db.py --reset
./.venv/bin/python -m pytest tests/ -q
```
</details>

## 3. Environment variables

Edit `.env` (created by `make setup`; git-ignored). Only the Langfuse keys need your
input — the ClickHouse defaults match the container `make ch-up` provisions.

### ClickHouse
| Var | Default | Notes |
|---|---|---|
| `CH_HOST` | `localhost` | |
| `CH_PORT` | `8123` | HTTP interface |
| `CH_USER` / `CH_PASSWORD` | `atlys` / `atlys` | Set by `deploy/docker-compose.ch.yml` |
| `CH_DATABASE` | `atlys` | |
| `CH_SECURE` | `false` | `true` + port `8443` for a Cloud service |

### Langfuse (tracing)
| Var | Notes |
|---|---|
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-…` from your project settings |
| `LANGFUSE_SECRET_KEY` | `sk-lf-…` |
| `LANGFUSE_HOST` | **Region matters.** `https://us.cloud.langfuse.com` or `https://cloud.langfuse.com` (EU). A US project 401s against the EU default. |

The `.env.example` placeholders are detected and treated as absent, so an unconfigured
clone runs with tracing **off** rather than emitting a stream of silent 401s. Confirm
with the check in §5.

### LLM
| Var | Default | Notes |
|---|---|---|
| `ATLYS_LLM_BACKEND` | `cli` | `cli` = Claude subscription via `claude -p` (**no API key**) · `api` = Anthropic SDK + `ANTHROPIC_API_KEY` · `mock` = deterministic, offline, zero credentials |
| `ATLYS_LLM_MODEL` | `claude-sonnet-5` | |
| `ATLYS_LLM_EFFORT` | `low` | Correct here: every call is bounded JSON emission over pre-computed context. Measured 5× wall-clock and 3.6× output tokens when unset, with no quality difference. |
| `ATLYS_LLM_TIMEOUT_S` | `600` | |

⚠️ Do **not** set `ANTHROPIC_API_KEY` while using `ATLYS_LLM_BACKEND=cli` — its presence
makes `claude -p` refuse subscription auth.

### Context retrieval
| Var | Default | Notes |
|---|---|---|
| `ATLYS_CONTEXT_RETRIEVAL` | `vector` | In-ClickHouse relevance ranking (`cosineDistance` + HNSW + text index). Set `full` to dump the whole layer into every prompt instead. |
| `ATLYS_RAG_TOP_K` | `12` | |

## 4. Run the pipeline end to end

```bash
./.venv/bin/python run_pipeline.py \
    --spec   ../specs/06_unseen/spec.md \
    --events ../specs/06_unseen/events.ndjson \
    --rebuild
```

Any of `01_express_checkout`, `02_group_family`, `03_status_sharing`,
`04_abandoned_checkout_recovery`, `05_instant_forex`, `06_unseen` works — nothing in the
pipeline is written against a known spec.

**It pauses for approval.** Once the DDL proposal dry-runs clean — proven runnable, but
nothing executed — it prints the DDL and rationale and waits:

```
Proceed with this schema? [y/N]
```

Nothing downstream (execute, load, MV measurement, context reconcile, analytics) runs
until you answer. Add `--yes` to auto-approve for an unattended run. Launched
non-interactively, the same gate polls the `pipeline_approvals` table instead of stdin
(`--approval-timeout`, default 1800s) and exits **3** if nobody answers — nothing
executed either way.

Takes ~3 minutes; nearly all of it is three LLM calls. Exit codes: **0** clean,
**1** hard failure (nothing written), **2** degraded (artifacts still written),
**3** declined.

**Output** — `artifacts/runs/<run_id>/`:

| File | What |
|---|---|
| `schema.sql` | The generated DDL |
| `proposal.json` | DDL + a rationale per decision + measured MV keep/drop |
| `insight_report.md` | The PM-facing insight summary |
| `context_diff.md` | What the Context Agent added/updated/superseded |
| `semantics.json` | Derived entity key, funnel, segment dims |
| `trace_url.txt` | The Langfuse trace |

## 5. Verify it worked

```bash
./.venv/bin/python -c "import tracing; print(tracing.verify())"
# -> (True, 'authenticated against https://us.cloud.langfuse.com')

./.venv/bin/python -c "import llm; print(llm.backend_info())"
# -> claude CLI (subscription auth), model=claude-sonnet-5

./.venv/bin/python -m pytest tests/ -q      # -> 241 passed
```

`tracing.verify()` does a real auth round-trip — worth running before any demo, because
a wrong Langfuse region fails at export time, not at startup.

Watch a run from a second shell (everything is written to ClickHouse as it happens):

```sql
SELECT stage, status, context_version, detail FROM pipeline_runs ORDER BY ts;
SELECT kind, title, verified, verification_sql FROM contradiction ORDER BY detected_at;
SELECT headline, metric, confidence, severity FROM insights_log ORDER BY ts;
SHOW CREATE TABLE f_unseen_events;
```

## 6. The other entrypoints

```bash
# Ask a feature's PM questions interactively (~40s each; the table already exists)
./.venv/bin/python ask.py --spec ../specs/06_unseen \
    --question "Which coupon codes erode margin without driving volume?"

# The Analytics Agent over the 8 PRE-EXISTING tables + the 4 standard probe prompts
./.venv/bin/python probe.py            # -> out/probe/PROBE_RESULTS.md

# Console: insights + evidence chain, run flow, native trace tree, trigger a run
./.venv/bin/streamlit run ui/app.py    # -> :8501

# Eval harness (no LLM): DDL re-verification, mock topologies, groundedness
make eval                              # -> out/eval/results.md

# Regenerate the schema catalog from the live DB
make schema-doc                        # -> docs/SCHEMA_CATALOG.md
```

**Chat over MCP** (two terminals — `atlys-mcp` runs on the *host* so it can use your
Claude subscription):

```bash
make mcp      # terminal 1 — atlys-mcp on :8100
make chat     # terminal 2 — LibreChat on :3080, opens a browser
```

In the UI: register → pick a model → enable MCP servers **atlys** + **clickhouse**.
Try *"what is our conversion rate?"* — it should come back **DISPUTED** with both
definitions rather than a single number.

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `git-lfs not installed` during `make init` | `brew install git-lfs && git lfs install`, then re-run `make init` |
| Parquet files are ~130 bytes | LFS pointers, not content. `make lfs` |
| `make ch-up` — container name conflict | An `atlys-ch` already exists: `docker start atlys-ch` (keeps data) or `docker rm -f atlys-ch` then `make ch-up` |
| `tracing.verify()` → `REJECTED by …` | Wrong Langfuse region. Switch `LANGFUSE_HOST` between the US and EU hosts. |
| `tracing_enabled()` is False | `.env` still holds the `pk-lf-…` placeholders |
| `claude` not found / auth refused | Install and log into Claude Code, **and** ensure `ANTHROPIC_API_KEY` is unset — or switch to `ATLYS_LLM_BACKEND=api` |
| Pipeline appears to hang after the DDL | It is waiting for schema approval. Answer the prompt, or pass `--yes`. |
| Want to run with no credentials at all | `ATLYS_LLM_BACKEND=mock` — the whole pipeline, offline and deterministic. Output is schema-valid but placeholder prose; every downstream gate still applies. |

Never `docker compose up` a second ClickHouse — `make ch-up` provisions `atlys-ch` and
everything else attaches to it. `make nuke` deliberately refuses to touch it.

---

Deeper reading: [`README.md`](README.md) (what it does and why),
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (module map, data flow),
[`docs/EVALUATION.md`](docs/EVALUATION.md) (how claims are verified),
[`docs/SUBMISSION.md`](docs/SUBMISSION.md) (evidence map against the track guidelines).
