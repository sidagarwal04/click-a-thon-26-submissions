# Approach & Thinking Trail

*How this design was produced, in order, with the reasoning at each step. Written 2026-08-01 during the hack window.*

## Method: evidence before architecture

The data dictionary makes claims (60s heartbeats, guaranteed session boundaries, bg/fg "not guaranteed"). Instead of designing against the docs, we profiled the actual 905,558-event dataset first with six parallel investigations (event taxonomy, heartbeat cadence, bg/fg behavior, dimensions/joins, disorder/duplicates, brute-force ground truth), then synthesized the findings into `EVIDENCE.md`. Nearly every load-bearing assumption in the docs turned out wrong or incomplete:

- The periodic heartbeat is a **40s trio** of `{network-activity, buffer-health, video-resize}`, not 60s — and **74.4% of iPhone sessions never emit it**, so any trio-based liveness rule silently drops iOS.
- `event_type='VideoHeartbeat'` is a grab-bag of **41 event names**, including lowercase `pause`/`resume` — pause is invisible at the event_type level.
- **Heartbeats stop when backgrounded** (78.5% of >120s bg windows have zero heartbeats) but continue at ~39% rate during foreground pause → silence detects backgrounding, not pausing.
- Naive session-boundary concurrency **overcounts foreground by 26% at peak** — the measured business case for the whole problem.
- Within-session event disorder is pervasive (99.65% of sessions, p99 lateness ≈ 2.3h) while the file's global order is a layout artifact.
- Every session in the extract is closed — open-session behavior exists **only mid-replay**, so update-friendliness must be demonstrated by replaying the stream, not by the at-rest data.

## The correctness oracle

Before designing the fast path, we computed the slow-but-correct answer: a brute-force per-minute foreground concurrency series (coverage semantics + bg-window exclusion), 3,872 minutes, peak 2,970 at 10:56 UTC. This file (`../prototype/reference/ground_truth_foreground_per_minute.csv`, generator alongside) is the diff contract every candidate design must match exactly. It also fixed the semantics precisely: slices are computed by filtering events first (event-attributed), the global series counts sessions once (session-attributed) — the two are non-additive by design (platform sums 2,982 vs global 2,970 at peak; 95 sessions emit under two platforms).

## Candidate architectures considered

**A. Pure minute-grain pre-aggregation** (`uniqState(session)` per minute × dims, insert-time MV): order-insensitive and simple, but exact dedup of `(session, minute)` across insert blocks is unreliable in pure incremental MVs; exact-uniq states get heavy at 100x peaks; and bg-window exclusion needs cross-event pairing an insert-time MV cannot do. Kept only as the session-independent comparison path the problem README asks for.

**B. Pure interval → delta model** (+1/−1 at active-interval edges, SummingMergeTree, cumsum to serve): exact, tiny (2 rows per interval — storage bounded by sessions, not session-minutes), additive within a scope so filtered peaks work. But "activity stopped" is the *absence* of heartbeats — an insert-time MV can never observe absence. Deltas cannot be emitted at insert time.

**C. Hybrid two-tier (chosen)**: Tier 1 absorbs the raw stream through an insert-time MV into **commutative aggregate states** (min/max/groupUniqArray — any arrival order and any duplication merge to the same state; this is what the measured disorder demands). A **watermark compactor** (30–60s tick) — the component that *can* observe absence — pairs bg/fg, applies the liveness rule, reconstructs foreground intervals per unit, and emits **±1 minute-edge deltas** into SummingMergeTree serving tables, with a ReplacingMergeTree memo enabling incremental corrections (new − old) when late events re-dirty a session. Day-split intervals make every day's cumsum self-contained: bounded reads, clean partition drops, and the unseen day loads as an isolated partition.

Key structural insight: the ground-truth minute-set semantics converts exactly into interval runs in minute space (merge covered minutes into consecutive runs, subtract wholly-contained bg minutes), so the delta model reproduces the oracle *by construction* rather than approximately.

## Validation before commitment

A full prototype was built on chdb (real ClickHouse engine, 26.5): DDL + insert-time MV + compactor + serving queries.

- **Exactness**: 0/3,872 minutes mismatched vs the oracle; slice spot-checks match (ANDROID_PHONE 1,818 and JIO 219 at the global peak minute; JIO's own peak 230 at a different minute — the cross-dimension peak behavior the problem highlights).
- **Latency**: 3–4 ms dashboard-shape queries reading 425 delta rows (global, hot day) vs a raw coverage scan of 906K events — the "what do your queries read" argument, measured.
- **Update handling**: an event-time replay (872 batches) with 1% of events artificially held back 30 minutes converges to **0 diffs** after absorption via correction deltas — avg compactor tick 165 ms. No rebuild anywhere.

## Adversarial review before finalization

Four independent attack lenses (ClickHouse mechanics, semantics-vs-oracle, scale/latency, operations/unseen-day) produced 23 findings; majors/criticals were each re-verified by refuter agents against the real data (`REVIEW-FINDINGS.md`). Confirmed items either became engineering fixes (UTC pinning, dense-grid serving query instead of WITH FILL, compactor atomicity ordering, dictionary defaults) or surfaced the genuine policy decisions that were then settled with the team (`DECISIONS.md`): ground-truth-parity contract, compactor-tick freshness, LibreChat+MCP and ClickStack integrations, and three benchmark-insurance scopes (user-level, app_version, audio_language).

## Where things stand

Design finalized (`DECISIONS.md` + pending v2 fold-in to `DESIGN.md`); prototype validates the core exactly; execution plan captured in `PLAN.md`. A concurrent independent solution exists in `../solution/` for end-of-session comparison — the two were deliberately kept isolated.
