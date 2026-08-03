# Measured evidence ledger

This ledger separates raw-source observations from explicitly scoped
policy-derived results. All calculations used chDB 4.2.1 over the hash-identified
official CSV bytes. Core source-profile queries are in
`sql/05_profile_loaded_data.sql`; end-to-end policy checks are in
`tools/verify_embedded.py`. Extended forensic counts below retain their stated
deduplication, lifecycle, and tie-handling scope.

## Source identity

| Source | Bytes | Data rows | SHA-256 |
|---|---:|---:|---|
| Raw events | 232,827,255 | 905,558 | `15ce6df78e7239820fb9951f2a5c68de2abb47a0950068947e1a0344a0283a96` |
| Content dimension | 1,181,455 | 33,464 | `e013c4958e9b6396f9cc6cd2681bb6944bb65dc810b7f0925f78254ed9c7ddd4` |

The raw event-time range is `2026-07-14 15:43:58.144` through
`2026-07-26 11:30:04.847` UTC over seven non-contiguous dates. July 26 contains
849,888 raw events and 10,517 distinct sessions whose first Start is on that
date, so whole-file daily averages are not a representative load benchmark.

Both source timestamp columns are 13-digit integers on every row. Of the
905,558 values, 904,654 `event_timestamp` values and 904,738
`session_start_epoch` values have non-zero millisecond remainders, establishing
that `DateTime64(3)` precision is required. The transport contract is therefore
Unix epoch milliseconds; ingestion converts it once to a UTC native timestamp.

`Asia/Kolkata` rendering changes the calendar date for 6,140 events (0.6780%)
across 34 sessions. Twenty-four SessionStart rows (0.2209% of 10,866 sessions)
would move to another raw partition. On July 26 alone, the event-date totals are
849,888 under UTC and 852,625 under India civil time. This measured difference
is why persisted service dates are explicitly UTC and local time is query-only.

## Population and shape

| Measure | Observed |
|---|---:|
| Raw events | 905,558 |
| Video session IDs | 10,866 |
| User IDs anywhere in events | 9,618 |
| Canonical users on SessionStart | 9,510 |
| Raw content IDs | 3,357 |
| Heartbeat rows | 843,600 (93.158%) |
| Rows/session (raw) | p50 53; p90 180; p99 434; max 1,803 |
| First-Start-to-first-End duration (`quantilesExact`) | p50 712.366s; p90 1,990.162s; p99 4,447.120s |
| Sessions longer than 1h / 4h / 24h | 150 / 16 / 1 |
| Longest session | 157,101.184s (43.64h) |

Event types: 843,600 `VideoHeartbeat`, 14,700 `AppBackgrounded`,
14,321 `AppForegrounded`, 10,883 `VideoPlay`, 10,881
`VideoSessionEnd`, 10,880 `VideoSessionStart`, and 293 `VideoError`.

## Disorder and duplicates

- 4,209 excess exact rows occur across about 3,412 duplicate groups and 862
  sessions; maximum multiplicity is six.
- `(session, timestamp, event_type, event)` removes 4,210 rows. The one extra
  conflict differs in subtitle payload, so payload selection must be explicit.
- Deduplicating `(session, timestamp)` would remove 211,766 rows from 161,660
  tied groups. At least 159,433 groups contain legitimate different events.
- In packaged CSV order, 264,998 rows (29.264%) are behind the prior event-time
  maximum for their session, affecting 10,828 sessions. Lag versus that prior
  maximum is p50 70.247s, p90 1,806.664s, p99 8,307.742s, and maximum
  155,764.222s (43.27h).
- Only 5,556 sessions physically start with their Start row, and only 4,281
  physically finish with their End row.

The file has no arrival timestamp. These values prove that batch replay must
sort by event time; they do **not** identify a production watermark. Production
must measure `ingested_at - event_time` directly.

## Lifecycle and state evidence

- After semantic deduplication, every supplied session has one distinct Start,
  one distinct Play, and at least one End. Four sessions have two non-identical
  End timestamps; the supplied snapshot contains no no-End session.
