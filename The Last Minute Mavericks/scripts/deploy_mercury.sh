#!/usr/bin/env bash
# Redeploy the RCA Engine API to the `mercury` host: sync code → restart the service.
#   bash scripts/deploy_mercury.sh          # code only
#   bash scripts/deploy_mercury.sh --env    # also push .env (creds)
#
# Live setup on mercury (Azure, azureuser):
#   ~/rca-api                    the app
#   systemd  rca-api             uvicorn on 0.0.0.0:8077 (Restart=always, on boot)
#   systemd  rca-tunnel          cloudflared quick tunnel → HTTPS backup (non-stable URL)
# STABLE public URL:  http://23.101.175.68:8077   (NSG rca-api-8077 pri 330 + ufw allow 8077/tcp)
#   /health · /scan · /investigations · /docs
# UI points at it via:  RCOS_API=http://23.101.175.68:8077 streamlit run ui/app.py
# Backup tunnel URL:  ssh mercury 'sudo journalctl -u rca-tunnel | grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" | tail -1'
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "→ syncing code to mercury:~/rca-api ..."
rsync -az --exclude='__pycache__' --exclude='*.pyc' \
  run_incident.py agent api sql contracts requirements.txt mercury:~/rca-api/
# api/server.py imports run_incident_v2 + adjudicate from tests/e2e (recall engine + LLM
# adjudication trays), so those must ship too — path preserved (server adds tests/e2e to sys.path).
ssh mercury 'mkdir -p ~/rca-api/tests/e2e ~/rca-api/integrations'
rsync -az tests/e2e/run_incident_v2.py tests/e2e/adjudicate.py mercury:~/rca-api/tests/e2e/
# run_incident.py AND api/server.py import integrations.otel at module level, so it must ship or
# the service dies on import. Only the module — integrations/librechat/data-node is a Mongo data
# dir and has no business on this host.
rsync -az integrations/otel.py mercury:~/rca-api/integrations/

if [[ "${1:-}" == "--env" ]]; then
  echo "→ pushing .env (creds) ..."; scp -q .env mercury:~/rca-api/.env
fi

echo "→ installing deps + restarting rca-api ..."
ssh mercury 'cd ~/rca-api
  ./venv/bin/pip install -q fastapi uvicorn clickhouse-connect "langfuse==4.14.2" openai \
    "opentelemetry-sdk>=1.27" "opentelemetry-exporter-otlp-proto-http>=1.27"
  sudo systemctl restart rca-api
  sleep 25
  echo "  service: $(systemctl is-active rca-api)"
  echo "  health:  $(curl -s --max-time 10 http://localhost:8077/health)"'

echo "→ public URL:"
ssh mercury 'sudo journalctl -u rca-tunnel --no-pager -n 80 | grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" | tail -1'
echo "done."
