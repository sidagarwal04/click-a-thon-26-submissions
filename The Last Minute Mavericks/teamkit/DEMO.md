# Demo (≤5 min) + UI spec

One incident, replayed end to end. **Show a run, not the build.** Lead with the trust layer —
that's the differentiation; everyone else stops at "detect → LLM writes a paragraph."

Pitch line to open and close on:
> **"ClickHouse does the reasoning. The LLM only reads the answer out loud — and we can prove it, per number, per query ID."**

Bring-up (before judges arrive): `./scripts/demo_up.sh` — starts console (:8533),
shim (:8601), LibreChat (:3080) and health-checks all four services. For the unseen
slice: `RCOS_TABLE=<db>.<table> RCOS_SCAN_BUNDLE=<scan.json> ./scripts/demo_up.sh`.

## The 5-minute beat sheet (3-page console: Metrics / Incidents / Diagnosis + Ask AI dock)
| Time | Beat | What's on screen |
|---|---|---|
| 0:00–0:25 | **The alert** | Metrics page: 6 KPI billboards + chart grid, incident windows shaded. Hover the fill-rate cliff — synced crosshair tracks all six charts; tooltip flags `INC-C · Fill rate ⚠` red while siblings stay calm. "A human starts drilling here; that takes ~114 analyst-hours. Watch." |
| 0:25–0:45 | **Provenance** | Footer: `source rca.events · rows read 9,000,000 · 100 ms · query id rcos-ui-…`. Time pill: flip Full range → Last 6 hours — a fresh live ClickHouse aggregation each time. "Every chart is one SQL query you can rerun." |
| 0:45–1:15 | **The incident** | Click the red point → incident card: `INC-C −44.8%`, cause chip, ruled-out collapsed. Click **Open investigation →** |
| 1:15–2:00 | **The investigation** | Incidents page: 2×2 incident tiles (each its own metric chart), arrow-key through INC-C's 4-step case file — Anomaly (observed 43.33% vs 78.49%) → Investigation (the 13,672-checks callout + ruled-out checklist) → Verdict (LOCALIZED · `os_version = Android 15`) → Action (NOW/TODAY playbook). |
| 2:00–2:50 | **The deep RCA** | Click **Full RCA evidence →** → Diagnosis page: LMDI waterfall (fill_rate ◆ PRIMARY DRIVER), culprit card (rate/mix, purity, counterfactual), candidate funnel 1,709 → 1, uniformity across 5 regions, 3-bucket hypotheses, 18-row evidence ledger w/ query ids. Selector chips: flip to INC-A — GLOBAL_UNLOCALIZED as a first-class verdict ("declaring a culprit here would be the false positive"). |
| 2:50–3:20 | **The guardrail (money shot)** | Ask AI dock → red chip "⛔ Demo: try to sneak in a fabricated number" → `FABRICATION REJECTED — 99.97, 0.001 appear in NO query result` + the grounded replacement. "Fabrication is structurally impossible — and you just watched it fire." |
| 3:20–3:50 | **Grounded chat** | Dock preset "What should I do next?" → answer with [ev_N] chips. Then ↗ → full LibreChat (self-hosted, 4th integration): same endpoint, same validator. |
| 3:50–4:20 | **Proof** | Sidebar → Langfuse trace (public URL): span per investigation node w/ SQL + query id. "Audit us without us." |
| 4:20–5:00 | **Unseen slice** | `RCOS_TABLE=… RCOS_SCAN_BUNDLE=…` (engine output on data it never saw) → the same three pages light up on the new dataset. Close on the pitch line. |

## Appendix — pre-reset 4-tab spec (historical; superseded by the 3-page console above)
Operator voice everywhere; statistics named on screen, explanations one click deeper
("How we know — LMDI, cross-checked with Shapley ▸"). All currency in **USD** (the dataset's
unit) — never ₹. Masthead badges stay honest: "metrics · live clickhouse" + "incident · demo
fixture" until run_incident.py emits real bundles.

Leave out: date pickers, auth, dark mode, segment explorers beyond the attribution table.
Target: **readable at 1080p in a 5-minute video**, and no further.
