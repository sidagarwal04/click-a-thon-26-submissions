# Unseen Incident Playbook

> **When the sealed dataset drops, follow this exactly. No improvising, no manual investigation. The system does the work.**

---

## Context

From the problem statement:

> "A fresh slice of the same universe, with new planted anomalies no one has seen, will be released to all teams simultaneously in the final hours of the hackathon. Your submission must include what your system produced for it: the diagnosis, the numbers behind it, and the trace that proves your system generated them."

**Key constraints:**
- Output must come from the system, not hand-written
- Must include: diagnosis, numbers, trace
- No trace = no credit
- All teams get the same input at the same time — outputs are directly comparable

---

## Step-by-Step Playbook

### Phase 1 — Ingest (target: 5 minutes)

```bash
# 1. Download the sealed dataset to InMobi/data/
#    (follow the distribution instructions from the organizers)

# 2. Update the data file path in replay.sh
#    Edit scripts/replay.sh — change AD_EVENTS_FILE to point to the new file

# 3. Truncate the existing data (if required) and replay
#    The script has a helper at the bottom for truncation
./scripts/replay.sh --data

# 4. Verify the data loaded
# Run in ClickHouse console:
SELECT count() FROM inmobi.ad_events_enriched;
SELECT min(event_time), max(event_time) FROM inmobi.ad_events_enriched;
```

**✅ Checkpoint:** Row count is reasonable. Time range covers the sealed window.

---

### Phase 2 — Detect & Investigate (target: 2 minutes)

```bash
# Option A: Let HyperDX detect and trigger automatically
#   → Just wait. If alerts are configured, the webhook fires.

# Option B: Manual trigger for all alertable metrics (faster, more reliable)
# Run each:
curl -X POST http://localhost:3002/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"title":"fill_rate alert","body":"metric_id=fill_rate"}'

curl -X POST http://localhost:3002/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"title":"revenue alert","body":"metric_id=revenue"}'

curl -X POST http://localhost:3002/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"title":"ecpm alert","body":"metric_id=ecpm"}'

curl -X POST http://localhost:3002/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"title":"requests alert","body":"metric_id=requests"}'
```

**✅ Checkpoint:** Docker logs show the investigation running. Langfuse shows new traces.

---

### Phase 3 — Capture Evidence (target: 5 minutes)

**Do all of these IMMEDIATELY after the investigation completes:**

1. **Screenshot the RCA UI** — full diagnosis for every detected anomaly
2. **Screenshot / export the Langfuse trace** — every span, every SQL
3. **Copy the narrative text** — save to `presentation/fallback_data/unsealed_narrative.txt`
4. **Copy the ledger JSON** — save to `presentation/fallback_data/unsealed_ledger.json`
5. **Record a screen capture** — the full diagnosis on screen, scrolling through it

```bash
# Save the docker logs for evidence
docker compose logs rca-api --tail 500 > presentation/fallback_data/unsealed_logs.txt
```

---

### Phase 4 — Quick Sanity Check (target: 3 minutes)

Before presenting, verify:

- [ ] The diagnosis names specific segments (not just "something is off")
- [ ] Every number in the narrative appears in the ledger
- [ ] The trace shows the full investigation ladder (reproduce → decompose → scan → holdout → cross)
- [ ] The system identified what was ruled out (not just what was found)
- [ ] The Langfuse trace has SQL text and query IDs visible

**DO NOT:**
- ❌ Edit the narrative by hand
- ❌ Re-run with different parameters to get a "better" answer
- ❌ Claim results the system didn't produce

---

### Phase 5 — Update Presentation (target: 5 minutes)

1. Update **Slide 9** (The Unseen Incident) with the actual diagnosis and numbers
2. Update the **Numbers to Have Ready** table in `TALKING_POINTS.md`
3. Add unsealed screenshots to `presentation/screenshots/` (items 21–23)
4. Have the Langfuse trace URL ready to show

---

## Troubleshooting

### "The agent returns `not_reproducible`"
- The anomaly window may not overlap with the agent's default 24h lookback
- Check `max(event_time)` — is the data fully loaded?
- Check the agent's window: it works backward from `max(event_time)`, so the window shifts with the data

### "No anomalies detected for any metric"
- Run the scan query manually to check:
  ```bash
  ./scripts/metric_query.py scan fill_rate
  ./scripts/metric_query.py scan revenue
  ```
- If the planted anomalies are in different metrics, try `render_rate`, `ctr`, `rpr`

### "Langfuse trace is empty"
- Check `.env` for `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
- Check docker logs for tracing errors
- Restart the container: `docker compose restart rca-api`

### "ClickHouse connection fails"
- Verify `.env` credentials
- Check that the ClickHouse Cloud instance is running
- Test with: `clickhouse-client --host=<host> --user=<user> --password=<password> --query="SELECT 1"`

---

## Timeline Summary

| Step | Time | Cumulative |
|---|---|---|
| Download + Ingest | 5 min | 5 min |
| Trigger investigations | 2 min | 7 min |
| Capture evidence | 5 min | 12 min |
| Sanity check | 3 min | 15 min |
| Update slides | 5 min | 20 min |
| **Total** | **20 min** | |

Leave buffer time before the presentation slot. Don't cut it close.
