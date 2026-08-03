# End-of-session comparison with the concurrent draft

The concurrent `docs/` / `prototype/` work was treated as an independent set of
notes and left unmodified. This comparison separates shared architectural ideas
from semantic differences that change the answer key.

## Strong agreement

Both approaches converge on the useful architectural core:

- append-only raw ingestion;
- content enrichment before dashboard serving;
- compact interval/delta representation rather than session×minute history;
- signed corrections for late/open-session changes;
- UTC service-date reset/splitting for bounded prefix sums;
- `SummingMergeTree` serving points;
- a live replay plus observability evidence rather than hand-computed answers.

Those pieces should be retained.

## Differences that materially change correctness

| Decision | Concurrent draft | Independent solution | Evidence/verdict |
|---|---|---|---|
| Pause | Paused foreground time remains active by default (`docs/DESIGN.md`, §2 item 6). | `pause` immediately clears playing. | The problem statement explicitly identifies paused time as overcount. Heartbeats continue after pause, so silence cannot repair this. Use pause-inactive. |
| Foreground | Foreground or a later qualifying event reactivates. | Foreground only changes visibility; it cannot undo pause or renew an expired playback lease. | In policy-aligned lifecycle state, 13,382/14,256 Foreground assignments leave playback stopped and 13,371 retain pause as the latest marker. Treating FG as liveness adds 0.546768h across 152 sessions at TTL120. Keep the conservative independent rule unless judges say otherwise. |
| Time fidelity | Activity is collapsed to distinct minutes and expanded to minute runs (`groupUniqArray(minute)`). | State is evaluated at exact `DateTime64(3,'UTC')` boundaries; minute statistics are derived afterward. | Exact hot-hour in-minute peak is 2,305, while exact minute-boundary sample peak is 2,285. Minute collapse cannot answer both semantics. |
| Content ID type | `UInt64`. | `Int32`. | Content IDs include `-987654322`; UInt is factually incompatible with the supplied data. |
| Session identity | `(user_id, video_session_id)`. | `video_session_id`, with user anchored from SessionStart; distinct-user concurrency is separate and unions session intervals. | The dictionary declares the video session ID unique. The 120 multi-user mappings are row drift; splitting them changes session counts. 775 users have multiple sessions and 61 overlap, proving the user metric needs a separate union. |
| Terminal End | Last End wins (`max`/`argMax`). | First End is terminal; later input remains raw but is excluded from interval state. | Four sessions have different End times; 241 sessions have 870 rows after first End. A terminal event should not reopen merely because anomalous tail rows exist. Confirm with judges if they define otherwise. |
| Raw incremental MV | Commutative minute/activity arrays are the state absorbed directly from raw blocks. | Raw MV only marks dirty IDs; ordered state is recomputed from complete touched-session history. | Incremental MVs see the inserted block only. Unordered minute presence loses pause/play ordering, exact expiry, and same-ms stop precedence. |
| Average | `avg(concurrent)` over zero-filled minute samples. | Integral of exact concurrency divided by elapsed time. | Samples and time-weighted average are different metrics; the public package does not resolve this. The independent policy makes the distinction executable rather than implicit. |
| “Ground truth” | Prototype validates against a locally generated foreground CSV and hard-coded expected peaks. | Calls its output an oracle/reference only and records the policy/source hash. | Judge truth is private. Locally derived expectations must be policy-labeled to avoid circular validation. |

## Measured consequence

For `2026-07-26 10:00–11:00 UTC` under the checked-in 120-second policy:

| Model | Peak semantics | Peak |
|---|---|---:|
| Exact session state | Instantaneous peak inside each minute | 2,305 |
| Exact session state | Minute-boundary sample | 2,285 |
| Session-independent heartbeat lease | Approximate minute-boundary sample | 3,162 |

The heartbeat-only comparison has mean overcount 292 and maximum overcount 938
over the 60 boundaries. This is direct evidence that the playback/foreground
state machine is not an optional refinement.

## Recommended synthesis

Keep the concurrent prototype’s replay/demo shell, correction visibility, and
operational scaffolding. Replace its semantic core and unsigned schema with:

1. `solution/policy.yaml` as the versioned contract;
2. exact event-time touched-session recomputation from
   `solution/sql/10_reference_intervals.sql`;
3. the signed old/new state-map and endpoint path in steps 11–20;
4. exact peak/active-milliseconds and validated minute generations from steps
   30–40;
5. the heartbeat-only path from step 60 as a labeled comparison, not truth.

If judges confirm alternate semantics (Foreground renews liveness, last-End wins,
minute sampling, or pause counts), retain those as separate policy versions and
produce side-by-side answer hashes. Do not mix their assumptions inside one
unversioned “ground truth.”