- After semantic deduplication, 241 sessions have 870 rows after the first End;
  239 sessions have 799 rows after even the latest End. Post-End input is an
  anomaly, not evidence that a terminal lifecycle should reopen.
- Coalescing same-millisecond pause/resume assignments with stop-wins leaves
  9,768 adjacent `resume -> resume` transitions and 423 `pause -> pause`
  transitions.
- Within first-Start/first-End lifecycle windows, 13,382 of 14,256 coalesced
  Foreground assignments leave playback stopped; 13,371 have pause as the latest
  playback marker. Foregrounding therefore cannot imply playing.
- At timestamps whose post-assignment foreground state is backgrounded, 2,014
  coalesced pause assignments and 309 coalesced resume assignments occur.
  Foreground and playing must be independent booleans.
- Of 293 errors, 238 are immediately followed by End and 288 have no later
  Play/resume. Treating Error as a playback stop is strongly supported; making
  it terminal is not established.
- The problem statement explicitly names paused time as inactive. Heartbeats
  continue after pause, so heartbeat freshness alone is insufficient.
- Eleven first-Start-to-first-End lifecycles cross UTC midnight and one crosses
  two; zero normalized active intervals cross midnight under the checked
  120-second policy.

Representative session `94D660...` starts, plays, emits telemetry, pauses at
800.944s, backgrounds at 827.440s, foregrounds at 830.641s, emits a heartbeat at
857.629s, then ends. Foreground and heartbeat do not erase the prior pause.

## Heartbeat evidence and sensitivity

`VideoHeartbeat` contains 47 event values, not one uniform clock. The clean
`network-activity` signal has 166,974 consecutive gaps: median 40.003s, p90
40.012s, and about 67% in [39s, 41s]. `video-resize` and iPhone
`network-bandwidth` show the same cadence. The data dictionary nevertheless says
the production heartbeat is currently every 60 seconds.

A periodic whitelist of `network-activity`, `buffer-health`, `video-resize`, and
`network-bandwidth` covers 10,847 of 10,866 sessions. The policy uses any
non-pause `VideoHeartbeat` as a liveness observation because the event type is
the documented heartbeat channel; stop markers still control playback state.

Sensitivity using exact dedup, event-time order, first-End terminal, independent
foreground/playing state, pause/error as stops, and an active-only heartbeat
lease:

| Model | Active hours | Share of naive session duration |
|---|---:|---:|
| Start-to-End overlap | 2,972.122 | 100.000% |
| Foreground + playing, no lease | 1,798.160253 | 60.501% |
| 60s lease | 1,773.598929 | 59.675% |
| 90s lease | 1,777.090138 | 59.792% |
| 120s lease | 1,779.502796 | 59.873% |

Relative to explicit foreground-and-playing time, 60/90/120 seconds retain
98.6341%/98.8282%/98.9624%, shortening 665/427/347 sessions. At 60 seconds,
retention varies from 99.94% on Mweb to 88.45% on Samsung HTML TV. A timeout is
therefore a configurable field policy, not a fact that this closed extract can
uniquely reveal.

These values use the checked-in rule that `AppForegrounded` changes only
visibility and does not renew liveness. If Foreground is instead treated as a
liveness signal, the 120s total becomes 1,780.049563h (+0.546768h across 152
sessions). That alternate assumption explains the prior sensitivity estimate;
it is not a query discrepancy.

## Dimensions and content

| Dimension | Cardinality |
|---|---:|
| Platform | 10 |
| App version | 65 |
| Country | 1 (`india`) |
| Audio language | 41 exact; 26 lower/trim-normalized |
| Subtitle language | 11 exact; 8 normalized |
| Player version | 14 |
| Content category | 84 |
| Content title | 30,508 |

- Content has 33,464 rows and 33,464 unique IDs. Every one of the 3,357 used IDs
  matches exactly once; 30,107 content rows are unused in this extract.
- Content IDs span `-987654322..2078179327`, proving `Int32` fits the supplied
  universe and `UInt32` is wrong.
