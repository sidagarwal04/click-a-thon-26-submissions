# Finalized Design Decisions

*Settled in design discussion on 2026-08-01, after profiling (`EVIDENCE.md`), draft design (`DESIGN.md`), adversarial review (`REVIEW-FINDINGS.md`), and prototype validation (`../prototype/RESULTS.md`). These decisions supersede the corresponding draft sections of `DESIGN.md`; a v2 rewrite folds them in when implementation resumes.*

## D1. Correctness contract → foreground **and** playing

> **Revised 2026-08-02.** The original D1 chose "paused-in-foreground counts as active" for parity
> with a benchmark we reconstructed ourselves. That reasoning was circular: the reproduced benchmark
> and the oracle we compared it against were both written to the same assumption, so agreement
> between them proved the encoding faithful and proved nothing about the semantics. It also left the
> repo internally inconsistent — see "The inconsistency this fixes" below.

**Chosen:** A session is active when it is started, not terminated, **foregrounded, and playing**,
with a live heartbeat:

- Counting key = `video_session_id` alone (not `(user_id, video_session_id)`)
- Session span = first event → last event (no clipping at `VideoSessionEnd`)
- **Paused counts as INACTIVE.** `pause` and `error` stop playback; `play` and `resume` restart it
- `error` stops playback but is **not** terminal (`error_is_terminal: false`) — measured: `VideoError`
  never ends a session (293 events, one per affected session; a quality signal)
- Activity/liveness = any event with `event_type ∈ {VideoSessionStart, VideoPlay, VideoHeartbeat, AppForegrounded}`
- Liveness T = 120s; bg **and** pause exclusion both use the wholly-contained-minute rule with
  next-event pairing
- Slices event-attributed (per `(session, dims)` unit), global session-attributed — non-additive by
  design, matching the ground-truth pipeline

**Why pause is inactive** — from the problem statement:

- **¶18, the formal ask:** *"count only truly active **playback** intervals, excluding backgrounded
  periods."* A paused player has no playback; that phrase excludes pause on its own.
- **¶12:** *"backgrounded, **paused**, or silent with no heartbeat. Counting that time overstates the
  audience."*
- **¶22:** groups all three — *"when the heartbeat is missing, **the player is paused**, or the app is
  backgrounded."*
- **¶31:** the dataset ships *"playback-state markers (playing, **paused**, backgrounded,
  foregrounded)"* — they exist to be used.
- **Business rationale:** concurrency drives ad load and capacity. A paused stream serves no ads and
  delivers no viewing.

