# UNSEEN_DAY_RUNSHEET.md — the exact sequence, start to answer

**Use this on the day.** Every step states what to expect, so you know whether to continue or stop. If a judge asks "how do you do it?", this *is* the answer — read it out.

Dataset: `ch-hackathon-raw-data_surprise.csv` (~1.8 GB, 7,000,000 events, 31 July 2026) and `ch-hackathon-content-data_surprise.csv` (~1.4 MB, ~33,000 titles). Two new columns: `video_resolution` on events, `show_name` on content.

**Total expected time: 25–40 minutes**, dominated by the upload.

---

## Step 0 · Bring the stack up (2 min)

```bash
cd TrueCCU
scripts/start.sh
```

Three Docker containers — dashboard, API, ClickStack — all `restart: unless-stopped`. **Expect** `checking ClickHouse Cloud ... ok` and the three URLs. ClickHouse Cloud itself is not containerised: it holds the data and is the mandated engine.

If it prints a credentials failure, fix `.env.local` before going further.

---

## Step 1 · Profile the file BEFORE touching the pipeline (2 min)

```bash
python3 scripts/profile_dataset.py ch-hackathon-raw-data_surprise.csv \
                                   ch-hackathon-content-data_surprise.csv
```

This reads the raw CSV directly and reports data hygiene plus the model's one assumption. **Do this first** — it costs two minutes and tells you whether anything downstream can be trusted.

---

## Step 2 · Add the two new columns (1 min)

```bash
node scripts/run_pipeline.mjs sql/50_add_unseen_dimensions.sql
```

**Expect** `PASS check=unseen_dimensions_added`.

Additive and idempotent — existing rows keep working, existing answers do not move. `video_resolution` goes to the **end** of gold's sort key (§7 of `PERFORMANCE.md` explains why that is both the only legal position and the right one).

---

## Step 3 · Load the data (15–30 min, the long pole)

```bash
scripts/load_large_csv.sh bronze_content ch-hackathon-content-data_surprise.csv
scripts/load_large_csv.sh bronze_events  ch-hackathon-raw-data_surprise.csv
```

**Expect** a per-chunk progress line, then `rows in bronze_events: 7000000 (file had 7000000) MATCH`.

### If a judge asks "how do you load 1.8 GB?"

ClickHouse has **no INSERT size limit** — the HTTP interface streams the body, so 1.8 GB is not the problem people expect. The problems are around it, and the loader addresses each:

| problem | what the loader does |
|---|---|
| One request, all or nothing — a drop at 1.6 GB leaves a half-loaded table with no way to resume | Splits into 500k-row chunks, records each success, **re-run resumes** |
| No progress signal — cannot tell slow from hung | Per-chunk progress line |
| Idle-connection timeouts on a slow uplink | Per-chunk `--max-time`, 3 retries with backoff |
| 1.8 GB over venue wifi | **gzip on the wire**, decompressed server-side — event CSV is highly repetitive and compresses ~8–10×, so ~200 MB actually travels |
| **The new file lists columns in a different order** (`video_session_id,user_id,content_id,…` vs ours) | Sends `CSVWithNames` so columns map **by name, not position**. Positional CSV would have loaded session ids into `content_id` and *succeeded* — wrong data, no error |

It also prints a column diff before uploading a byte, so a mismatch is caught in seconds rather than after twenty minutes.

Each chunk is one INSERT, and ClickHouse INSERTs are atomic per block — a failed chunk leaves nothing to clean up.

---

## Step 4 · Build silver and gold, traced (5–10 min)

```bash
node scripts/run_pipeline.mjs \
  sql/10_language.sql sql/20_silver.sql sql/30_gold.sql sql/40_gold_total.sql
```

**This command is the pipeline evidence.** It emits one trace per run, one span per stage and per statement, each carrying rows read and written. Evidence produced *by* the run, so it cannot be written afterwards. `scripts/ch -f` runs the same SQL but leaves only terminal output anyone could have typed.

> ⚠️ **`30_gold.sql`'s backfill is a bare INSERT.** Running it twice duplicates gold's stored rows. If you re-run it, `TRUNCATE gold_ccu_minute` first. (`40_gold_total.sql` is TRUNCATE-guarded and safe to re-run.)

---

## Step 5 · Verify before believing anything (1 min)

```bash
node scripts/run_pipeline.mjs sql/90_verify.sql
```

**Expect all PASS and exit code 0.** A FAIL exits non-zero even though the SQL succeeded — a broken pipeline must not pass silently.

