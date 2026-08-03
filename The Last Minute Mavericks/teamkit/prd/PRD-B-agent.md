# PRD-B — Agent / orchestration + trust layer (`agent/` + `run_incident.py`)

**Owner:** B · **Directory:** `agent/`, `run_incident.py` · **Consumes:** §7/§8/§8.1/§9 + the
golden fixture · **Produces:** the traced, multi-incident diagnosis judges audit.

## Mission
Turn A's SQL results into a diagnosis where **fabrication is structurally impossible** and the
whole investigation is a **readable Langfuse trace**. This is our differentiator ("trustworthiness")
and the "no trace, no credit" deliverable. You develop entirely against the **golden fixture** —
zero wait on A.

## Deliverables (files in `agent/`, referencing `CONTRACTS.md`)
| File | Implements | Contract |
|---|---|---|
| `run_incident.py` | One command: load → **scan** (metrics × windows) → emit `{scan_summary, investigations:[...]}` + trace. **BUILD FIRST, dumb baseline.** | §8, §8.1 |
| `evidence.py` | Evidence store: `register(label, value, sql, query_id) → ev_id`; `{value, sql, query_id, rows}` | §7 |
| `validator.py` | Reject any completion with a numeral not resolvable to an `ev_id`; retry once; fail loud | §7 |
| `narrate.py` | Prompt receives **label/value pairs only**, emits `{{ev_N}}` placeholders — never raw rows/arithmetic | §7 |
| `graph.py` | LangGraph: detect → decompose → attribute → descend → verify → rule_out → narrate | §9 |
| `trace.py` | Langfuse span per node: SQL, `query_id`, rows, **prune/pursue reason**; spans for cleared/pruned branches too | §9 |

## Sequence (timeboxed)
1. **`run_incident.py` dumb E2E FIRST (by hour 2).** ingest → scan → naive top-segment → printed sentences → `{investigations:[...]}` + a Langfuse trace. Ugly but end-to-end, committed. *If this exists at hour 2 and never breaks, we finish.*
2. **Evidence store + validator (against the fixture).** Prove the validator **rejects a tampered number** and retries — this is the demo money-shot; build the `inject_hallucination` path.
3. **Narration.** Placeholder-only prose from `{{ev_N}}`; multi-incident aware (one narration per investigation).
4. **LangGraph + Langfuse spans.** Nodes map 1:1 to trace spans; emit spans for ruled-out/pruned branches with the number that cleared them.
5. **Swap fixture → A's live SQL** at integration; keep the 4-incident test green end-to-end.

## Acceptance criteria
- [ ] `run_incident.py <slice>` emits a ranked multi-incident bundle + a **public** Langfuse trace URL
- [ ] Validator provably rejects a fabricated numeral (demo it); no number reaches the user without an `ev_id`
- [ ] On the seen data (with A's SQL) it reproduces the 4 diagnoses incl. `GLOBAL_UNLOCALIZED` for INC-A
- [ ] Trace reads top-to-bottom like a transcript, including what was ruled out and why

## Landmines specific to you
- **`langfuse==4.14.2` pinned.** SDK is v4; v2/v3 patterns (`langfuse.trace()`, `trace.span()`, `langfuse_context`) are removed — an agent writing from memory will emit v2 and burn an hour. Use `shutdown()` (not `flush()`) in a `finally`, and `set_trace_as_public()` so judges open the trace without our creds.
- **Multi-incident:** don't hardcode single-investigation; the slice has ≥4 (§8.1). Confirm scan-default vs `--scan` with A before wiring.
- **The LLM never sees a raw row.** If you're about to pass a dataframe into a prompt, stop.
- **`GLOBAL_UNLOCALIZED` is a valid verdict**, not an error — some incidents have no responsible segment (§6.5). Narrate it honestly ("no single segment; the move is global").
