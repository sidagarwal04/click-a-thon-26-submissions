# Screenshots & Visual Evidence Checklist

> Capture everything before the presentation. Screenshots are your fallback if the live demo breaks, and your proof for the submission.

---

## Naming Convention

```
presentation/screenshots/
├── 01_rca_ui_dashboard.png
├── 02_rca_ui_android15_diagnosis.png
├── 03_rca_ui_ios18_diagnosis.png
├── ...
```

Number them in presentation order. Use descriptive names.

---

## Required Screenshots

### Architecture & Setup

- [ ] **01_clickhouse_tables.png** — ClickHouse console showing the key tables: `ad_events_enriched`, `metric_def`, `metric_dim_map`
- [ ] **02_metric_def_rows.png** — SELECT * FROM metric_def (or top rows) — shows the semantic layer
- [ ] **03_metric_dim_map_rows.png** — SELECT * FROM metric_dim_map — shows drill paths and priorities
- [ ] **04_data_volume.png** — `SELECT count() FROM ad_events_enriched` — proves the data is loaded

### Detection (HyperDX / ClickStack)

- [ ] **05_hyperdx_dashboard.png** — The HyperDX dashboard showing metric charts
- [ ] **06_hyperdx_alert_config.png** — Alert configuration for fill_rate (or any metric)
- [ ] **07_hyperdx_alert_firing.png** — An alert that has fired (if available)

### RCA UI — Training Data Results

- [ ] **08_rca_ui_landing.png** — The RCA UI landing/dashboard page
- [ ] **09_rca_ui_android15_full.png** — Full Android 15 fill-rate diagnosis (scroll capture)
- [ ] **10_rca_ui_android15_reproduction.png** — Reproduction section zoomed in
- [ ] **11_rca_ui_android15_dimension_scan.png** — Dimension scan section showing rankings
- [ ] **12_rca_ui_android15_holdout.png** — Holdout result showing bleed-through killed
- [ ] **13_rca_ui_android15_dependency.png** — Dependency walk showing uniform across devices
- [ ] **14_rca_ui_android15_narrative.png** — The plain-English diagnosis text
- [ ] **15_rca_ui_ios18_full.png** — iOS 18.1 diagnosis (if available)

### Traceability (Langfuse)

- [ ] **16_langfuse_trace_overview.png** — Full trace showing all spans for one investigation
- [ ] **17_langfuse_span_detail.png** — A single span expanded showing SQL, query_id, rows, elapsed
- [ ] **18_langfuse_narrate_span.png** — The narration span showing LLM input/output

### Grounding

- [ ] **19_grounding_pass.png** — Evidence of grounding check passing (if visible in UI/logs)
- [ ] **20_grounding_fallback.png** — Example of the templated fallback (optional — show only if you have one)

### Unseen Incident (capture AFTER sealed data arrives)

- [ ] **21_unsealed_diagnosis_full.png** — Complete diagnosis for the sealed dataset
- [ ] **22_unsealed_trace.png** — Langfuse trace for the sealed dataset investigation
- [ ] **23_unsealed_narrative.png** — The narrative text for the sealed incident

### Terminal / Logs

- [ ] **24_webhook_curl.png** — Terminal showing the webhook curl command and response
- [ ] **25_agent_logs.png** — Docker logs showing the investigation steps
- [ ] **26_test_results.png** — `uv run pytest -q` output (39 tests passing)

---

## Screen Recordings (Optional but Recommended)

- [ ] **demo_full.mp4** — End-to-end demo: webhook → investigation → diagnosis → trace (2–3 min)
- [ ] **demo_unsealed.mp4** — The sealed dataset run (capture the moment it runs)

### Recording Tips
- Use QuickTime (Cmd+Shift+5 on Mac) or OBS
- Record at 1080p minimum
- Include the terminal and browser side-by-side if possible
- Keep recordings under 3 minutes

---

## How to Capture

### Full-page screenshot (scroll capture)
```bash
# Browser: Use the built-in "Capture full page" in Firefox, or a Chrome extension
# Mac: Cmd+Shift+4 for region, Cmd+Shift+3 for full screen
```

### ClickHouse query results
```sql
-- Run in the ClickHouse console and screenshot the output
SELECT * FROM inmobi.metric_def FORMAT PrettyCompact;
SELECT * FROM inmobi.metric_dim_map ORDER BY metric_id, priority FORMAT PrettyCompact;
SELECT count() FROM inmobi.ad_events_enriched;
```

### Docker logs
```bash
docker compose logs rca-api --tail 100 | head -50
```

---

## Submission Folder Structure

```
presentation/
├── screenshots/           ← all numbered screenshots
├── recordings/            ← screen recordings
├── fallback_data/         ← sample ledger JSON, raw narrative text
│   ├── android15_ledger.json
│   ├── android15_narrative.txt
│   ├── unsealed_ledger.json
│   └── unsealed_narrative.txt
└── ... (template files)
```
