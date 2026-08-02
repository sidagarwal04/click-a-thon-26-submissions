# US-17: Live-event concurrency replay (demo)

## The business ask
The demo must show the whole system working live: a match-day stream fed in real time, the concurrency curve **building minute by minute**, and dashboard queries answering instantly. How do we stage that end-to-end?

## The expectation
A stream of session events for a live-event day is replayed so the concurrency curve climbs in near real time as sessions open, heartbeat, and close. A filtered (platform, country) minute-grain query answers instantly, and optionally a chat follow-up is answerable.

## Proof — replaying the India vs Australia match day

1. **Replay:** feed raw events at **60x speed** for the match day.
2. **Curve (live):**
   - 0 viewers before start → **12K at toss** → **342K at first wicket** → drops after the end — updating on the dashboard as events flow.

| Moment | Concurrency |
|---|---|
| Before match | 0 |
| Toss | 12,000 |
| First wicket | 342,000 |
| After end | drops |
3. **Filtered query:** `platform='android' AND country='IN'` at 19:45 → **4,212** in **~40ms** (serving layer, US-12).
4. **Chat (optional):** "Which title had the highest concurrency at 8 PM?" → `"Cricket Live" (342K)` — answered from a real query (US-14).

## Where it can go wrong
- Replaying a full day at 1x speed (demo never shows the live build-up).
- Pre-computing the curve as a static chart instead of letting the pipeline produce it.

## Acceptance Criteria
- Given a stream of session events for a live-event day
- When the demo runs
- Then the concurrency curve builds in near real time as sessions open/heartbeat/close
- And a filtered (platform, country) minute-grain query answers instantly
- And optionally, a chat follow-up question can be answered

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
