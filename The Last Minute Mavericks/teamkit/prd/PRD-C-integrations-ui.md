# PRD-C — Integrations + UI + deliverables (`integrations/` + `ui/`)

**Owner:** C · **Directory:** `integrations/`, `ui/` · **Consumes:** the golden fixture (UI) +
B's Langfuse trace · **Produces:** the auditable trace, the latency proof, the demo surface, and
the four submission artifacts.

## Mission
Make the system **auditable** (Langfuse), **provably fast** (ClickStack), and **legible in a
5-minute video** (one Streamlit page) — then own the deliverables that are how judges perceive the
other 95%. **LibreChat is dropped** (container sprawl replaces our dashboard = the trap; the rules
need one integration, Langfuse + ClickStack = two).

## Deliverables
| File / artifact | What it does | Notes |
|---|---|---|
| Langfuse (P0 spine) | Stand it up; verify B's traces land and open **publicly** | Cloud or self-host; pull images beforehand |
| `integrations/otel.py` | ClickStack: OTel-instrument the pipeline → HyperDX; per-stage latency | gate behind `CLICKSTACK_ENABLED=1` |
| `ui/app.py` | **One Streamlit page**, 5 panels, against the fixture | see `DEMO.md`; no tabs/routing/auth |
| Deliverables | ≤500-word summary · ≤5-min video · ≤15-slide deck | from ~hour 8, solo |

## Sequence (timeboxed)
1. **Langfuse verified first (~1h).** B's spans visible, trace set public. Non-negotiable — "no trace, no credit."
2. **UI against the fixture (~2.5h, overnight).** Build panels in order (stop partway = still a demo): (1) alert header + **wall-clock timer**, (2) metric tree green/amber/red via nested `st.container`, (3) diagnosis chips `st.popover` → SQL + `query_id` + rows, (4) ruled-out ledger `st.dataframe` incl. the `DILUTION_ARTIFACT` / `EXPLAINED_BY` rows, (5) trace deep-link + `inject_hallucination` toggle.
3. **ClickStack (~1h).** Show "diagnosis in Xs, N ClickHouse queries, p95 …" — the real, measured latency. **Drop this first if slipping.**
4. **Deliverables from hour 8.** Full **dry submission by hour 10** (all fields, real URLs, placeholder video/deck), then swap in the real assets. Record early, not at 11:55.

## Acceptance criteria
- [ ] A judge can open a **public** Langfuse trace URL and follow the investigation unaided
- [ ] ClickStack shows measured per-stage latency (backs the "seconds" claim with data)
- [ ] Streamlit renders the fixture end to end incl. the guardrail toggle firing on screen
- [ ] Dry submission complete by hour 10; final assets swapped before the freeze

## Landmines specific to you
- **ClickStack points at its OWN bundled ClickHouse**, never the competition service — it would write `otel_*` tables into the DB our graded demo depends on.
- With Langfuse + ClickStack both live, set `Langfuse(blocked_instrumentation_scopes=["rca.clickhouse"])` or query spans flood the Langfuse UI judges read.
- **UI is not scored much (5%)** but it's the lens for everything else — build it *readable at 1080p*, and no further. No date pickers, dropdowns, charts, or dark mode.
- **Do NOT build LibreChat.** If asked, point at this PRD + the `DECISIONS.md` entry.
- **You stop coding at ~hour 8** — from there it's video/deck/summary only. This is the role people fumble; protect the deliverables.
