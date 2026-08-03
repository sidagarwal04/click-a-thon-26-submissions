# CLAUDE_RUNBOOK.md — get everything running on a fresh machine

**Who this is for:** an AI assistant (or a human) with a clean clone and nothing else.
**Goal:** dashboard, API, pipeline and ClickStack all working, verified by output rather than by assumption.

> If you are an AI: execute these in order and **check the stated expected output at each step**. Several steps fail *silently* — they return success while doing nothing. Those are called out. Do not skip them and do not assume a command worked because it exited 0.

Companion docs: [`HANDOVER_AND_JURY_PREP.md`](HANDOVER_AND_JURY_PREP.md) (what was built and why), [`CLAUDE.md`](CLAUDE.md) (architecture), [`claude-venkat-branch.md`](claude-venkat-branch.md) (decision record and bug catalogue).

---

## 0. Prerequisites

| need | version used | check |
|---|---|---|
| Node | v24.14.0 (any ≥ 20) | `node -v` |
| npm | 11.9.0 | `npm -v` |
| Docker | 29.6.1, **running** | `docker info` |
| Python 3 | any 3.9+ | `python3 -V` |
| curl | any | `curl --version` |

No ClickHouse install needed — the data lives in ClickHouse Cloud, and the only local ClickHouse is the one inside the ClickStack container.

---

## 1. Credentials

```bash
cd <repo>
cp .env.local.example .env.local
chmod 600 .env.local
```

Fill in `CH_HOST` / `CH_USER` / `CH_PASS` — **ask Venkat**, they are deliberately not in git. Leave the HyperDX values for now; step 5 generates them.

Verify:

```bash
scripts/ch 'SELECT 1'
```

**Expect:** `1`. Anything else means the credentials or the host are wrong — stop and fix before continuing.

---

## 2. Is the data already there?

It should be. The pipeline has already run against Cloud, and Cloud is shared — you are not expected to load anything.

```bash
scripts/ch "SELECT name, formatReadableQuantity(total_rows) AS rows
            FROM system.tables WHERE database='default' AND total_rows > 0
            ORDER BY total_rows DESC FORMAT PrettyCompactMonoBlock"
```

**Expect** roughly:

| table | rows |
|---|---|
| `silver_events` | 905.56 thousand |
| `bronze_events` | 905.56 thousand |
| `gold_ccu_minute` | 105.08 thousand |
| `bronze_content` / `silver_content` | 33.46 thousand |
| `silver_session_dims` | 10.87 thousand |
| `dim_language_map` | 35 |

