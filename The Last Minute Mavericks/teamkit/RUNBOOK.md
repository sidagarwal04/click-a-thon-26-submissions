# RUNBOOK — run the live system (no local data needed)

Everything is deployed. **You do not load data, build a cube, or run the engine locally.**
Point at the shared live services and go.

## The live services (shared by the whole team)

| Service | URL | What it is |
|---|---|---|
| **RCA Engine API** | **`http://23.101.175.68:8077`** | The detector, live. Recomputes diagnoses from ClickHouse. Public + stable. |
| **ClickHouse Cloud** | in `.env` (`CLICKHOUSE_*`) | The shared data-of-record (`rca` db, 9M rows). One service for everyone. |
| **Langfuse** | cloud.langfuse.com | Traces + eval experiments (each incident links its trace). |

### Hit the API directly — no setup, works from anywhere
```bash
curl http://23.101.175.68:8077/health          # {"status":"ok","db":"rca","investigations":4}
curl http://23.101.175.68:8077/scan            # full bundle: 4 investigations + scan_summary
curl http://23.101.175.68:8077/investigations  # list view
# interactive docs in a browser:
open http://23.101.175.68:8077/docs
```

## Run the UI against the live services

```bash
# from the repo root
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # streamlit, clickhouse-connect, pandas, altair, ...

# point the Incidents/Diagnosis tab at the LIVE engine (no local engine run):
export RCOS_API=http://23.101.175.68:8077

# ClickStack traces from the DEPLOYED engine (only once 8080 is reachable — see below):
export CLICKSTACK_URL=http://23.101.175.68:8080

streamlit run ui/app.py                    # → http://localhost:8501
```

**ClickStack via the deployed service.** The engine is instrumented but the tracer is a
no-op unless `CLICKSTACK_ENABLED=1` is set **on the box**, so deploying the code is not
enough. Enable and verify it in one command:

```bash
bash scripts/enable_clickstack_mercury.sh            # enable + verify spans land
bash scripts/enable_clickstack_mercury.sh --status   # report only
bash scripts/enable_clickstack_mercury.sh --off      # revert
```

Run `scripts/deploy_mercury.sh` from current `main` first — the engine cannot emit a span
if `integrations/otel.py` is not on the box. The sidebar link only resolves off-box once
port 8080 is opened (`ufw` **and** an Azure NSG rule mirroring `rca-api-8077`); until then
the spans exist and are queryable by SQL on the box, but the link will not open.

- **Incidents / Diagnosis tab** → fetched **live** from `…8077/scan`. The footer reads
  *"…8077/scan (live RCA engine)"*. No local data, no `run_incident.py` run needed.
- **Metrics / charts tab** → queries **shared ClickHouse Cloud** directly, so it needs the
  `CLICKHOUSE_*` values in `.env` (the Captain shares one `.env` — same values every terminal;
  it's gitignored, never committed). Set `RCOS_TABLE=rca.ad_events`.
- If the API ever blips, the Incidents tab silently falls back to the committed
  `contracts/fixtures/scan_bundle.json` — the page can't break mid-demo.

### Minimal `.env` (Captain provides the real values)
```
CLICKHOUSE_HOST=...      CLICKHOUSE_PORT=8443    CLICKHOUSE_SECURE=true
CLICKHOUSE_USER=default  CLICKHOUSE_PASSWORD=... CLICKHOUSE_DATABASE=rca
LANGFUSE_PUBLIC_KEY=...  LANGFUSE_SECRET_KEY=... LANGFUSE_BASE_URL=https://cloud.langfuse.com
OPENAI_API_KEY=...       # for LLM narration; deterministic fallback if absent
```

## One-liner: just the incidents, fully remote (no `.env` at all)
If you only want the Incidents tab and have **no** ClickHouse creds:
```bash
RCOS_API=http://23.101.175.68:8077 RCOS_DATA=off streamlit run ui/app.py
```
(The Metrics tab shows "data unavailable" without creds; Incidents works fully off the API.)

## Deploying an API change (owner: whoever changes `api/` or the engine)
The API is a systemd service on the `mercury` VM. To ship a change:
```bash
bash scripts/deploy_mercury.sh          # rsync code → restart rca-api (needs SSH to mercury)
bash scripts/deploy_mercury.sh --env    # also push an updated .env
```
Firewall (Azure NSG `rca-api-8077` + host `ufw allow 8077/tcp`) is already open and persists —
redeploys don't touch it. After deploy, verify: `curl http://23.101.175.68:8077/health`.

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| API `curl` connection refused | Service down: `ssh mercury 'sudo systemctl restart rca-api'`. Firewall is already open. |
| Incidents tab shows static demo cards | `RCOS_API` not set / API unreachable → it fell back to the file. Re-export `RCOS_API` and reload. |
| Metrics tab "data unavailable" | `CLICKHOUSE_*` missing from `.env`. Get the shared `.env` from the Captain. |
| Want the URL to be HTTPS | Use the backup tunnel: `ssh mercury 'sudo journalctl -u rca-tunnel \| grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" \| tail -1'` |
