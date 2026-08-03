# TrueCCU — handover and jury prep

**Click-a-thon 2026 · SonyLIV track**
**For:** a teammate picking this up cold, and anyone who has to defend it in front of judges.

Read this once end to end. To *run* things, use [`CLAUDE_RUNBOOK.md`](CLAUDE_RUNBOOK.md); on submission day, [`UNSEEN_DAY_RUNSHEET.md`](UNSEEN_DAY_RUNSHEET.md); for why the schema is shaped as it is, [`PERFORMANCE.md`](PERFORMANCE.md). For the decision trail and every bug worth not rediscovering, [`claude-venkat-branch.md`](claude-venkat-branch.md).

---

## 1. The one-paragraph version

Sony gave us two static CSV files. They are loaded into **one ClickHouse Cloud database** and moved through three layers — **bronze** (raw, untouched), **silver** (cleaned, corrected, row-complete), **gold** (a minute-grain concurrency serving layer). An Express API reads gold; a React dashboard reads the API. A second, separate ClickHouse — inside a local **ClickStack/HyperDX** container — stores telemetry about the pipeline and the API. **Peak concurrency on the provided data is 2,882 sessions at 2026-07-26 10:56 UTC**, verified three independent ways.

---

## 2. What we were given, and what "real-time" means here

Two files, delivered as Git LFS objects:

```
ch-hackathon-raw-data.csv       905,558 rows   232 MB
ch-hackathon-content-data.csv    33,464 rows   1.2 MB
```

**There is no live source and no upstream database.** The problem statement talks about streaming because that is the *production* shape at SonyLIV. For the hackathon it is simulated. If someone asks "which Kafka topic?" — there isn't one.

The data covers **2026-07-14 15:44 → 2026-07-26 11:30 UTC**, and 94% of it lands on the final day. There is **no data at all for 15–20 July**.

---

## 3. The concurrency model

> **A minute counts for a session if that minute contains at least one `event_type = 'VideoHeartbeat'` row.**
> `CCU(minute) = count of distinct sessions with ≥1 heartbeat in that minute`

No timeout. No grace period. No gap rule. No state machine.

**Jury ruling (binding):** real-time CCU per minute uses heartbeat rows only. `pause` / `resume` / `AppBackgrounded` / `AppForegrounded` must **not** gate concurrency — those events are known to go missing. They remain available for other analytics.

### The numbers

| metric | value |
|---|---|
| **Peak concurrent sessions** | **2,882** @ 2026-07-26 10:56 UTC |
| Peak unique users | 2,807 (75 sessions at peak belong to a repeat user) |
| Total watch-time | 135,929 session-minutes (2,265 h) |
| Naive (any open session) | 3,743 @ 10:59 · 189,429 min |

Verified three ways that agree exactly: Python over the raw CSVs, SQL in ClickHouse, and the live API.

**Superseded figures — do not quote:** 3,035, 3,115, 2,937.

### How we validated the model — and a justification we had to retract

The risk is a minute of genuine viewing with no heartbeat: it gets dropped and CCU is understated *silently*.

We originally justified the model with cadence — *"beats arrive every ~40s, p99 48.8s, so no active minute can be empty."* **That argument does not survive contact with the data**, for two reasons found by executing it rather than reasoning about it:

- One beat instant emits **several rows** (`network-activity`, `buffer-health`, `video-resize` at the same millisecond), so row-to-row gaps are mostly 0s and any percentile over them is meaningless.
- Beatless minutes **exist anyway**: 47,008 of them, **25.7%** of all minutes sessions span.

So we measure the failure mode directly instead. Of the **5,701** gaps in heartbeat coverage inside a session — all 47,008 minutes — **every single one opens in a minute that also carries an explicit `pause` or `AppBackgrounded`. Zero unexplained.**

That is a *stronger* result: minute-presence does not approximate foreground viewing on this data, it **coincides** with it. It also explains the naive-vs-model gap: 189,429 − 135,929 is largely paused and backgrounded minutes.

`sql/90_verify.sql` check 2 asserts exactly this on any dataset.

---

## 4. Architecture

```
ch-hackathon-*.csv ──HTTP INSERT──► ClickHouse Cloud
                                     bronze_events / bronze_content
                                          │  10_language.sql
                                          │  20_silver.sql   (batch)
                                          ▼
                                     silver_events  (905,558 rows, row-complete)
                                          │  mv_gold_ccu_minute   (materialized view)
                                          ▼
                                     gold_ccu_minute (105,083 rows, 2.5 MiB)
                                          │
                    Express API :8787 ────┘
                          │
                    React dashboard :5173

  API + pipeline ──OTLP──► ClickStack container ──► HyperDX UI :8081
                            (its own ClickHouse, telemetry only)
```