Counter-evidence, and why it loses: the metric's shorthand name is "foreground-only", and ¶56/¶63
name only backgrounded. But "foreground-only" is a label, and ¶63 (*"overcounting backgrounded time
is the failure mode this whole problem exists to prevent"*) is emphasis on the **primary** failure
mode, not an exhaustive list of exclusions.

**Measured impact** (10,866-session CSV extract, `sonyliv`):

| Peak minute | fg only (old D1) | fg + playing (new D1) |
|---|---:|---:|
| 10:56 UTC | 2,970 | **2,728** (−8.1%) |
| 10:57 | 2,939 | 2,699 |
| 10:58 | 2,940 | 2,677 |
| 10:59 | 2,965 | 2,691 |

Evaluated **instantaneously** rather than per-minute the same definition gives 2,285 — the two differ
only by minute attribution (wholly-contained-minute is permissive: a pause shorter than a minute
boundary excludes nothing). Do not compare those two numbers directly.

### The inconsistency this fixes

Before this revision the repo held two definitions, and the validated one was not the one the newest
code implemented:

| Location | Playback axis | Status |
|---|---|---|
| `prototype/reference/ground_truth_generator.py` | none | the oracle |
| `prototype/pipeline.py` | none | validated: 0 mismatched minutes |
| `docs/DECISIONS.md` D1 (old) | — | mandated the above |
| `solution/policy.yaml` | yes, pause stops playback | contradicted D1 |
| `pipeline/sql/011_build_active_intervals.sql` | yes, gates `playing_state = 1` | newest commit, **never validated** |

`solution/policy.yaml` and `pipeline/sql/011` were already correct and need no change.
`prototype/reference/ground_truth_generator.sql` replaces the `.py` (which could not run) and adds
the playback axis; disabling that axis reproduces the old numbers exactly, so the translation is
verified and the only semantic change is the intended one.

**Rejected:** production-first semantics as primary (user+session key, End-clipping) — risks
systematic divergence from the judges' private answer key; dual parallel tables — double the logic to
defend.

**Kept as documented policy knobs** (each with measured impact): End-clipping (≈ −198
session-minutes; 239 sessions trail events past End), user+session key (120 colliding session ids),
**pause-as-active** (+8.1% at peak, minute-grain), T ∈ {90, 120, 180}s (false-cut 0.253% / 0.201% /
0.157%).

**Residual risk.** The statement is not fully self-consistent and the key is sealed. If it counts
paused-in-foreground, this runs ~8% low at minute grain. Mitigated structurally rather than by
hedging: `play_state` is a separate column everywhere, both series are computed side by side, and
switching the served definition is a one-line change with the alternative already measured. ¶22 poses
pause as a question to the designer, which implies a defended answer is expected — this is that
answer.

## D2. Live freshness → compactor tick only

**Chosen:** One serving path. The "right now" number is the served value at the last compacted minute; compactor cadence 30–60s bounds staleness. The replay demo still shows the curve building live.

**Rejected:** a second live-overlay query on `session_state` — the review showed the draft version was wrong three ways (unmerged aggregate states, missing foreground gate → 9.2% backgrounded contamination, End sentinel mishandling); fixing it means maintaining a second semantics forever. Not worth it for ~45s of freshness.

## D3. OSS integration → both LibreChat+MCP and ClickStack

- **LibreChat + ClickHouse MCP**: conversational layer over the serving tables ("what was peak concurrency on Android in the last hour?") — the problem statement's own suggested fit; demo moment.
- **ClickStack**: observes our pipeline itself — ingest lag, compactor tick latency, serving query performance — and directly feeds the unseen-day "pipeline evidence" requirement.
- Langfuse: skipped (only meaningful with an LLM layer in the data path; weakest fit).

## D4. Benchmark insurance → all three extra scopes

Benchmark queries are unknown until event day; each scope is cheap now, impossible to backfill fast later:
1. **User-level concurrency table** (`concurrency_deltas_users`, user-scoped compactor emission) — the data dictionary names user-level concurrency explicitly; it diverges 3.3% from session-level at peak.
2. **`app_version`** added to the dimension delta key — 65 values, session-constant, listed as a filter dimension.
3. **`audio_language`** added to the dimension delta key — 41 values, genuinely switches mid-session in 16.1% of sessions, so it must be event-attributed like platform.

Resulting dim serving key: `(platform, content_id, app_version, audio_language, m)` + `video_type` denormalized via dictionary; roll-up tables (global, platform) unchanged.

## By-fiat defaults (documented, data cannot decide)

| Knob | Default | Note |
|---|---|---|
| Timezone | UTC everywhere (epoch-seconds arithmetic; `DateTime('UTC')` on Cloud); IST display-only | An IST/UTC mixup already caused a cross-investigator discrepancy during profiling |
| Duplicate Ends | Last-End-wins (argMax) | 4 sessions differ between first/last-End |
| Bot user `4CE58A95…` | Kept at session level; excluded only from user-level metrics | 301 sessions, up to 95 concurrent |
| Missing minutes | Served as explicit zeros via dense-grid reconstruction | 26.3% of naive-active minutes have fg = 0 |
| Unseen-day content misses | `dictGetOrDefault(..., 'unknown')` + dictionary refresh before each compaction | Tuning data had 100% join coverage; unseen day may not |
| Raw heartbeat retention | Keep during hackathon (auditability); note TTL path for the 53.7% trio share | Storage-vs-audit tradeoff |
