# Clean run — from nothing to a working system

Two paths live here: a **clean run** (wipe → working system, below) and **[Day 2](#day-2--new-data-without-a-wipe)** (load a new slice into the running stack, no wipe).

## Step 0 — prerequisites (once)

Optional but recommended, for real LLM narratives instead of deterministic templates:
edit `librechat/.env` → set `OPENAI_API_KEY` and `NARRATOR_MODEL=gpt-5-nano`. Without a
key the flow still works end to end on template narratives.

## Step 1 — run the script

```bash
./clean_run.sh --yes                                      # seen data only
./clean_run.sh --yes --unseen-dir /path/to/unseen_data    # seen + unseen slice
```

It wipes everything, boots ClickHouse + HyperDX + collector, loads the 9M events
(validation report must show every check `pass = 1`), then **pauses and waits for
Step 2**. With `--unseen-dir` it loads the unseen slice right after — order matters:
seen events are enriched under the old dims first, THEN the unseen folder's
regenerated dim CSVs replace them (spec requirement; enrichment is at insert time).

Ingest only — nothing is investigated yet.

## Step 2 — connect HyperDX to ClickHouse (the ONE manual moment)

Open **http://localhost:8081**. The "Welcome to HyperDX" wizard appears. Fill exactly:

| field | value |
|---|---|
| Connection Name | `Stack ClickHouse` |
| Host | `http://clickhouse:8123` ← **NOT localhost** (HyperDX runs inside Docker; localhost there is the HyperDX container itself) |
| Username | `rca_rw` |
| Password | `rca_rw_dev` |

Click **Test Connection** (green) → **Create Connection**.

The script detects this automatically, wires the trace API key, and boots LibreChat.

## Step 2b — investigate (your call, when you're ready)

```bash
./investigate.sh            # profiler + sweep + prefill
./investigate.sh --force    # re-investigate what's already diagnosed
```

One pass per loaded dataset, chronological, each restricted to its own date range
with `RCA_DATASET` set to match — an incident measured under the wrong dataset sees
zero rows (NO_DATA), and segment attributes differ per dataset. Spans stream to
HyperDX live. Works the same for a seen-only ingest (one pass) and seen+unseen (two).

## Step 3 — see the dashboard

1. In HyperDX go to **Dashboards → RCA Overview** (auto-seeded; sources too)
2. Set the time range to **2026-06-01 → 2026-07-06** — the data is historical;
   the default range shows an EMPTY dashboard every time
3. Traces: **Traces tab** → one `investigate <incident_id>` tree per incident

## Step 4 — LibreChat

1. Open **http://localhost:3080** → register (any credentials, it's local)
2. Create the RCA Analyst agent: follow `librechat/README.md` §5 (~2 min)
3. Ask: `What incidents are there?` then `Why did fill rate drop June 23–25?`
4. Full checklist: `librechat/GOLDEN_QUESTIONS.md`

## What success looks like

| stage | expect |
|---|---|
| load.sh | validation report: every check `pass = 1` |
| sweep | ~19 incidents, ~6 `detected` (Jun 21 revenue, Jun 23 fill among them) |
| prefill | one diagnosis per incident, `verified=True` on every line |
| HyperDX seed log | `RCA Overview dashboard created (11 tiles)` |
| HyperDX Traces | 19 traces, `investigate …` root span + step tree each |
| LibreChat | names Android 15, fill 0.4333 vs 0.785, ~98% of the drop |

## If something's off

| symptom | fix |
|---|---|
| port 8123/9000 busy at start | `docker stop clickhouse zookeeper` (other project), rerun |
| empty dashboard | it's the time range. It's always the time range (Step 3.2) |
| traces missing | `./librechat/wire_traces.sh` then re-investigate one incident: `cd librechat && docker compose exec -T rca-mcp python -c "from agent.runner import investigate; investigate('inc_20260623T00_fill_rate_global', force=True)"` |
| dashboard crashes the page | `cd librechat && docker compose exec -T mongodb mongosh --quiet --eval 'db.getSiblingDB("hyperdx").dashboards.deleteOne({name:"RCA Overview"})' && docker compose up -d --force-recreate hyperdx-seed` |
| edited code in agent/ or detector/ not taking effect | images bake code at build: `cd librechat && docker compose up -d --build rca-mcp` |
| narrator says 429 / template narratives | key over quota — switch `NARRATOR_MODEL` in `librechat/.env` to any model with a working key (`gpt-5-nano` is the cheapest paid option; `gemma-4-31b-it` and `gemini-3.1-flash-lite` have generous free limits; `template` = zero API calls, always works), then `docker compose up -d rca-mcp` and re-run prefill |
| agent chats but never calls tools | agent model has no function calling (Gemma models can't) — edit the agent, set a Gemini flash model; Gemma is narrator/plain-chat only |
| spans accepted but the trace looks stale in HyperDX | trace identity is scoped to the run (`<incident_id>-run-<run_id>`) precisely so re-runs appear as NEW traces; if you see spans merging onto an hours-old trace, the code is reusing a trace id — check `Investigation.trace_id` |

---

# Day 2 — new data without a wipe

The unseen-slice path. New events load into the SAME tables under a `dataset` tag. The MV
cascade fires on insert (enriched + hourly rollup populate automatically) and existing
data, incidents, diagnoses, and traces are untouched.

## Step 1 — load the new events file

```bash
cd ~/personal/ch-hackathon
export CH_HOST=localhost CH_SECURE=0 CH_TRANSPORT=http CH_USER=rca_rw CH_PASSWORD=rca_rw_dev
# folder drop with its own dim CSVs (the unseen slice ships regenerated dims — the
# spec says join against THOSE; --data-dir reloads them, --events would NOT):
./load.sh --data-dir /path/to/unseen_data --dataset unseen
# events-only drop (no new dims shipped):
./load.sh --events /path/to/new_events.parquet --dataset unseen
```

- Validation report runs on everything — every check must show `pass = 1`
- The guard refuses loading the same `--dataset` tag twice (safe to re-run);
  each new drop gets its own tag: `unseen`, `day2`, …

## Step 2 — see it in HyperDX (zero setup)

Dashboards read the rollup, which spans all datasets — just move the time picker to
the new data's window.

## Step 3 — detect + investigate only what's new

```bash
./investigate.sh
```

- profiler + sweep re-run over the extended timeline (sweep is idempotent:
  deterministic incident_ids, existing windows are skipped)
- prefill runs once per dataset, restricted to that dataset's date range with
  `RCA_DATASET` set to match; incidents that already have diagnoses are skipped,
  so only the new windows are investigated
- spans stream to HyperDX live (collector already wired from the initial setup)

## What success looks like (Day 2)

| stage | expect |
|---|---|
| load.sh | validation all `pass = 1`; row count grew by the new file's size |
| sweep | only NEW incident ids appended (old ones unchanged) |
| prefill | "N investigated, M already stored" — M = everything from before |
| HyperDX | new time window renders; new traces appear under Traces |

## Known caveat — short slices and baselines

The runner queries only the dataset named by `RCA_DATASET`. If the new slice is short
(a few days), q1 finds too few clean baseline days (`min_clean_days < 2`) and the
investigation correctly falls back to the **q4 peer path** (segment vs siblings, no
history needed). That is the designed behavior for the unseen incident.

Decided (2026-08-02, on the real unseen slice): baselines ARE shared. RCA_DATASET
accepts a comma-separated set and q1–q5 filter `dataset IN (...)`; investigate.sh
passes the cumulative chronological set per pass ("main" for main, "main,unseen" for
unseen). Isolated baselines degraded every unseen verdict to the peer path; with
sharing, the unseen fill trench diagnoses CAUSE_CONFIRMED on the baseline path.
Caveat that remains by construction: segment labels cross the dim-regeneration
boundary, so segment baselines mix populations — global measurements are exact,
segment baselines are approximate where the regenerated attributes reshuffled.