**Two ClickHouse instances that never touch.** Cloud holds the SonyLIV data. ClickStack's bundled ClickHouse holds telemetry and contains **zero** SonyLIV tables. Separated so observability volume never competes with the data being measured.

---

## 5. What silver corrects

**Row-complete: 905,558 in, 905,558 out.** Nothing deleted; destructive judgements are exposed as flags, so both the corrected and the as-delivered readings stay available.

| # | correction | scale |
|---|---|---|
| 1 | Exact duplicates **flagged**, not dropped | 4,209 (0.465%) |
| 2 | epoch-ms → `DateTime64(3)` | all rows |
| 3 | Languages → BCP 47 shortest subtag (`hin`→`hi`) | 41 variants → 15 |
| 4 | Content blank `video_type` → `vod` | 1,089 titles |
| 5 | Odd `content_id`s kept and surfaced, not deleted | 1 |
| 6 | `platform`/`user_id`/`content_id` pinned per session | 95 / 120 / 1 |
| 7 | `player_version` left as-is including blanks | 1,534 |

Flags: `is_heartbeat`, `is_state_marker`, `is_post_session_end`, `is_duplicate`.

---

## 6. Gold — the serving layer

`gold_ccu_minute`, minute × dimension grain, fed by a materialized view.

- **`uniqExactState`, not `uniqState`.** The latter is HyperLogLog — approximate. Against a private ground truth that is a correctness risk for no benefit at this scale.
- **Why distinct-count at all.** `platform`/`content_id`/`video_type`/`category` are pinned per session so their session sets are disjoint and `sum()` would be exact — but `audio_language` is **not** pinned (81% of sessions change it mid-session), so a session splits across rows in one minute and summing would double-count.
- **Peak is never stored.** `max()` does not decompose across a filter predicate.

**Benchmark** (`scripts/benchmark.sh`), gold vs the silver equivalent:

| query | gold | silver | reads less |
|---|---|---|---|
| `peak_platform` | 11.21 MiB / 18ms | 56.20 MiB / 37ms | **5.0×** |
| `peak_platform_type` | 11.27 MiB / 18ms | 56.81 MiB / 36ms | **5.0×** |
| `top_content` | 17.86 MiB / 38ms | 61.54 MiB / 44ms | 3.4× |
| `hourly_rollup` | 18.67 MiB / 21ms | 62.62 MiB / 40ms | 3.4× |
| `series_2h` | 17.19 MiB / 21ms | 55.43 MiB / 36ms | 3.2× |

---

## 7. ClickStack

Self-hosted from ClickHouse's official `hyperdx-all-in-one` image. **ClickStack and HyperDX are the same stack** — ClickHouse acquired HyperDX; HyperDX is the UI layer. Inside one container: the UI, an OpenTelemetry collector, a ClickHouse for telemetry, and MongoDB for HyperDX's own config.

**What is instrumented, and what deliberately is not.** Not query latency, bytes or errors *as the point* — `system.query_log` already has all three at higher fidelity, and duplicating it is the "superficial inclusion" the rubric warns against. It exists for what query_log structurally cannot do:

| | |
|---|---|
| Cross-system attribution | one trace = browser → API → ClickHouse. Real example: `GET` 84.8ms → `clickhouse.query` 84.3ms → `POST` 83.7ms, so API overhead is ~1ms and the wait is the round trip |
| Pipeline run evidence | one trace per run, one span per stage and statement, each with rows read/written |
| Freshness lag | event time → queryable time, as a histogram. query_log records when the INSERT ran, never how stale the row was |
| A UI judges can open | HyperDX |

**Fail-open always** — collector down or `OTEL_SDK_DISABLED=true` and everything behaves exactly as before.

---

## 8. The dashboard

Vite + React + TypeScript, 68 KB gzipped, **no chart library** — hand-rolled SVG, nothing from a CDN. SonyLIV palette, dark by default, validated with a palette validator rather than by eye (CVD ΔE 32.0 dark / 29.9 light against a target of 8).

Panels: time range → four stat tiles → minute-grain chart with optional distinct-users overlay → per-dimension peak bars (click to filter) → time rollup.

Things worth demoing:

- **Drag on the chart to zoom.** It does not crop the viewport — it emits an absolute range that re-filters everything, so tiles, breakdown and rollup all follow, and the query-cost strip shows the read shrink with it (97,423 → 49,152 rows on a 6h → 31m zoom).
- **The query-cost strip** is on screen deliberately: the rubric says judges inspect what a query *reads*.
- **The rollup grain adapts** to the range (minute → … → year) so a year is 13 bars, not 8,760 rows.

---

## 9. What we did NOT do

