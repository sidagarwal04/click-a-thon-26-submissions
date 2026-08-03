# Golden questions — the checkpoint for "the interactive flow works"

Run these in order in a fresh LibreChat conversation with the RCA Analyst agent.
Expected numbers come from the validated query record (`sql/agent/VALIDATED.md`,
9M-row dev load, dataset `main`). Every check must pass before the flow is called
done (ARCHITECTURE.md build order, step 3).

The demo state is **pre-filled** (`agent/prefill.py`): every listed incident already
carries a stored diagnosis + trace, so drills on listed incidents present stored
data instantly; `investigate_window` (and explicit `force` re-runs) run live.
Expected figures below are from the chronological pre-fill: q6 hygiene excludes
earlier *diagnosed* windows (Jun 16/17/21) from later baselines, so the Jun 23
numbers differ in the second decimal from the clean-slate VALIDATED.md record
(−3.417 vs −3.455 pp) — by design. To restore this exact state, use the reset
recipe in [README.md](README.md) (truncate + sweep + prefill).

## 1 · See incidents
**Ask:** "What incidents are there?"
- [ ] Calls `rca.list_incidents`, renders a table (window, metric, scope, status,
      headline, id) — no invented columns or rows.
- [ ] The seeded dev incidents appear, including the Jun 23–25 fill_rate global
      incident and the Jun 21 requests drop.

## 2 · Drill down (the headline demo)
**Ask:** "Why did fill rate drop June 23–25?"
- [ ] Calls `rca.investigate` on the Jun 23–25 fill_rate incident (or
      `investigate_window` with that window) — does NOT answer from its own SQL.
- [ ] Presents the **stored** diagnosis (`cached: true`) — the answer is instant;
      the drill-down itself ran at pre-fill time and its trace is in
      `investigation_steps`.
- [ ] Names **Android 15 (os_version)** as the cause: fill ≈ **0.4333** in-window,
      delta ≈ **−0.3518**, contributing ≈ **98.6%** of the global ≈ **−3.417 pp**
      move (clean-slate measurement: −3.455 pp, see intro note).
- [ ] Requests (≈+4%), render, eCPM reported within thresholds; other dimensions
      (region, ad_format, device_model, …) explicitly ruled out with residuals.
- [ ] Mentions `numbers_verified: true` and that the trace is logged.
- [ ] For a LIVE run instead, ask "re-investigate it fresh" (`force: true`) —
      seconds, not minutes.

## 3 · Show your work
**Ask:** "How do you know? Show your work."
- [ ] Queries `rca.investigation_steps` for the incident, shows steps in order:
      rule_out (baseline hygiene) → decompose → dim_scan ×N → rule_out ×N →
      narrate → verify, each with hypothesis and decision.
- [ ] The SQL used for the trace query itself is shown in the chat.

## 4 · Follow-ups (read-only SQL, shown beside the answer)
**Ask:** "Which apps were hit hardest?"
- [ ] Composes a SELECT over `ad_events_enriched` (two-window sumIf pattern or
      in-window vs baseline), shows the SQL in a ```sql block, ratios are sum/sum.
**Ask:** "What about APAC specifically?"
- [ ] Scoped SELECT (`region = 'APAC'` — NAM/EU/APAC/LATAM/MEA, not NA), SQL shown.

## 5 · Ad-hoc window ("ask about anything")
**Ask:** "Something feels off with rewarded ads on Tuesday June 16 — check it."
- [ ] Calls `rca.investigate_window` (metric fill_rate or revenue,
      2026-06-16, scope `ad_format=rewarded`).
- [ ] If nothing moved: answer is a confident "nothing moved beyond noise", listing
      the levers checked with their numbers — presented as a valid verdict, not an
      apology.

## 6 · Scoped + global contrast
**Ask:** "Was Indonesia hit harder than the rest in the June 23–25 incident?"
- [ ] Either `investigate_window(fill_rate, …, scope=country=ID)` (expected: fill
      ≈ **−6.594 pp** scoped vs −3.455 global — ID skews Android) or a scoped
      follow-up SELECT with the SQL shown.

## 7 · The uniform / global verdict
**Ask:** "Investigate the June 21 revenue drop." (the seeded head for that outage
is the revenue incident)
- [ ] Verdict is GLOBAL_MOVEMENT via the requests lever (≈ −43% uniformly, per-
      segment range ≈ −44…−43%, no segment ≥50% of the move); the agent does NOT
      force-name a segment.

## 8 · Trust probes
**Ask:** "Are you sure? Could you have made those numbers up?"
- [ ] Explains the guardrail: narrative numbers are machine-checked against the
      evidence bundle (`numbers_verified`), every step's exact SQL + result rows are
      in `rca.investigation_steps`, and the diagnosis is reproducible by re-running
      the logged SQL.
- [ ] Does not recompute or "re-verify" numbers itself in chat.

## Latency note
Listed incidents answer **instantly** (stored diagnosis). Live runs
(`investigate_window`, `force` re-runs): SQL total well under 1 s (rollup-first
sweeps); end-to-end incl. one narrator LLM call ≈ 4–8 s. If a live run is much
slower, check that sweeps hit the rollup variant (global scope) and that the stack
isn't falling back to `clickhouse local`.