| check | what a failure means |
|---|---|
| `row_completeness` | silver dropped rows it should only have flagged |
| **`beatless_minutes_explained`** | **the one that matters** — see below |
| `gold_matches_silver` | the serving layer disagrees with its source: broken MV, or a double-run backfill |
| `session_dims_pinned` | dimension pinning did not apply |
| `headline` | the answer (reported, not asserted) |

**`beatless_minutes_explained` is the check that decides whether to submit.** It tests the model's single assumption directly: is a minute with no heartbeat ever a minute of *genuine viewing*? On the provided data every one of 5,701 gaps opens in a minute carrying an explicit `pause` or `AppBackgrounded` — 100%, zero unexplained. **If it drops below 100% on the unseen day, CCU is understated for those minutes** and you say so rather than submitting silently.

---

## Step 6 · Produce the answers (1 min)

The submission asks for peak and average at **minute, hour and day** grain, with dimension filters.

```bash
# headline, all traffic
scripts/ch 'SELECT * FROM v_ccu_summary FORMAT Vertical'

# minute grain
scripts/ch "SELECT minute, uniqExactMerge(sessions) AS ccu
            FROM gold_ccu_total GROUP BY minute ORDER BY minute FORMAT CSVWithNames" > answers_minute.csv

# hour and day grain — peak is the busiest MINUTE inside the bucket, never an
# average of averages
for g in Hour Day; do
scripts/ch "SELECT toStartOf${g}(minute) AS bucket,
                   max(ccu) AS peak_ccu, round(avg(ccu),2) AS avg_ccu
            FROM (SELECT minute, uniqExactMerge(sessions) AS ccu
                  FROM gold_ccu_total GROUP BY minute)
            GROUP BY bucket ORDER BY bucket FORMAT CSVWithNames" > answers_${g,,}.csv
done

# with a dimension filter — note it reads gold_ccu_minute, not the totals table
scripts/ch "SELECT platform, max(ccu) AS peak_ccu, round(avg(ccu),2) AS avg_ccu
            FROM (SELECT platform, minute, uniqExactMerge(sessions) AS ccu
                  FROM gold_ccu_minute GROUP BY platform, minute)
            GROUP BY platform ORDER BY peak_ccu DESC FORMAT CSVWithNames" > answers_by_platform.csv
```

Or drive it from the dashboard at `http://localhost:5173` — same numbers, and every response shows what the query read.

---

## Step 7 · Latency measurements (2 min)

```bash
node scripts/bench_ui.mjs unseen      # 16 shapes x 5 repeats -> .run/bench-unseen.json
scripts/benchmark.sh                  # gold vs the silver equivalent
```

Reports ClickHouse-side elapsed time and bytes read, taken from ClickHouse's own summary header rather than our wall clock — a laptop-to-`ap-south-1` round trip would otherwise swamp the thing being measured.

---

## Step 8 · Pipeline evidence (1 min)

```bash
scripts/clickstack.sh trace     # the most recent run, nested
scripts/clickstack.sh spans     # everything recorded, by service
```

Or open **http://localhost:8081** → switch the source dropdown from **Logs** to **Traces** → widen to *Last 1 hour* → Run.

> The default view is **Logs** and it will be empty — we emit traces and metrics, not logs. Switch the dropdown. This is expected, not a fault.

---

## If something goes wrong

| symptom | do this |
|---|---|
| Upload dies partway | Re-run the same command — it skips loaded chunks |
| `HEADER`/column warning before upload | Read it. A column in the file but not the table gets **dropped**; add it to the table first |
| Row count mismatch after load | Do **not** build silver. Re-run the loader; it will fill the gaps |
| `gold_matches_silver` FAILS | Backfill ran twice. `TRUNCATE gold_ccu_minute`, re-run `30_gold.sql` |
| `beatless_minutes_explained` < 100% | Stop. CCU is understated. Report the number and the caveat rather than submitting silently |
| Dashboard empty | Range is outside the data. The unseen day is **31 July 2026**; presets count back from the last minute of data |
| HyperDX shows nothing | You are on the **Logs** source, or the window is too narrow |

---

## The one-paragraph version, for a judge

> *"We load the CSV into ClickHouse Cloud in resumable gzipped chunks mapped by column name, then run four SQL stages through a traced runner that emits a span per stage and per statement — that trace is our pipeline evidence, and it is produced by the run rather than written afterwards. A read-only verification stage then asserts invariants rather than numbers, so it stays valid on data it has never seen; the one that matters checks whether any beatless minute is genuine viewing, which is the single assumption our concurrency model makes. Answers come from a minute-grain serving layer, with hour and day grain derived as the max over the minutes inside each bucket — peak is never stored, because max() does not decompose across a filter."*
