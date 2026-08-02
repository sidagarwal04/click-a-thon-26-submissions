# US-05: Multiple time grains (minute / hour / day)

## The business ask
A dashboard needs three zoom levels: minute, hour, and day. "What did 20:00 look like?" must roll up correctly from its 60 minutes, and the daily view must roll up from its 1,440 minutes.

## The expectation
All grains come from the same underlying data and agree with each other: **hour = aggregation of its minutes**, **day = aggregation of its hours**. No grain invents numbers the others don't support.

## Proof — one hour, minute vs hour grain

Per-minute concurrency for 19:45–19:59 (excerpt) and the hour to 20:00:

| Minute | 19:45 | 19:46 | … | 19:59 | 20:00 |
|---|---|---|---|---|---|
| concurrency | 4,212 | 4,180 | … | 4,010 | 4,305 |

- **Minute:** query per-minute → `19:45 = 4,212`, `19:59 = 4,010`.
- **Hour (peak):** `max` of the 60 minute values of the 20:00 hour → **4,305**.
- **Hour (average):** `avg` of the same 60 minute values → mean of them.
- **Day (peak):** `max` over 1,440 minute values (or `max` over 24 hour-peaks).
- **Day (average):** `avg` over the 1,440 minute values.

### Queries
- **[NOW]** `toStartOfMinute(event_timestamp)` / `toStartOfHour(...)` / `toDate(...)` — all valid on raw.
- **[BUILD]** pre-aggregated per-grain counts in the serving table.

### Consistency check (do not assume — verify)
| Grain | Peak | Check |
|---|---|---|
| minute 19:45 | 4,212 | source of truth |
| hour 20:00 | 4,305 | = max of its 60 minutes |
| day | max | = max over 1,440 minutes |

If hour ≠ max of its minutes, the aggregation is broken.

## Where it can go wrong
- Rolling up hours with **average** when the dashboard expects **peak** (or vice-versa) — e.g., averaging 4,305 into a day shows a lower number.
- Day = average of hours but hours have different numbers of minutes (never true here — fixed 60 — but worth stating the rule).

## Acceptance Criteria
- Given the same underlying data
- When I query at minute, hour, or day grain
- Then each returns consistent, correct values (hour = aggregation of its minutes)

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
