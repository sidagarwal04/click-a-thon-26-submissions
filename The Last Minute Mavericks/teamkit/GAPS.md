# Gaps — live tracker (for the mentor checkpoint)

Status: 🟢 closing now · ⏳ open · 🔵 deferred (presentation — later, per lead).
The engine + observability are strong; the gaps are integration + packaging.

## ✅ Closed
| Gap | Resolution |
|---|---|
| **UI ↔ engine (no live data)** | **DONE — end-to-end live.** API deployed on the `mercury` VM (systemd `rca-api`, uvicorn `0.0.0.0:8077`, on-boot). Public + stable at **`http://23.101.175.68:8077`** (`/health` 0.49s, `/scan` 0.78s, 4 real investigations). UI `incidents()` fetches it via `RCOS_API` — `source_label()` reads *"…8077/scan (live RCA engine)"*. Metrics tab hits ClickHouse Cloud directly. Firewall path opened both layers (Azure NSG rule `rca-api-8077` pri 330 + host `ufw allow 8077/tcp`). Redeploy: `bash scripts/deploy_mercury.sh`. |
| Bundle shape ↔ UI fixture | DONE — `ui/incidents._normalize_api()` maps the engine `/scan` shape → the §8.1 card shape; `scripts/emit_ui_bundle.py` writes the file-drop fallback. Both converge on `_card()`. |
| **ClickStack not wired** (the 4th leg) | **DONE — shipped and verified.** `integrations/otel.py` + a `TracedClient` proxy returned by `run_incident.py connect()` open one span per ClickHouse query across the engine, engine v2 and the API — zero call-site edits, gated behind `CLICKSTACK_ENABLED=1`. Measured: **198 spans per scan** (192 query + 6 stage) land in ClickStack's own ClickHouse (service `rca-engine`); detector output is **identical ON vs OFF**; overhead is not measurable (25.6s OFF / 25.2s ON). The Evidence ledger now shows real cost — 30/30 evidence objects carry non-zero rows and ms (e.g. 3,599,416 rows · 102.6 ms) — and every `query_id` resolves in `default.otel_traces` to its SQL, rows read and ms. Guardrail held: no `otel_*` table exists in the graded service. HyperDX UI: **`http://localhost:8081`** (host 8080 is held by Tailscale). Plan + results: `teamkit/PLAN_CLICKSTACK.md`. |

## ⏳ Open (substance exists, needs wiring/packaging)
| Gap | Why it matters | Priority |
|---|---|---|
| **Speed not packaged as the hero** | We have it (58ms drill-downs, ~seconds e2e) but no benchmark / before-after. The number *"~114 human-hours of dashboard-slicing → seconds"* isn't shown. | HIGH (easy win) |
| **Adoption / business framing** | Customer, revenue-protected, analyst-hours-saved, prod path — implicit, not stated. | MED |
| **LLM narration prose** | Occasionally imprecise phrasing ("decreased by 0.4333"). Grounded + validated, just wording. | LOW |
| **Robustness < 10%** | Measured: catches ≥12%, misses <10%. Challenge plants 34–51% → safe margin, but a subtler unseen anomaly would be missed. Lower gate + FDR to push it (precision cost). | LOW (measured) |

## 🔵 Deferred (presentation — later)
- ≤500-word summary · ≤5-min demo video · ≤15-slide deck · dry submission.

## Where we're strong (for the mentor)
- **ClickHouse & OSS depth (25%)**: all analysis is SQL over the cube; Langfuse used deeply
  (traces + eval **experiments** scored 4/4); LibreChat shim; API now exposes it. ~8.5/10.
- **Trustworthy / Localized / Honest** (the PS bar): ~9/10 each — evidence+`query_id`+validator
  (no hallucination), 2-D/dilution localization, ruled-out ledger, recompute-don't-trust.
- Correct on all 4 planted incidents incl. the hard 2-D; cold-start (blank DB → diagnosis + trace) proven.
