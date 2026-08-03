# Execution Plan & Progress — closing the end-to-end loop

The single tracker. Vision: `VISION.md`. Pipeline: `ARCHITECTURE.md`. Interfaces: `CONTRACTS.md`.
Status: ✅ done · 🔄 in progress · ⏳ todo · 🚫 blocked. Owners are **suggested, not mandatory**
(ENG = ClickHouse/engine · AGT = narration/agent · UI = Naman · INT = integrations · CAP = captain).

## 🔑 The one unblock that makes everything parallel
**T1.1 — freeze the Evidence Bundle contract** (`{scan_summary, investigations:[...]}`, CONTRACTS §8).
The moment this is fixed, the engine (emit it), narration (consume it), and the UI (render it) all
build **at the same time against the same shape**, with a golden fixture as the stand-in. Do this first.

---

## Phase 0 — Foundation ✅ (done)
| # | Task | Owner | Status |
|---|---|---|---|
| 0.1 | Load 9M events + dims into ClickHouse `rca` | ENG | ✅ |
| 0.2 | Cube `rca.cube` (pre-aggregated, the Fast enabler) | ENG | ✅ |
| 0.3 | Detection engine: detect → localize → rule-out (all 4 incidents correct, incl. 2-D) | ENG | ✅ |
| 0.4 | Terminal report — REAL vs FALSE table view | ENG | ✅ |
| 0.5 | Langfuse: real investigation trace + eval dataset + precision/recall scores | ENG | ✅ |
| 0.6 | Battle-test harness (synthetic injector + scoring) | ENG | ✅ |
| 0.7 | Reproducible loader (`--parquet` unseen-ready) | ENG | ✅ |
| 0.8 | UI console: metrics grid, time picker, Incidents tab, RCA diagnosis panel | UI | ✅ |
| 0.9 | LibreChat self-hosted + OpenAI-compat shim + chat dock | UI | ✅ |

## Phase 1 — Complete the RCA core (make it "speak") — the current focus
| # | Task | Owner | Status | Depends |
|---|---|---|---|---|
| 1.1 | **FREEZE the Evidence Bundle contract** + commit golden fixture | ENG+UI | ⏳ | — |
| 1.2 | Evidence store: every number → `{value, sql, query_id}` (capture query_id from ClickHouse) | ENG | ⏳ | 1.1 |
| 1.3 | `run_incident.py --json` emits the bundle (not just the table) | ENG | ⏳ | 1.1 |
| 1.4 | Revenue decomposition per incident (identity walk: requests × fill × eCPM) | ENG | ⏳ | 0.2 |
| 1.5 | Confidence score per incident | ENG | ⏳ | 0.3 |
| 1.6 | LLM narration — evidence-only prompt → `{{ev_N}}` → plain-English diagnosis (OPENAI_API_KEY ready) | AGT | ⏳ | 1.2 |
| 1.7 | Validator — reject any numeral not backed by evidence, retry once | AGT | ⏳ | 1.6 |
| 1.8 | Log bundle + narration to the Langfuse investigation trace | AGT | ⏳ | 1.3, 1.6 |

## Phase 2 — Integration (make it "show") — parallel once 1.1 is frozen
| # | Task | Owner | Status | Depends |
|---|---|---|---|---|
| 2.1 | **UI renders the REAL engine bundle** (replace fixtures) | UI | ⏳ | 1.1, 1.3 |
| 2.2 | LibreChat follow-ups route into the engine (same evidence/trace guarantees) | UI/INT | ⏳ | 1.1 |
| 2.3 | ClickStack: OTel-instrument the pipeline → HyperDX (proves "seconds") — 198 spans/scan, evidence rows/ms real, `PLAN_CLICKSTACK.md` | INT | ✅ | — |
| 2.4 | End-to-end on SEEN data: alert → engine → narration → trace → UI | Shared | ⏳ | 1.6, 2.1 |

## Phase 3 — Unseen-incident readiness (the scored moment)
| # | Task | Owner | Status | Depends |
|---|---|---|---|---|
| 3.1 | Multi-incident scan → ranked `investigations[]` (slice has ≥4) | ENG | 🔄 | 1.3 |
| 3.2 | Unseen loader path: `load_clickhouse.py --parquet <slice> --database rca_unseen` → cube → scan | ENG | ✅ ready | 0.7 |
| 3.3 | **Dry-run rehearsal** on a hand-mangled / held-out slice → capture diagnosis + trace | Shared | ⏳ | 2.4, 3.2 |
| 3.4 | Battle-test precision/recall on fresh synthetic; tune gates (target high precision) | ENG | 🔄 | 0.6 |
| 3.5 | Regression test: the 4 known incidents always detected (`tests/detection_eval.py`) | ENG | 🔄 | 0.3 |

## Phase 4 — Deliverables & submission
| # | Task | Owner | Status | Depends |
|---|---|---|---|---|
| 4.1 | ≤500-word solution summary | CAP/Shared | ⏳ | 2.4 |
| 4.2 | ≤5-min demo video (metric tree · validator firing · trace · unseen run) | UI | ⏳ | 2.4, 3.3 |
| 4.3 | ≤15-slide pitch deck ("ClickHouse three ways", the 4 pointers) | UI | ⏳ | 2.4 |
| 4.4 | Repo public + MIT verified + README polished | CAP | ⏳ | — |
| 4.5 | **Dry submission** (all fields, placeholder assets) | CAP | ⏳ | 4.1–4.3 |
| 4.6 | Swap real assets → submit before the freeze | CAP | ⏳ | 4.5 |

## Housekeeping (unblock the queue)
| # | Task | Owner | Status |
|---|---|---|---|
| H.1 | Commit the local contract-alignment + `tests/*` work (uncommitted in a terminal) | A/ENG | ⏳ |
| H.2 | Merge/decide open docs PRs: #4 (PRDs), #18 (architecture), #33 (vision) | CAP | ⏳ |

---
**Critical path to a demo:** 1.1 → (1.2, 1.3) → 1.6/1.7 → 2.1 → 2.4 → 3.3. Everything else runs
alongside. 2.3 (ClickStack) is done and carries no demo risk — it is gated behind
`CLICKSTACK_ENABLED=1` and adds no measurable overhead, so leave it on.
