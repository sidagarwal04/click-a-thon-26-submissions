# Replay — As-Built

Two independent mechanisms make a static, past-dated CSV/parquet dump look and
behave like a live stream to ClickStack, without ever storing two copies of the
data. Easy to conflate because both touch `event_time` — they don't overlap.

| Mechanism | Question it answers | Lives in |
|---|---|---|
| **Time shift** | Is there data in the window a wall-clock alert just asked for? | `scripts/replay.sh` (load time, once) |
| **Replay clock** | Given a timestamp, which data-hour and which seasonal bucket is it? | `inmobi.replay_clock` (query time, every render) |

Both read/write **the same single table**, `ad_events_enriched` — see
`CLAUDE.md` rule "EVERYTHING reads this." There is no separate table for
HyperDX; the reasoning for that is in the conversation that produced this doc,
not repeated here.

---

## 1. Time shift — makes the data visible to a wall-clock alert

ClickStack alerts evaluate `WHERE $__timeFilter(ts)` against the wall clock.
The shipped dataset ends `2026-07-05`; an unshifted load can never fall inside
"now," so no alert would ever fire.

`scripts/replay.sh` fixes this once, at load time, by shifting every row's
`event_time` forward by `TIME_SHIFT_WEEKS` whole weeks before it lands in
`ad_events_enriched`:

```sql
SELECT event_time + INTERVAL ${TIME_SHIFT_WEEKS} WEEK, ...
```

- **Whole weeks only.** A partial-week shift misaligns day-of-week, which
  corrupts the weekday/weekend baseline match in `metric_sql.deviation_sql`.
- **Rounded up, not down** (`scripts/suggest_shift.sh`). Rounding down leaves
  the newest event stale by up to 6 days and an alert still can't fire.
  Rounding up puts the tail of the data slightly in the *future* instead —
  harmless, because every query is bounded by `now()`, and
  `investigate.py::get_max_ts()` clamps to `least(now(), max(event_time))` so
  the agent never investigates hours that haven't "happened" yet on the
  shifted clock.
- **One-shot, not reversible without a reload.** It's baked into the stored
  `event_time`, so changing `TIME_SHIFT_WEEKS` means re-running
  `replay.sh --data` (or a full reload), not a config flip.

This is the only mechanism active today. `replay.sh`'s default
(`TIME_SHIFT_WEEKS=4`) is retuned by hand each time the data goes stale enough
that `suggest_shift.sh`'s recommendation changes.

---

## 2. Replay clock — makes bucket and seasonality math agree

`inmobi.replay_clock` (`sql/04_semantic_layer.sql` §4.3) is a one-row config
table, not event data:

```sql
CREATE TABLE inmobi.replay_clock (
    id UInt8 DEFAULT 1, bucket_seconds UInt32, anchor Int64,
    origin_dow UInt8, updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY id;
```

| Field | Meaning |
|---|---|
| `bucket_seconds` | Wall-clock seconds per data-hour. `3600` = real time (default). |
| `anchor` | Unix seconds of data-bucket 0. |
| `origin_dow` | Weekday (0=Mon) of the first data day — needed because a compressed calendar can't be read off the timestamp. |

`RCA/app/registry.get_clock()` reads it (uncached — deliberately, see below).
`RCA/app/metric_sql._clock_exprs()` turns it into three SQL fragments used by
`deviation_sql()`:

- **bucket expression** — which timestamp a row belongs to
- **hour-of-day expression** — for baseline partitioning
- **is-weekend expression** — for baseline partitioning

At the default (`bucket_seconds = 3600`), all three collapse to plain
calendar functions (`toStartOfHour`, `toHour`, `toDayOfWeek`) — i.e. today,
this table is present but inert.

### Both renderers read it, on every call

- `RCA/app/investigate.py::_deviation()` calls `get_clock()` and passes it to
  `deviation_sql()`.
- `scripts/metric_query.py::get_clock(env)` queries the row over HTTP and
  passes it to the same builder for the HyperDX alert/scan SQL.