- Used event rows split into 778,455 VOD, 101,293 live, and 25,810 with blank
  video type. Blank is retained as explicit `__unknown__`.
- There are 4,317 observed start-anchored
  `(platform,country,content_id,video_type)` combinations, making benchmark-mask
  materialization bounded on this dataset.
- Static-dimension drift versus SessionStart affects user in 120 sessions,
  platform in 95, content in one, app version in zero, and country in zero.
  Audio/subtitle/player values are genuinely stateful and must not be silently
  treated as session constants.

## Session versus user concurrency

- 775 canonical users have more than one session and 61 have overlapping
  session lifetimes.
- One synthetic user owns 301 sessions and reaches 98 simultaneous open
  sessions.

Session concurrency and distinct-user concurrency are materially different.
Distinct users must be computed by unioning a user's intervals per requested
dimension mask before boundaries are emitted.

## Verified exact versus session-independent baseline

The checked embedded verifier emitted all ten configured rollup-mask boundary
maps for both session and user entities. It built, published, parity-checked, and
dashboard-queried a minute generation only for `entity=session, rollup_mask=0`;
validation additionally compared global mask-0 and platform mask-1 boundary
points. The remaining masks and the user minute cache were not independently
validated end to end. Under policy `sonyliv-active-v1` with a 120s lease:

- Source-wide global session state has 31,947 active intervals across 10,848
  sessions and 1,779.502796 session-hours.
- The hot `2026-07-26 10:00–11:00 UTC` exact in-minute peak is 2,305 and exact
  time-weighted average is 855.578199.
- The exact minute-boundary sample peak is 2,285. The session-independent
  heartbeat-lease estimator peaks at 3,162, with mean overcount 292 and maximum
  overcount 938 across the 60 boundaries.
- Exact endpoint query and minute cache agree. Invalid/overlapping/post-End
  intervals, negative prefix points, unbalanced days, global/platform delta
  mismatches, and content misses are all zero. Cache active-milliseconds equal
  clipped reference interval milliseconds (`6,018,191,556`) for July 26.
- A deterministic late pause at `2026-07-26 10:27:46.358 UTC` dirties exactly
  one session and emits 320 unique compensating rows (160 session, 160 user)
  with signed row sum zero. The current state table, corrected serving curve,
  and a fresh full-source rebuild each produce exactly `6,404,143,590` active
  milliseconds.
- The corrected generation passes exact per-minute parity and all full-source
  gates, changing the hot-hour result to peak 2,304 and average 855.041077.
  Republishing the same adjustment batch and rebuilding the same generation are
  both rejected; a partial-minute cache request is also rejected for exact-query
  routing.
- Generation 1's sealed ledger/point fingerprint and exact/cached query hashes
  remain unchanged after generation 2. Identical attestation retries remain one
  logical claim; a second conflicting claim and a post-attestation candidate row
  are both rejected with zero manifest rows.
- A separate replacement-boundary fixture emits four rows with four unique
  operation IDs. At the shared old-end/new-start timestamp, two distinct rows
  sum to the required `+2`; the batch ledger publishes exactly once. This guards
  against collapsing distinct correction causes that happen to share a final
  signed delta.

These are correctness results from embedded ClickHouse, not target-Cloud latency
claims. The full record is `evidence/embedded-verification.json`.

## Sizing consequence

With the checked-in state machine and 120-second setting, the global session
mask yields 31,947 normalized active intervals and 63,894 endpoints: 14.17x
fewer contributions than raw events before timestamp aggregation. That narrow
mask alone scales linearly to about 6.39M endpoints at 100x.

The configured serving design deliberately fans those intervals across ten
session masks and ten distinct-user masks. The checked run emitted 1,268,514
signed adjustment rows and sealed 1,263,018 non-zero logical points. A simple
100x framing is therefore about 90.6M raw events, 6.39M global-session
endpoints, and 126.9M configured adjustment rows—not 6.39M rows for the whole
serving layout. These are sizing proxies, not benchmark results; real scale
tests must report `system.query_log` rows/bytes and wall latency.
