# US-06: Exclude backgrounded time

## The business ask
An app in the background is **not watching**. When a session goes to the background and later returns, those inactive minutes must be cut out of the active range so the viewer isn't counted while away.

## The expectation
`AppBackgrounded` ends the active segment; `AppForegrounded` resumes it (confirmed by a subsequent heartbeat). The backgrounded window contributes **0** to every minute in it, and active time resumes correctly after foreground.

## Proof — one session with a background gap

Timeline: start 10:00 → active; `AppBackgrounded` 10:05 → inactive; `AppForegrounded` 10:08 → active resumes; heartbeat 10:09 → still active; end 10:10.

Per-minute active status:

| Minute | 10:00 | 10:01 | 10:02 | 10:03 | 10:04 | 10:05 | 10:06 | 10:07 | 10:08 | 10:09 | 10:10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| active? | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ bg | ✗ bg | ✗ bg | ✓ | ✓ | ✗ end |

- **Active range:** `[10:00–10:05)` + `[10:08–10:10)` = **7 minutes**, not the naive 10.
- **Minute 10:06** contributes **0** (backgrounded) → `[BUILD] concurrency = 0`.
- **Minute 10:09** contributes **1** (foregrounded + heartbeat) → `[BUILD] concurrency = 1`.

### Queries
- **[NOW]** `SELECT event_type, event_timestamp FROM ch_hackathon_raw WHERE video_session_id='...'` — inspect the raw background/foreground events.
- **[BUILD]** concurrency computed from the cut active range.

## Where it can go wrong
- Foregrounding alone without a following heartbeat (US-07) — the resume point must be validated against the heartbeat-gap rule, not assumed.
- Forgetting the second active segment after foreground (counts only `[10:00–10:05)`, losing 10:08–10:09).

## Acceptance Criteria
- Given a session that backgrounds then foregrounds
- When concurrency is computed
- Then the backgrounded window contributes 0 to the count
- And active time resumes correctly after foreground

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
