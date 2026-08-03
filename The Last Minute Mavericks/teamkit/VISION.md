# Vision — the final solution & the full loop

Keep this in mind while building anything (UI, engine, integrations). It's the destination and how
the pieces connect. (The technical pipeline is in `ARCHITECTURE.md`; this is the product end-state.)

## What we're building (one sentence)
An **automated root-cause analyst**: point it at a metric that moved, and in **seconds** it says
*why* — the exact segment responsible — with **every number computed (never invented)**, **what it
ruled out**, and an **auditable trace**. It replaces the hours an analyst spends slicing dashboards.

## The full loop — end to end (✅ built · ⏳ remaining)
```
A metric moves  (or the sealed unseen data drops in)
   │
   ▼  ClickHouse — ALL reasoning is SQL over the cube
   ├─ DETECT     is the move real? (same-weekday baseline + gates)          ✅
   ├─ LOCALIZE   which segment? (1-D / 2-D interaction / global)            ✅
   ├─ RULE OUT   what's false? (dilution artifact / seasonality / noise)    ✅
   │
   ▼  LLM — narrate ONLY (evidence + validator; cannot invent a number)
   └─ "Revenue fell 12% — fill rate for Android 15. Volume & CTR ruled out."  ⏳
   │
   ▼  surfaced three ways
   ├─ Langfuse trace  — the auditable "why", per number, public for judges    ✅
   ├─ UI console      — metric tree + diagnosis (must read the REAL engine)    ✅ built · ⏳ wire to engine
   └─ LibreChat chat  — ask follow-ups, same engine + same guarantees          ✅
```
The hard part (the analytical core) is done — it correctly finds all 4 planted incidents incl. the
2-D interaction and demotes the look-alikes. What remains is the **last mile**: narration + wiring
the UI to the real engine + speed proof.

## What you can do with it
1. **On-call / analyst** — alert fires "revenue −12%" → run it → *"fill rate collapsed for Android
   15; volume & CTR normal and ruled out"* + the proof, in **seconds instead of hours**.
2. **The judged unseen incident** — sealed data drops Day 2 → `run_incident.py` on it → diagnosis +
   Langfuse trace → that IS the submission ("no trace, no credit").
3. **Generalizes** — same engine on any metric/fact table (sign-ups, latency, error rate). Same
   cube, same loop. The scale-&-impact story.

## How we make it better (= the 4 judging pointers)
| Pointer | Now | Better |
|---|---|---|
| **Fast** | cube → ~58ms drill-downs | ClickStack telemetry to *prove* "seconds" |
| **Trustworthy** | evidence + validator | `query_id` on every number (clickable → re-run) |
| **Localized** | correct on all 4, incl. 2-D | confidence scores; battle-test on unseen synthetic |
| **Honest** | ruled-out ledger | narration that states each cleared hypothesis in words |

## For everyone building — the rules that keep us aligned
- **The RCA source of truth is `run_incident.py`** (the ClickHouse SQL engine), NOT fixtures. The UI
  renders the engine's `{scan_summary, investigations:[...]}` bundle; fixtures are offline-dev only.
- **ClickHouse does all reasoning; the LLM only narrates; Langfuse traces it.**
- **Lean (mentor):** only the given data, one cube, no external tables. Don't re-add sprawl.

## Definition of done
One command: sealed data in → a **correct, evidence-backed, plain-English diagnosis** out, with a
**public Langfuse trace** a judge can open — plus the public repo, ≤500-word summary, ≤5-min demo,
≤15-slide deck. Judged on **Fast · Trustworthy · Localized · Honest**.
