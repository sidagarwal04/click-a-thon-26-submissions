# UNSEEN_DATASET — run the pipeline on a new slice, on your own laptop

> The scored moment: the sealed slice drops near the end, we repoint at it, and the same three
> pages light up. This is the teammate-facing "how do *I* run it here" wrapper around the
> canonical procedure in **`../.mridul` §4** (auto-loaded via `CLAUDE.md`). If this file and
> §4 ever disagree, §4 wins — it's audited against the code.

## The mechanism (one line, not per-tool flags)
Everything — the CLI scan, the API, the dashboard, the bundle emitter — resolves the target
database through `run_incident.default_db()` **at call time**. So you repoint the whole stack by
editing **one line** in `.env`:
```
CLICKHOUSE_DATABASE=rca_unseen
```
No code edits, no `--db` on every command. For a one-off run without touching `.env`, set
`RCOS_DB=rca_unseen` in the environment (it wins over `.env`). Load each slice into its **own**
database, never into `rca` — keep `rca` as the seen/scratch data so a reload can't clobber it.

## Who does what
- **Captain (once):** loads the sealed slice into the shared ClickHouse as `rca_unseen`. One load,
  the whole team queries it — do **not** each spin up your own service (credits burn; "one service
  per team" in `../CLAUDE.md`).
- **Everyone else (your laptop):** point your local scan + dashboard at `rca_unseen` via the same
  `.env` line. "Local" = the UI/engine runs on your machine, the **data lives in the shared
  service**. Same creds everyone already has.

## The 5 steps (verbatim from `.mridul` §4)
```bash
# 1. repoint everything at the new db
echo 'CLICKHOUSE_DATABASE=rca_unseen' >> .env        # or edit the existing line

# 2. load: builds ad_events + dim tables + the denormalized `events` table, then verifies
python scripts/load_clickhouse.py --parquet data/unseen.parquet

# 3. scan: --rebuild-cube is REQUIRED — the cube is a snapshot, new rows are invisible until rebuilt
python run_incident.py --rebuild-cube

# 4. refresh the UI's fallback bundle (also rebuilds the cube)
python scripts/emit_ui_bundle.py

# 5. run the console, or if it's already up, hit the sidebar ↻ Refresh
streamlit run ui/app.py
```
The loader is schema-tolerant, uploads the local parquet via Arrow, reloads the dimension CSVs,
builds `{db}.events` (what every Metrics chart reads — **not** `ad_events`), and runs the integrity
asserts (row count, funnel monotonicity, CTR sanity, `advertiser_id` blank only on unfilled). If a
check says **FAIL**, stop — don't trust analysis on that load. Add `--narrate` to step 3 for the
LLM diagnosis, `--trace` for a public Langfuse trace.

## Rehearse before the real drop (offline, no shared data touched)
Generate a ~10M-row synthetic slice with planted anomalies + a ground-truth manifest, point at it,
and run the same steps:
```bash
python scripts/gen_e2e_dataset.py            # builds rca_e2e server-side (nothing crosses the wire)
RCOS_DB=rca_e2e python run_incident.py --rebuild-cube      # engine must find the planted incidents
RCOS_DB=rca_e2e python scripts/emit_ui_bundle.py
RCOS_DB=rca_e2e streamlit run ui/app.py
```
`RCOS_DB=rca_e2e` repoints for that one run without editing `.env`. If it lights up end to end and
the engine finds the planted incidents, your machine is ready for the sealed slice — same steps,
`rca_e2e` → `rca_unseen`.

## Gotchas (the ones that bite on stage)
- **The loader `DROP`s `{db}.ad_events` first.** On the shared service, a teammate running the
  loader mid-demo drops your fact table. Present off a private frozen copy; leave `rca` as scratch.
- **The cube is a snapshot, not a materialized view** (there is no MV in the repo — don't say
  "materialized view" in the pitch). New rows stay invisible until `--rebuild-cube`.
- **Metrics reads `{db}.events`, not `ad_events`.** Loading a slice that skips the `events` build
  (e.g. an old loader) leaves every chart blank — the current loader builds it; don't hand-roll.
- **Parachute:** `RCOS_API=off` forces the UI onto `contracts/fixtures/scan_bundle.json` — the
  one-command recovery if ClickHouse misbehaves live. Keep that bundle current (step 4).
- **Pause the shared service when idle** — credits burn even idle ($400 total for the team).
