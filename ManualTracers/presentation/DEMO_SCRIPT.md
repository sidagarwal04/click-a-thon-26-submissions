# Live Demo Script — Automated Root-Cause Analyst

> **Objective:** Replay an incident end-to-end in front of the judges. Show detection → investigation → diagnosis → trace.

---

## Pre-Demo Checklist

- [ ] ClickHouse Cloud instance is up and data is loaded
- [ ] `.env` is configured with correct credentials
- [ ] RCA agent is running (`docker compose up --build -d`)
- [ ] RCA UI is accessible at `http://localhost:8090`
- [ ] RCA API health check passes: `http://localhost:3002/health`
- [ ] Langfuse is configured and receiving traces (if available)
- [ ] HyperDX dashboard is open (if showing detection)
- [ ] Terminal is ready with the project directory open
- [ ] Browser tabs pre-loaded: RCA UI, Langfuse trace, HyperDX (if used)

---

## Demo Flow (3–4 minutes)

### Act 1 — Set the Scene (30 sec)

**Say:** "Let me show you what happens when a metric drops. I'm going to trigger an investigation for fill rate and walk you through what the system does."

**Show:**
- The RCA UI landing page / dashboard
- Briefly point at the metric chart showing the fill rate dip

---

### Act 2 — Trigger the Investigation (30 sec)

**Option A — Webhook trigger (preferred, shows full pipeline):**
```bash
curl -X POST http://localhost:3002/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"title":"fill_rate alert","body":"metric_id=fill_rate"}'
```

**Option B — If using pre-computed reports:**
- Navigate to the RCA UI and select an existing report (e.g., Android 15 fill-rate drop)

**Say:** "The webhook hits our receiver. It dedupes, validates the metric against the registry, and backgrounds the investigation."

---

### Act 3 — Walk Through the Diagnosis (90 sec)

**Show the RCA UI output. Walk through each section:**

1. **Reproduction:**
   - "The system first re-derived the anomaly from live data. Fill rate was 0.75 vs expected 0.78."
   - Point at the z-score: "Peak z of -9.17 — well beyond the threshold."

2. **Decomposition (if revenue):**
   - "For revenue, it first walks the funnel identity: requests × fill rate × render rate × eCPM. Which factor moved?"
   - "Fill rate was implicated. Requests and eCPM were cleared."

3. **Dimension scan:**
   - "It then scored all 62 dimension slices in ONE query — ranked by contribution, not percentage change."
   - "Android 15 was #1, but Galaxy A54, EU, tier_2 also lit up."

4. **Holdout:**
   - "Here's the key: it removed Android 15 from the data and recomputed. Residual: 0.784 — right at baseline."
   - "So Android 15 IS the sole cause. Galaxy A54 only appeared because those devices run Android 15."

5. **Dependency walk:**
   - "Finally, it crossed Android 15 with device_model and country. Both came back uniform."
   - "Every Android 15 device was depressed equally. The fault is at the OS level."

6. **Narrative:**
   - Read out the plain-English diagnosis
   - "Every number in this text was checked against the ledger. If anything didn't match, the LLM output would have been thrown away."

---

### Act 4 — Show the Trace (30 sec)

**Show the Langfuse trace (or equivalent):**
- "Here's the full trace. Each span is one step of the investigation."
- Click into a span: "Here's the SQL that ran, the query_id, rows read, elapsed time."
- "A judge can follow every step, verify every number, reproduce every claim."

**Say:** "No trace, no credit. Here it is."

---

### Act 5 — What Was Ruled Out (30 sec)

**Say:**
- "The system checked AND reported what it cleared:"
  - Seasonality: same hour-of-day, same day-type comparison — not a weekend effect
  - Requests: volume was normal — this isn't a traffic drop
  - eCPM: pricing was normal — this isn't a demand-side issue
  - Device_model, region: bleed-through, not independent causes (holdout proved it)

---

## Fallback Plan

If the live demo breaks during the presentation:

1. **Pre-recorded video:** Have a 2-minute screen recording of the full demo flow saved locally.
2. **Static screenshots:** Have all screenshots from `SCREENSHOTS_CHECKLIST.md` ready in a folder.
3. **Langfuse trace link:** Have the trace URL copied and ready to paste into the browser.
4. **Pre-computed report JSON:** Keep a copy of a complete ledger JSON output to show raw data.

**Where to save fallbacks:**
```
presentation/
├── fallback_video/        ← screen recording (.mp4)
├── fallback_screenshots/  ← numbered screenshots
└── fallback_data/         ← sample ledger JSON, narrative text
```

---

## Demo Tips

- **Don't read slides during the demo.** The UI is the star.
- **Use the narrative as the anchor.** Read the diagnosis aloud — that's what the judges evaluate.
- **Point at numbers.** Every time you mention a number, point to where it appears in the UI AND where it came from in the trace.
- **Name what was ruled out.** The problem statement explicitly rewards "what the system checked and ruled out."
- **Keep the terminal visible** for the webhook curl — it shows this is a real system, not a mock.
- **Rehearse the timing.** The demo should be 3–4 minutes, not 7. Cut ruthlessly.
