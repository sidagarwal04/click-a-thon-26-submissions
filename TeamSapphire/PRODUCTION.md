# Production — what changes with real-time ingestion, and what doesn't

`investigate.sh` is a **convenience wrapper, not the system**. It exists so that a full investigation is one command with no remembered steps — which is what makes it safe to put behind an alert hook or a cron entry. The system underneath it is a library, and the shell script is one of four ways to drive it.

This document answers: if data streams in continuously instead of arriving as a file, what actually has to change?

**Short answer: less than you'd expect.** The ingestion path changes and the trigger changes. The analysis doesn't change at all.

---

## 1. The layering

```
  ENTRYPOINTS  (swappable — pick one, or several at once)
  ├── investigate.sh          one-shot, batch. What we demo
  ├── --watch N               continuous polling. Production shape
  ├── POST /api/v1/investigate on-demand via HTTP. What a UI or alert hook calls
  └── import engine           anything else — Airflow, Lambda, a Kafka consumer
                    │
                    ▼
  ENGINE  (engine/*.py — pure functions, no CLI, no file assumptions)
      investigate(db, start, end) -> Investigation
                    │
                    ▼
  CLICKHOUSE  (materialized views keep rollups current on every INSERT)
```

The engine's entire interface is:

```python
from engine.db import DB
from engine.investigate import investigate

inv = investigate(DB(), "2026-06-21 00:00:00", "2026-06-21 23:00:00")
```

No files, no shell, no assumptions about where rows came from. `investigate.sh` is ~20 lines of bash that calls this and prints the result. Delete it and nothing is lost but convenience.

---

## 2. What already works under streaming, unchanged

**The materialized views.** This is the important one. `mv_events_hourly` and `mv_events_hourly_by_dim` are **insert triggers** — they fire on every `INSERT` into `ad_events`, regardless of what produced it. A Kafka consumer, a ClickHouse `Kafka` engine table, an HTTP POST from an edge collector, a batch parquet load: all the same to them.

So under continuous ingestion the rollups stay current **with no batch job, no cron, no recompute**. That is not something we'd need to add for production — it is how it already works, and it is why loading the unseen incident needs no backfill step.

**Everything downstream of the rollups.** Detection, decomposition, localization and the ruled-out ledger read `events_hourly` and `events_hourly_by_dim`. They neither know nor care whether those rows arrived a month ago or four seconds ago.

**Cost.** One pass over a 48-hour window is ~1.2s and ~874K rows read. At a 60-second poll interval that is well under 5% duty cycle on a single connection — you can run this continuously without thinking about it.

---

## 3. What has to change

### a. Ingestion — replace `load.py`

`scripts/load.py` reads a parquet file. In production that's a stream. The standard ClickHouse pattern needs no application code at all:

```sql
CREATE TABLE ad_events_queue (...) ENGINE = Kafka
  SETTINGS kafka_broker_list = '...', kafka_topic_list = 'ad_events',
           kafka_format = 'JSONEachRow';

CREATE MATERIALIZED VIEW ad_events_ingest TO ad_events
  AS SELECT * FROM ad_events_queue;
```

Rows land in `ad_events`, and **our existing MVs fire off that insert exactly as they do today.** The rollups follow automatically. Nothing in `engine/` changes.

### b. Trigger — replace the human

Four options, in rough order of how much infrastructure they need:

| Approach | How | Fits |
|---|---|---|
| `--watch N` | `./investigate.sh --watch 60 --hours-back 48` | A single box, a demo, a pilot |
| Cron / systemd timer | `*/5 * * * * cd /srv/rca && ./investigate.sh --hours-back 48` | Ops teams that already have this |
| Alert-driven | Your monitor fires → `POST /api/v1/investigate` with the window | Best fit: investigate only when something is already wrong |
| Orchestrator | Airflow / Dagster task calling `investigate()` | Shops that already run one |

The alert-driven path is the one the problem statement actually describes — *"An alert already answers 'did it move'. The question is why."* Our detector can serve as the alert too, but it doesn't have to.

### c. Alert deduplication — new concern

Polling a rolling window re-detects a live incident on **every pass**. A 3-day Android 15 outage polled every 60 seconds is 4,320 identical alerts, which is how an on-call engineer learns to ignore you.

`--watch` keys alert identity on `(window_start, classification, headline)` and announces each only once:

```
1 event(s), 1 new · 1243 ms · 873,602 rows read
NEW  [global] Revenue -44.8%, driven by requests falling uniformly ...
1 event(s), 0 new · 1138 ms · 873,602 rows read     ← silent
1 event(s), 0 new · 1156 ms · 873,602 rows read     ← silent
```

In-memory, so it resets on restart. A production deployment would persist this to a table and add resolution detection ("the incident that was open is no longer detected → send an all-clear").

### d. The partial-hour trap — a real bug that batch testing cannot surface

**This is the one that would have bitten us silently.**

Under continuous ingestion the newest hour is always incomplete. Run at 14:30 and hour 14 contains thirty minutes of traffic. Compared against a full-hour baseline that reads as a **~50% collapse** — on every single run, forever.

It is a *confident* false alarm: the arithmetic is correct, the baseline is correct, the comparison is invalid. Exactly the failure mode the whole project is built to avoid.

It never appears in our testing because the provided dataset happens to end on a complete hour (last event at 23:59:59). It would appear within minutes of going live.

The fix: an inferred window now stops one hour short of the newest data, because for an append-only stream an hour is only provably complete once data from a *later* hour exists.

```
default:                 2026-07-04 22:00:00 → 2026-07-05 22:00:00
--include-partial-hour:  2026-07-04 23:00:00 → 2026-07-05 23:00:00
```

An explicit `--end` is still honoured as given — the caller stated the window and owns that choice.

### e. Narration cost and rate

At ~$0.026 per narration, one incident per hour is trivial and one per minute is $37/day. Production should narrate only newly-announced incidents (which `--watch` already tracks) rather than on every pass. The structured diagnosis, which is the part that matters, costs nothing but the query time.

---

## 4. What we would add before calling it production

Honest list — none of these are built:

- **Incident state table.** Persist open/resolved incidents so dedup survives restarts and an all-clear can be sent
- **Backfill-aware baselines.** Late-arriving events mutate hours already analysed; the current design assumes append-only
- **Per-tenant isolation.** One publisher's traffic collapse shouldn't page everyone
- **Alert routing.** The diagnosis is produced; delivering it to PagerDuty/Slack is not built
- **Threshold tuning per metric.** Currently one global gate; production would tune per metric and per segment volume
- **HyperDX/OTel instrumentation of the API** — two lines, would make pipeline latency visible alongside LLM latency

---

## 5. Try it

```bash
# One-shot — what the demo runs
./investigate.sh --start "2026-06-20 00:00:00" --end "2026-06-22 00:00:00"

# Continuous — the production shape, same engine
./investigate.sh --watch 60 --hours-back 48

# On demand over HTTP — what an alert hook or UI button calls
curl -X POST localhost:8010/api/v1/investigate \
     -H 'content-type: application/json' \
     -d '{"start":"2026-06-20 00:00:00","end":"2026-06-22 00:00:00"}'
```

```python
# As a library — anything else
from engine.db import DB
from engine.investigate import investigate
inv = investigate(DB(), start, end)
for event in inv.events:
    print(event.classification, event.headline)
```

All four run the identical analysis. That is the point: the batch demo and the production deployment are not two systems, and there is no rewrite waiting between them.