If those exist, **skip to step 3.** If the tables are missing, see [§9 Rebuilding from raw CSV](#9-rebuilding-from-raw-csv) — and read the warning there first.

---

## 3. Start everything (the normal path)

```bash
scripts/start.sh
```

That is a thin wrapper over `docker compose up -d --build` which first checks your credentials — so a bad `.env.local` fails in two seconds rather than halfway through a demo. First run builds two images and pulls a 2.5 GB one; after that it is seconds.

**Expect:**

```
checking ClickHouse Cloud ... ok
waiting for the API ... 2882

  dashboard   http://localhost:5173
  API         http://localhost:8787/api/summary
  HyperDX     http://localhost:8081     (source dropdown: Logs -> Traces)
```

`peak_ccu = 2882` is the sanity check. Anything else and something upstream changed — investigate before trusting the dashboard.

Three containers, all `restart: unless-stopped`, so they come back by themselves after a reboot or a Docker restart:

| service | port | what |
|---|---|---|
| `web` | 5173 | built dashboard on nginx, proxies `/api` to `api` |
| `api` | 8787 | Express, holds the ClickHouse credentials |
| `clickstack` | 8081 | HyperDX UI + OTel collector + telemetry ClickHouse |

Everyday commands:

```bash
scripts/start.sh status      # or: docker compose ps
scripts/start.sh logs        # or: docker compose logs -f api
scripts/start.sh stop        # keeps telemetry
docker compose down -v       # wipes telemetry, back to first-run
```

**Still do §5 once** — a fresh HyperDX has no OTLP receivers until a team exists.

---

## 3b. Running natively instead (for development)

Compose rebuilds on every code change, which is wrong for editing. For that, run the two apps directly:

### The API

```bash
cd app/server && npm ci
set -a; . ../../.env.local; set +a
node src/index.js
```

**Expect:**

```
TrueCCU API on http://localhost:8787
  telemetry -> http://localhost:4418
```

Check it in another shell:

```bash
curl -s "http://localhost:8787/api/summary" | head -c 300
```

**Expect** JSON containing `"peak_ccu":2882` and a `stats` object with non-zero `readRows`. If `peak_ccu` is anything other than 2,882 on the provided data, something upstream changed — investigate before trusting the dashboard.

---

### The dashboard

```bash
cd app/web && npm ci && npm run dev
```

**Expect:** Vite serving on `http://localhost:5173` with hot reload. You should see the gold **TrueCCU** wordmark, four stat tiles led by **2,882**, a concurrency curve, and two panels beneath.

Vite proxies `/api` to `:8787`, so the API must already be running. Stop the compose `web` and `api` containers first, or the ports collide.

---

## 5. ClickStack (HyperDX) — first-run setup

Compose already started it. `scripts/clickstack.sh up` is the standalone equivalent if you are not using compose.

### ⚠️ The first-run trap — read this or nothing will work

**A fresh container has NO OTLP receivers at all.** They are pushed to the bundled collector over OpAMP only *after a team exists in the UI*. Before that it accepts your spans and silently drops every one — `otel_traces` stays empty with no error anywhere.

1. Open **http://localhost:8081**
2. Register (local only — any email, password needs 12+ chars with upper/lower/number/symbol)
3. Confirm the receivers came up:

```bash
scripts/clickstack.sh status
```

**Expect:** `receivers  OTLP up`. If it still says *NOT configured*, the team was not created — go back to the UI.

4. Grab the ingest key and put it in `.env.local`:

```bash
docker exec trueccu-clickstack sh -c \
  "mongo --quiet --eval 'JSON.stringify(db.getSiblingDB(\"hyperdx\").teams.find({},{apiKey:1}).toArray())'"
```

Set `OTEL_EXPORTER_OTLP_HEADERS=authorization=<that-key>` in `.env.local`, then `docker compose up -d api` so the API picks it up.

**Data survives.** Both ClickHouse and MongoDB are on *named* volumes (`trueccu-clickstack-ch`, `trueccu-clickstack-mongo`), so `down`, a reboot, or a rebuild keep the account, the ingest key and every span. Only `docker compose down -v` wipes them — and then you redo this setup.

### Ports are shifted on purpose

| service | documented | ours | why |
|---|---|---|---|
| HyperDX UI | 8080 | **8081** | 8080 was taken by an unrelated local process |
| OTLP gRPC | 4317 | **4417** | Docker Desktop runs its own collector on 4317/4318 |
| OTLP HTTP | 4318 | **4418** | same |

If any of `8081 / 4417 / 4418` are busy on your machine, edit the constants at the top of `scripts/clickstack.sh` **and** `OTEL_EXPORTER_OTLP_ENDPOINT` in `.env.local`. They must agree.

---

## 6. Verify telemetry end to end

Generate traffic, then look:

```bash
for i in 1 2 3 4 5; do curl -s "http://localhost:8787/api/rollup" -o /dev/null; done
sleep 12
scripts/clickstack.sh spans
```

**Expect** rows for `ServiceName = trueccu-api`, including a `GET` span with `SpanKind = Server`.

> **If `GET`/Server spans are missing but `clickhouse.query` spans are present**, the SDK started too late. `telemetry.js` must be the **first import** in the entry point and it starts the SDK *at import time* — ES modules hoist every `import` above every body statement, so a `startTelemetry()` call between imports loads `express` unpatched and produces no server spans. Do not "fix" this by moving the call.

In the UI: open **http://localhost:8081** → change the source dropdown from **Logs** to **Traces** → widen the time range to *Last 1 hour* → Run.

> **The default view is Logs and it will be empty.** We emit traces and metrics, not logs. That is expected, not a fault.

---

## 7. Run the pipeline (traced)

Read-only verification, safe to run any number of times:

```bash
set -a; . .env.local; set +a
node scripts/run_pipeline.mjs sql/90_verify.sql
```

**Expect** all checks PASS and exit code 0:

```
PASS  check=row_completeness            bronze_rows=905558 silver_rows=905558
PASS  check=beatless_minutes_explained  gaps=5701 gap_minutes=47008 unexplained_gaps=0
PASS  check=gold_matches_silver         gold_peak=2882 silver_peak=2882
PASS  check=session_dims_pinned         0 / 0 / 0
      check=headline                    peak_ccu=2882 peak_minute=2026-07-26 10:56:00
```

A FAIL exits non-zero even though the SQL itself succeeded. That is deliberate — a broken pipeline must not pass silently.

Then see the run's own trace:

```bash
scripts/clickstack.sh trace
```

---

## 8. On the unseen day

Order matters.

```bash
# 1. Profile the new file BEFORE any pipeline work
python3 scripts/profile_dataset.py <unseen-raw.csv> <unseen-content.csv>

# 2. Load bronze
scripts/ch -l bronze_content CSVWithNames < <unseen-content.csv>
scripts/ch -l bronze_events  CSVWithNames < <unseen-raw.csv>

# 3. Build, traced (this IS the evidence)
node scripts/run_pipeline.mjs sql/10_language.sql sql/20_silver.sql sql/30_gold.sql

# 4. Verify
node scripts/run_pipeline.mjs sql/90_verify.sql

# 5. Answers
scripts/ch 'SELECT * FROM v_ccu_summary FORMAT Vertical'
```

**The check that decides whether to trust the output** is `beatless_minutes_explained`. If it drops below 100%, there are minutes with no heartbeat *and* no stop signal — genuine viewing the model will not count, so CCU is understated. Stop and review before submitting.

---

## 9. Rebuilding from raw CSV

> **Only if the Cloud tables are missing.** Normally you never do this.

The CSVs are Git LFS objects in the organisers' repo (`github.com/sidagarwal04/click-a-thon-2026`, `SonyLiv/data`). A plain `git clone` gives 132-byte pointer stubs — you need `git lfs pull` or the LFS batch API.

```bash
scripts/ch -f sql/00_bronze.sql
scripts/ch -l bronze_content CSVWithNames < ch-hackathon-content-data.csv
scripts/ch -l bronze_events  CSVWithNames < ch-hackathon-raw-data.csv
scripts/ch -f sql/10_language.sql
scripts/ch -f sql/20_silver.sql
scripts/ch -f sql/30_gold.sql
```

### ⚠️ `sql/30_gold.sql` is not safely re-runnable

Its DDL is `IF NOT EXISTS`, but the **backfill `INSERT` is not guarded**. Running it twice duplicates gold's stored rows. `TRUNCATE gold_ccu_minute` first.

CCU itself would survive — merging identical `uniqExactState`s is idempotent — but row count and storage would not, and the benchmark numbers would become nonsense.

---

## 10. Everyday commands

```bash
scripts/ch 'SELECT 1'                          # query Cloud
scripts/ch -f sql/90_verify.sql                # run a file, untraced
node scripts/run_pipeline.mjs sql/90_verify.sql  # run a file, traced
scripts/benchmark.sh                           # gold vs silver read comparison
scripts/clickstack.sh up|status|spans|trace|down
cd app/server && node src/index.js             # API   :8787
cd app/web    && npm run dev                   # web   :5173
```

---

## 11. Troubleshooting, by symptom

| symptom | cause | fix |
|---|---|---|
| `scripts/ch` fails immediately | no `.env.local`, or wrong creds | step 1 |
| API starts, dashboard blank | API not reachable on `:8787` | check the API shell; Vite proxies `/api` |
| `otel_traces` empty, no errors | first-run team not created | step 5 — receivers do not exist until then |
| Only `clickhouse.query` spans, no `GET` | SDK started after `express` loaded | `telemetry.js` must be the first import |
| HyperDX "No results found" | you are on the **Logs** source | switch to **Traces**, widen the time range |
| `ports are not available` on `up` | 8081/4417/4418/8787/5173 taken | edit the ports in `docker-compose.yml` (and `.env.local` if you move OTLP) |
| Spans stop when running under compose | `.env.local` points OTLP at `localhost` | compose overrides it to `http://clickstack:4318`; inside a container `localhost` is that container |
| Everything gone after a reboot | container was created without compose | `scripts/start.sh` — compose sets `restart: unless-stopped` |
| Peak is not 2,882 | gold backfilled twice, or data changed | `TRUNCATE gold_ccu_minute`, re-run `30_gold.sql` |
| Dashboard shows an empty chart | range is outside the data | data ends **2026-07-26 11:30 UTC**; presets count back from there, not from today |

---

## 12. Things that are true and surprising

Worth knowing before you conclude something is broken.

- **The data is historical and ends 2026-07-26 11:30 UTC.** Every time preset counts back from *the last minute of data*, not wall-clock now. Anchoring to now would return an empty chart for every preset.
- **There is no data for 15–20 July.** A six-day hole in the middle of the range. The chart draws it as a gap; that is real, not a rendering bug.
- **`gold_ccu_minute` is sparse** — 3,856 populated minutes across a 17,026-minute span.
- **Peak is never stored.** `max()` does not decompose across a filter, so gold holds the series and peak is computed after filtering. Per-platform peaks sum to 2,966 against a true peak of 2,882.
- **Duplicates do not affect CCU.** 4,209 redelivered rows move peak and watch-minutes by exactly zero.
- **`.env.local` must never be committed.** It is gitignored. Rotate the ClickHouse password after the event.
- **ClickStack has no persistent volume.** Removing the container discards every span. Regenerable by re-running, but not recoverable.
