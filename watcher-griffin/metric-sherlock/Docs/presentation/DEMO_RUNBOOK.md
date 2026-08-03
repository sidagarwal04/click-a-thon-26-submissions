# Live demo runbook — RevenueWatch

Companion to `RevenueWatch_Deck.pptx` (the demo hand-off is slide 15). Five beats, ~4 minutes.
Everything here is a click path + one line to say + what the screen should show + a fallback.

- UI: **http://127.0.0.1:8089** · API: **http://127.0.0.1:8088**
- Langfuse: the project dashboard for the keys in `utils/.env` (log in **before** the talk, keep the tab open)

---

## Pre-demo checklist (run the day before, again 30 min before)

1. **Deploy and verify all four services.**
   ```bash
   ./scripts/deploy.sh
   ```
   (`scripts/deploy.ps1` on Windows.) It runs its own preflight/postflight checks — if it refuses to start, fix that first; do not demo around it.
2. **Keys are live.** Narration and tracing both depend on them:
   ```bash
   python scripts/check_keys.py
   ```
   If narration ever says "unavailable" during rehearsal, this script is the first stop — an empty/rejected key is by far the most likely cause.
3. **⚠️ THE ONE HIGH-STAKES CHECK — the unseen dataset has bands + incidents.**
   `PROGRESS.md` records that `unseen_data`'s `baselines` / `incidents` / `sweep_runs` were **0 rows** when the drop was loaded (5 days of data < the 28-day baseline window; the baselines job now clamps to the data's own end). Before demo day, run the remaining step and verify:
   ```bash
   python -m engine.baselines_job --rebuild --dataset unseen
   ```
   ```bash
   python -m engine.scanner --once --dataset unseen --ignore-cadence
   ```
   Then confirm `unseen_data.incidents` is non-empty (read-only MCP or any client):
   `SELECT count() FROM unseen_data.incidents`
   - **If an incident exists** → Beat 5 runs as written (the full payoff).
   - **If not** → use the Beat 5 fallback below; do **not** claim on stage that the scanner diagnosed the unseen incident.
4. **Warm the paths.** Open the UI, open INC-0623's detail page once, send one throwaway chat message, open one Langfuse trace. First hits are cold; warm runs are the 2.5 s / 3.0 s story.
5. **Pin the tabs in order:** ① UI ops home · ② INC-0623 detail · ③ Langfuse · ④ UI again for the dataset switch. Alt-Tab risk is real under stage nerves.
6. **Screenshot every beat during rehearsal** into `Docs/presentation/screenshots/` — these are the universal fallback if anything is down on the day.

---

## Beat 1 — Ops home (~40 s)

- **Do:** open **http://127.0.0.1:8089**.
- **Say:** "This is the queue after one sweep over nine million events: thousands of raw breaches, but only **7 alertable incidents** — the funnel from the deck, live. Note the suppression counts: the system tells you what it filtered and why. Nothing is hidden."
- **Expect:** incident queue ordered chronologically, the Android outage present; suppression/coverage summary visible on the page.
- **Fallback:** if the UI is down but the API is up, `GET http://127.0.0.1:8088/api/ops/summary` in a browser tab — the JSON tells the same story. Otherwise: rehearsal screenshot.

## Beat 2 — INC-0623, the diagnosis (~60 s)

- **Do:** click **INC-0623** (Android demand partner outage) in the queue.
- **Say:** "Fill rate on Android, one-day grain, **$24.42/day** — $48.84 across its two-day span. The band chart shows the breach against a same-weekday baseline. The waterfall splits the revenue identity — volume vs fill vs price. And this list is my favorite part: the **ruled-out list with numbers** — 7/7 categories spread, 5/5 formats spread — 'not X' is a claim too, so it gets a number. The evidence score's formula is printed right next to the bar: it's an evidence index, never a probability."
- **Expect:** band chart, waterfall, impact bars, causal chain, evidence score ~0.85/85, ruled-out list, SQL trace section.
- **Fallback:** any alertable incident on the page tells the same story — don't fight for the specific ID; the components are identical.

## Beat 3 — Ask it a question (~40 s)

- **Do:** in the incident's chat box, ask: **"Why do you think this is a demand-side problem and not an app problem?"**
- **Say:** "Watch the answer: every figure it uses is one the engine already computed — 33 of 170 apps moved, and that concentration just mirrors Android share. The model is not allowed to compute; if a number isn't in the evidence, it can't say it. And this turn just created its **own Langfuse trace** — hold that thought."
- **Expect:** grounded answer in ~3 s citing spread/concentration numbers from the evidence.
- **Fallback:** if the LLM/key fails, the system returns the deterministic evidence with an explicit "narration unavailable" flag — **show that**: "this is the fail-safe from the deck, live. It would rather tell you it can't narrate than guess." (A genuinely honest save.)

## Beat 4 — Open the trace (~50 s)

- **Do:** switch to the Langfuse tab → most recent traces → open the **investigation trace** for the incident, then point at the **chat trace** from Beat 3.
- **Say:** "The judging criterion is: open a trace and follow the investigation. Here it is — baseline, decompose, the rank queries fanning out **in parallel** — real spans opened around the real execution, not replayed after the fact. Click any span: the **verbatim SQL**, copy-paste-runnable. The narrator is a generation span at the end. And here's the chat turn from a minute ago as its own root trace — a judge typing a question is the moment traceability is actually tested."
- **Expect:** span tree with parallel rank spans, drilldown depth, rule-out events, narrator generation; a separate chat trace with today's timestamp.
- **Fallback:** rehearsal screenshot of a trace + offer to export/share the trace link after the talk. If only Langfuse is down, the UI's SQL-trace panel on the incident page shows the same logged queries.

## Beat 5 — The unseen dataset (~50 s)

- **Do:** back in the UI, use the **dataset switcher** → select the unseen dataset.
- **Say:** "Same UI, same engine, same thresholds — a registry repoints the entire system; no SQL in the repo names a database. This is the data that dropped yesterday: on July 8–9, fill rate falls from **0.794 to 0.731**, led by **APAC at −11.5 points** while every other region loses two to four — and it's flat across formats, which is exactly why region is the localizing dimension. Zero code changes to get here."
- **Expect (if pre-demo check 3 passed):** the APAC fill-rate incident in the unseen queue; open it and let the same components render.
- **Fallback (if `unseen_data.incidents` is empty):** stay honest and still win the point — show the switcher working, then say: "Five days of history is less than one 28-day baseline window — the exact regime our incomplete-window guard exists for; it reports insufficient history rather than hallucinating collapses. The incident itself is confirmed by direct query" — and show the numbers above from a prepared query result (rollups reconciled against raw; isolation proven: the same `app_id` carries different attributes in the two databases with main untouched).

---

## Close (~10 s)

Return to the deck (slide 17): "Every number you just saw — on the slides, in the diagnosis, in the chat answer — traces to a query you can re-run. That's the system."

## If everything is on fire

The deck stands alone: every beat has a slide with the real numbers, and rehearsal screenshots cover the visuals. Present slides 15's beats from screenshots and offer a live session to any judge afterwards.
