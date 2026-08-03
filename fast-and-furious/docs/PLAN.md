# SonyLIV Click-a-thon: Finalized Design → Execution

## Context

Hackathon problem: foreground-only concurrency at streaming scale on ClickHouse — judged on correctness vs a private answer key, query latency (what queries read), incremental update handling, design defense, and an unseen day of data flowing through the pipeline.

This session already produced (all uncommitted): `docs/EVIDENCE.md` (measured profiling of the real 905K-event dataset), `docs/DESIGN.md` (draft architecture), and a validated chdb prototype (`prototype/pipeline.py|validate.py|replay.py`) whose serving layer matches brute-force ground truth **exactly (0/3,872 minutes)** at 3–4 ms per dashboard query, converging under a late-event replay stress test. An adversarial review (4 lenses, verified findings) supplied the fix list below.

**Design decisions finalized with the user:**
1. **Contract = ground-truth parity** (session_id counting key, no End-clip, paused-in-foreground = active) as the primary semantics; production variants (user+session key, End-clipping) documented as policy knobs with measured impact.
2. **Freshness = compactor tick only** (30–60s), one serving path, no live overlay.
3. **OSS = both** LibreChat + ClickHouse MCP (conversational layer over serving tables) *and* ClickStack (observing our own pipeline: ingest lag, compactor latency, query perf). Build phase comes later; design doc reserves their place now.
4. **Benchmark insurance = all three scopes**: user-level concurrency table (user-scope compactor emission), plus `app_version` and `audio_language` added to the dimension delta table key (both event-attributed; app_version is session-constant, audio_language genuinely switches mid-session in 16.1% of sessions).

## Architecture (final)

```
event stream → raw_events (MergeTree, PARTITION BY utc-day, ORDER BY (session, ts))
  → insert-time MV → session_state (AggregatingMergeTree, commutative states only;
      unit key = (vsid, platform, content_id, app_version, audio_language))
  → compactor tick (30–60s watermark; single-writer; memo-diff corrections)
      emits three scopes:
        concurrency_deltas          (platform, content_id, video_type, app_version, audio_language, m)
        concurrency_deltas_global   (m)            — session-scoped, exact global
        concurrency_deltas_users    (m)            — user-scoped (uniq-by-user)
      all SummingMergeTree ±1 minute-edge deltas, day-split (day-anchored cumsum)
  → serving: dense-grid day-anchored cumulative sum; peak = max, avg = avg over minutes
```

Correctness contract (validated): activity = ANY event type in {SessionStart, Play, Heartbeat, Foregrounded}; liveness T=120s; bg exclusion = wholly-contained-minute rule with next-fg pairing; slices event-attributed, global session-attributed.

## Execution steps

### 1. Finalize `docs/DESIGN.md` (v2 — single source of truth)
Fold in decisions + verified review fixes:
- UTC pinned everywhere: epoch-seconds arithmetic in prototype (already true); `DateTime('UTC')` types noted for Cloud DDL; day = UTC day
- §2 wording: bg exclusion is the minute-grain wholly-contained rule (what the prototype implements and validated), not second-grain "immediate"; state the GT-parity contract + knobs table with measured deltas (End-clip ≈ −198 session-minutes; user+vsid key affects 120 colliding sessions)
- §3.5 serving query: dense-grid cumsum (numbers(1440) LEFT JOIN deltas), not WITH FILL after window
- §3.7 live number: served from last compacted minute (decision 2); remove the broken session_state overlay query
- Compactor: single-writer rule, memo-update-after-deltas ordering, idempotent re-run note
- Dictionary: `dictGetOrDefault(..., 'unknown')`, refresh before each compaction tick; unseen-day new-content note
- Unseen-day runbook: named re-verify queries (heartbeat cadence p50/p99, gap-threshold cut-rate at 60/90/120/180s, event-name inventory diff) + decision rule (adjust T only if measured cadence differs; re-emit via memo-diff — no rebuild)
- New scopes (decision 4) + their compactor emissions; serving-table ORDER BY (platform, content_id, app_version, audio_language, m); roll-up tables global/platform stay
- OSS integration section: LibreChat+MCP and ClickStack placement (decision 3)

### 2. Update prototype to the finalized design
- Extend Tier-1 unit key + dim delta table with app_version, audio_language (normalized)
- Add user-scope compactor emission + `concurrency_deltas_users`
- Dictionary default 'unknown'
- Re-run `validate.py` (must stay 0/3,872 global; slice spot-checks; new: user-level sanity vs brute-force uniq-user query) and `replay.py` (convergence to 0 diffs)

### 3. Design HTML artifact
Render the finalized design doc as a self-contained HTML page (architecture diagram, evidence stats, contract, knobs, runbook) for team discussion — publish as private artifact.

### 4. Commit to hackathon repo
`docs/EVIDENCE.md`, `docs/DESIGN.md` (v2), `prototype/` (pipeline, validate, replay), README pointer updates. Clean commit messages; repo already public per event rules.

### Out of scope for this session (next phases, listed in README)
ClickHouse Cloud deployment, LibreChat + MCP wiring, ClickStack setup, benchmark harness + query_log evidence capture, demo dashboard.

## Verification
- `python3 prototype/validate.py` → 0 mismatched minutes vs ground truth; slice checks pass; serving queries < 10 ms; user-level scope sane
- `python3 prototype/replay.py` → live curve builds; 1% held-back late events converge to 0 diffs
- `git log` shows docs + prototype committed; design HTML artifact link delivered