Neither caches it (`known_dims()` elsewhere in `registry.py` does cache, with
a comment explaining why that's safe — this table is the opposite case: it's
*designed* to be rewritten while the agent's process is still running, so a
cache would go stale exactly when it matters).

**Why both must read the same row:** if the alert bucketed rows one way and
the agent bucketed them another, an hour that alerted as anomalous could
reproduce as clean (or vice versa) purely from a bucket-boundary mismatch —
indistinguishable from an actual "not reproducible" verdict. One row, read
live by both, is what rules that out.

---

## 3. Compression — as built

`scripts/compress_replay.py` sets `bucket_seconds < 3600`. It rewrites
`event_time` for the whole dataset so a data-hour occupies `bucket_seconds`
wall-clock seconds instead of 3600, anchored at `now()`, then updates the single
`inmobi.replay_clock` row to match. At `bucket_seconds = 2`, 840 data-hours
stream past in 28 minutes.

```bash
./scripts/compress_replay.py --bucket-seconds 2
./scripts/provision_alerts.py --apply        # ALWAYS, see below
```

### It is re-runnable, and that took a fix

The obvious implementation derives the data-hour index as
`intDiv(event_time - min(event_time), 3600)`. That is correct **only on
real-time rows**. Run it a second time, over an already-compressed replay where
a data-hour is one second, and `intDiv` by 3600 collapses all 840 buckets into
one — 9M rows at a single timestamp.

This matters because re-running is the normal case, not the exception: the
sealed dataset arrives late and the demo pace gets retuned, and neither can
require a full `replay.sh` reload first. So the script detects its input. A
previous compression is recognisable because its whole span is far shorter than
the calendar hours it claims to cover, and inverting it is exact — `replay_clock`
records the `anchor` and `bucket_seconds` that produced it. `origin_dow` is
carried forward rather than re-read, because a compressed calendar cannot be
read off the timestamps.

### Tiles are rendered against the clock; the agent is not

This is the one coupling that bites. `metric_sql._clock_exprs()` bakes the
bucket, hour-of-day and weekend expressions into the **query text**. The agent
re-reads `replay_clock` on every query, so it follows a clock change for free.
A saved HyperDX tile does not — it holds the SQL string it was created with, and
keeps scoring the previous clock until re-rendered.

**Every compression must therefore be followed by
`./scripts/provision_alerts.py --apply`.** `compress_replay.py` prints that
reminder as its last line.

### Windows are counted in data-hours, never in real time

`metric_sql.window_seconds(buckets, clock)` converts a span expressed in
data-hours into wall-clock seconds. Writing a lookback directly as
`INTERVAL 24 HOUR` or `timedelta(hours=24)` is correct only at real time; at
`bucket_seconds = 2` it reaches past the entire dataset, and the "last 24 hours"
silently becomes all 35 days — which reads as a flat baseline and reports every
real incident as `not_reproducible`.

`metric_sql.lookback_buckets(clock)` additionally widens the agent's window to at
least one alert evaluation. ClickStack's interval enum bottoms out at `1m`, so a
compressed replay cannot be alerted on at its own pace: at `bucket_seconds = 2`
one evaluation covers 30 data-hours. Investigating a narrower window than the
alert scored would drop the anomaly that fired it.

The `time shift` mechanism (§1) is unaffected and still runs first, at load —
compression and the week-shift solve different problems and compose: the
shift gets data into `now()`'s neighborhood once; the clock governs how every
subsequent query interprets time within that data.

---

## 4. Quick reference

```
load time  (once, replay.sh):        event_time += TIME_SHIFT_WEEKS weeks
compress   (re-runnable):            event_time  = anchor + hour_index * bucket_seconds
query time (every render, both):     bucket/hour/weekend ← replay_clock row
```

- Change `TIME_SHIFT_WEEKS` → re-run `replay.sh --data` (rewrites stored rows).
- Change `replay_clock` → the **agent** picks it up on its next query; **HyperDX
  tiles do not**, they hold rendered SQL. Re-run
  `./scripts/provision_alerts.py --apply`.
- Confirm what's active: `SELECT * FROM inmobi.replay_clock FINAL` — anything
  other than `(3600, 0, 0)` means compression is live.