Say these plainly if asked. Each has a reason.

| not done | why |
|---|---|
| **No Kafka / streaming ingest** | there is no live source; the data is two static files |
| **bronze → silver is batch, not incremental** | two corrections are session-scoped (`row_number()` over a session, and a `GROUP BY video_session_id` join) and cannot be computed from one insert block. See §10 Q3 |
| **No browser-side spans** | API→ClickHouse is instrumented; browser→API is inferred, so cross-system attribution is two-thirds done |
| **No AI agent** | optional; blocked on an LLM API key |
| **No logs in ClickStack** | we emit traces and metrics only, so HyperDX's default Logs view is empty |
| **Benchmark query set not the organisers'** | it was absent from their package; our six shapes are inferred from the problem statement |
| **No calendar grains past `year`** in the rollup | months are not fixed-length; would need a separate `toStartOfMonth` path |
| **`ranga/ddl` not merged** | his codecs and `FixedString(64)` are worth adopting; his `content_id UInt32` cannot hold our negative id, and his `substring(lower(x),1,3)` leaves `jap`/`jpn` split |
| ~~No persistent volume on ClickStack~~ | **fixed** — named volumes for both ClickHouse and Mongo, so spans, the account and the ingest key survive restarts |
| **Two modelling decisions open** | the 802 post-`VideoSessionEnd` events, and whether a mid-session audio switch splits attribution — both Ranganadh's call |

---

## 10. Jury questions, with answers

### Q1. "How do you know 2,882 is right?"

Three independent computations agree exactly: Python directly over the raw CSVs, SQL in ClickHouse, and the live API. `sql/90_verify.sql` also asserts gold agrees with a direct silver query on every run — that is the check that catches a broken materialized view or a double-run backfill, the failures that produce a plausible-looking wrong answer rather than an error.

### Q2. "Why not just count sessions that are open?"

That is the naive number: 3,743. It counts sessions that are open but not being watched — paused, backgrounded, or long finished. The jury ruling is that heartbeats are the liveness signal, and 100% of our beatless minutes are explained by an explicit pause or background event. 189,429 naive watch-minutes against 135,929 measured is that difference.

### Q3. "How would this run in real time?" ← **expect this one**

**Lead with the model, not the plumbing.** Most concurrency implementations compute intervals: open a session, hold it in memory, close it on an end event or timeout. That is painful in a stream — you track open sessions, set watermarks, and reprocess on late arrival.

Minute-presence has none of that, and three properties fall out:

1. **Idempotent under redelivery.** Every streaming system gives at-least-once delivery. Our data already contains 4,209 redelivered rows, and removing them changes peak CCU from 2,882 to 2,882 and watch-minutes from 135,929 to 135,929 — **exactly zero difference**. A replayed Kafka partition cannot corrupt the answer.
2. **Order-independent.** `uniqExactState` merges are commutative and associative.
3. **Late arrivals need no handling.** A heartbeat arriving an hour late for 10:56 merges into 10:56's state. No watermark, no window reopening.

**What already works:** silver → gold is a materialized view. We inserted one late heartbeat and the minute moved **2,882 → 2,883** automatically, with `system.mutations` showing *nothing* on the data path — no rebuild.

**What doesn't, and why:** bronze → silver is batch because duplicate flagging uses `row_number()` across a session and dimension pinning joins a whole-session aggregate.

**The production design:** Kafka → ClickHouse (Kafka engine or ClickPipes), then split the corrections by scope. Row-local ones (epoch→DateTime, language normalisation, `is_heartbeat`) become a materialized view — that is everything CCU needs. Session dimensions become an `AggregatingMergeTree` of `argMaxState(platform, event_ts)` per session, converging as the session runs. **Deduplication does not belong in the hot path at all** — we measured that it does not affect the answer — so it becomes a periodic correction pass for the analytics that care about event volume.

### Q4. "Why is peak not pre-computed per dimension?"

Because `max()` does not decompose across a filter — different slices peak at different *minutes*. Over a 6-hour window the ten per-platform peaks add to **2,966** against a true peak of **2,882**, an 84-session overstatement, because ANDROID_PHONE and IPHONE do not crest in the same minute. A stored peak would be wrong for every filter combination it was not computed for, and there are more combinations than rows. Gold stores the series; the API applies `max()` *after* filtering.

### Q4b. "Show me your sort keys are actually optimal."

Measured with `EXPLAIN indexes=1`, one dimension filter at a time over the same minute range: with no filter, 7/12 granules survive; with `platform` (2nd in the sort key) **2/12**; with `video_type`, `app_version` or `player_version` — 7/12, identical to no filter. **Only the column immediately after `minute` prunes**, because `minute` is a range predicate and later columns are interleaved within it.

