# USAGE — run the demo in 3 minutes

RootCauseOS finds *why* an ad metric moved. You open a dashboard, click an incident, and get a
diagnosis where every number came from a ClickHouse query — not from the model.

**Nothing runs locally except the dashboard.** The engine and the data are already deployed.

---

## 1. Install (once)

```bash
git clone <this repo> && cd clickathon-inmobi-2026
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Start the dashboard

```bash
export RCOS_API=http://23.101.175.68:8077     # the live engine
streamlit run ui/app.py                       # → http://localhost:8501
```

Check the engine is up first if you want: `curl $RCOS_API/health` → `{"status":"ok",...}`

**No ClickHouse credentials?** Add `RCOS_DATA=fixture` — the Incidents and Diagnosis pages still
work fully off the API; only the raw charts go quiet.

**Have the team `.env`?** Drop it in the repo root and the Metrics page queries ClickHouse Cloud
directly. Nothing else changes.

---

## 3. Walk the demo (4 screens, left sidebar)

| Click | What the judge sees |
|---|---|
| **Metrics** | Revenue, fill rate, eCPM over time. The dip is visible. Every chart is one live SQL query. |
| **Incidents** | The anomalies the engine found on its own — each with a headline delta, a time window, and a verdict. Not a list of everything that moved; the noisy ones are already gated out. |
| **Diagnosis** | Pick one incident. You get: what moved, the split across requests/fill/eCPM, the culprit segment, **what was ruled out** (with numbers), and a Langfuse trace link. |
| **Lite** | The same triage, projector-safe. Use this one if the room's screen is bad. |

Then use the **Ask AI** dock (bottom-right) — ask *"Why did revenue drop?"* or *"What did you
rule out?"*. Answers cite `[ev_N]` evidence tags. Ask it something the data can't support and it
says so instead of inventing a number.

The sidebar also links straight to the **Langfuse trace** and the **ClickHouse console** so
anything on screen can be audited on the spot.

---

## 4. Run the engine yourself (optional)

Only if you want to prove the answers are recomputed, not canned. Needs ClickHouse creds in `.env`.

```bash
python run_incident.py                      # detect → decompose → attribute → verify → print
python run_incident.py --narrate --trace    # add the LLM diagnosis + a public Langfuse trace
python run_incident.py --json scan.json     # write the bundle the UI reads
```

Point the UI at your own run: `RCOS_SCAN_BUNDLE=scan.json streamlit run ui/app.py`

To run against a **different dataset**, set `RCOS_TABLE=<db>.<table>` — the loader reads column
names from the file, so a new slice doesn't need a code change.

## 5. LibreChat (optional, needs Docker)

```bash
python integrations/openai_shim.py &                                  # :8601
docker compose -f integrations/librechat/docker-compose.yml up -d     # :3080
```

Same brain as the in-dashboard chat dock, just a full chat UI. Skip it if Docker isn't running —
the dashboard is unaffected.

---

## If something breaks mid-demo

| Symptom | Fix |
|---|---|
| Incidents look static / generic | `RCOS_API` isn't set or the API is unreachable — it fell back to a bundled fixture. Re-export and reload. |
| Metrics says "data unavailable" | No `CLICKHOUSE_*` in `.env`. Harmless — the diagnosis story still works. |
| Chat dock missing | The shim (`:8601`) isn't running. Optional; everything else works. |
| Page looks stale | **↻ Refresh data** in the sidebar clears caches and re-runs the scan. |

Deploying an engine change, credentials, and the VM details: **[`teamkit/RUNBOOK.md`](teamkit/RUNBOOK.md)**.