So `minute` leads (every query filters on it, and it is the most selective), `platform` takes the one remaining pruning slot, and everything after it is ordered for compression only. The nine dimensions cannot be dropped from the key for speed — `ORDER BY` *is* the merge key of an `AggregatingMergeTree`, so removing one would merge rows that must stay separate. Full reasoning and numbers in `PERFORMANCE.md`.

### Q5. "Why ClickStack when ClickHouse already logs queries?"

It would be redundant if we shipped query latency into it — that is why we deliberately did not. `system.query_log` cannot do cross-system attribution (was the slow filter the browser, the API, or ClickHouse?), cannot measure event-time-to-queryable-time, and is not a UI. Those are the four things we instrumented.

### Q6. "Show me the pipeline actually ran."

`node scripts/run_pipeline.mjs sql/90_verify.sql`, then `scripts/clickstack.sh trace`. One trace per run, one span per stage and per statement, each carrying rows read and written. The evidence is produced *by* the run, so it cannot be written afterwards. `scripts/ch` runs the same SQL but leaves only terminal output anyone could have typed.

### Q7. "You dropped rows to make the numbers look better."

The opposite. Silver is **row-complete** — 905,558 in, 905,558 out. Duplicates are *flagged*, not deleted, because duplication is not uniform (5.103% on Mweb vs 0.078% on JIO_ANDROID_TV, a 65× spread) so leaving them in distorts cross-platform comparison — but the judges' ground truth may have been computed on raw data and the key is private. Flagging retires both risks for one `UInt8`, and both readings stay available.

### Q8. "What breaks on the unseen day?"

The one assumption is that a beatless minute means the user stopped watching. `sql/90_verify.sql` check 2 tests it directly and reports unexplained gaps. If that drops below 100%, CCU is understated for those minutes and we would say so rather than submit silently. Everything else is invariant-checked, not number-checked, so it stays valid on data it has not seen.

### Q9. "Why ClickHouse Cloud rather than local?"

The problem statement mandates ClickHouse as the primary datastore and analytical engine. Cloud also gives `SharedMergeTree` and a real network hop, which is what makes cross-system tracing meaningful — a local instance would hide the latency the dashboard actually pays.

### Q10. "What would you do with another week?"

In order: make bronze→silver incremental so the real-time claim is demonstrated rather than described; add browser-side spans to close cross-system attribution; merge `ranga/ddl`'s codecs and `FixedString(64)`; add logs alongside traces; and build the synthetic harness for open sessions, which the provided data cannot exercise because it contains zero of them.

### Q11. "Is the dashboard reading live, or is it a fixture?"

Live. Every response carries what ClickHouse actually read, straight from its own summary header, and it is on screen. `/api/summary?platform=IPHONE` returns 347 @ 10:58 having read 105,083 rows; the same SQL run directly against gold returns 347 @ 10:58. `system.query_log` on the server shows the query arriving over HTTP.

### Q12. "Why is the chart empty when I pick today?"

The data is historical and ends 2026-07-26 11:30 UTC. Every preset counts back from the last minute of data, not from now — anchoring to now would return an empty chart for every preset. The picker states its window and disables dates outside it.

---

## 11. Known weak points — be honest about these

If you are asked and you bluff, it will go worse than if you name them first.

1. **bronze → silver is batch.** The real-time story is a design, not a running system. §10 Q3 has the honest framing.
2. **The benchmark query set is ours, not the organisers'.** Their set was missing from the package. Our six shapes determine whether the gold ordering key is optimal, so the conclusion is provisional.
3. **`system.query_log` is per-replica on Cloud.** Benchmarks must read `clusterAllReplicas(default, system.query_log)` or they return a partial, non-deterministic subset. This cost us two confusing report passes.
4. **The provided data has zero open sessions and zero missing background markers.** Both cases only appear on the unseen day, so incremental-update handling cannot be fully tested as-is.
5. **ClickStack is localhost-only.** Data now persists across restarts on named volumes, but it is still a laptop service, not a deployed one — judges see it on your screen.
6. **Full-range chart is downsampled.** Above 6,000 minutes of span the series is bucketed keeping each bucket's maximum. Peak is exact; troughs are flattened, so the curve reads slightly busier than reality between peaks. The UI says so.

---

## 12. Ownership

| area | owner |
|---|---|
| bronze → silver, gold, API, dashboard, ClickStack | Venkat |
| concurrency modelling decisions, DDL branch | Ranganadh |
| the two open modelling calls (§9) | Ranganadh |

**Housekeeping:** `.env.local` is gitignored and must stay that way. **Rotate the ClickHouse password after the event** — it was pasted into a chat transcript.
