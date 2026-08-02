#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

set -a
# shellcheck disable=SC1091
. "$SCRIPT_DIR/.env"
set +a

: "${SSH_TARGET:?Set SSH_TARGET in deploy/ui/.env}"
: "${SSH_PASSWORD:?Set SSH_PASSWORD in deploy/ui/.env}"
: "${REMOTE_DIR:?Set REMOTE_DIR in deploy/ui/.env}"
: "${LIBRECHAT_WORKFLOW_AGENT_ID:?Set LIBRECHAT_WORKFLOW_AGENT_ID in deploy/ui/.env}"
: "${LIBRECHAT_NATIVE_EMAIL:?Set LIBRECHAT_NATIVE_EMAIL in deploy/ui/.env}"
: "${LIBRECHAT_NATIVE_URL:=https://clickathon26librechat.nannan.in}"

ASKPASS="$(mktemp)"
cleanup() { [ ! -e "$ASKPASS" ] || rm "$ASKPASS"; }
trap cleanup EXIT
printf '%s\n' '#!/bin/sh' 'printf "%s" "$SSH_PASSWORD"' > "$ASKPASS"
chmod 700 "$ASKPASS"

remote() {
  DISPLAY=codex SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force \
    ssh -o StrictHostKeyChecking=accept-new "$SSH_TARGET" "$@"
}

if [[ "${1:-}" == "--remote" ]]; then
  remote "${2:?Provide the remote command after --remote}"
  exit
fi

remote "sudo mkdir -p '$REMOTE_DIR' '$REMOTE_DIR/deploy/ui' '$REMOTE_DIR/deploy/librechat' && \
  sudo chown -R \"\$(id -un):\$(id -gn)\" '$REMOTE_DIR'"
DISPLAY=codex SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force \
  scp -o StrictHostKeyChecking=accept-new "$REPO_DIR/.dockerignore" "$SSH_TARGET:$REMOTE_DIR/"

# Preserve the VM's generated runtime .env until the next step safely refreshes
# it from LibreChat's existing credentials. This also omits local build output.
tar -C "$REPO_DIR/deploy/ui" --exclude=.env --exclude=frontend/node_modules \
  --exclude=frontend/dist --exclude=backend/__pycache__ -czf - . | \
  DISPLAY=codex SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force \
  ssh -o StrictHostKeyChecking=accept-new "$SSH_TARGET" "tar -xzf - -C '$REMOTE_DIR/deploy/ui'"
tar -C "$REPO_DIR/deploy/librechat" -czf - agents | \
  DISPLAY=codex SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force \
  ssh -o StrictHostKeyChecking=accept-new "$SSH_TARGET" "tar -xzf - -C '$REMOTE_DIR/deploy/librechat'"
remote "value() { sed -n \"s/^\$1=//p\" /opt/LibreChat/.env | tail -n 1; }; \
  local_value() { sed -n \"s/^\$1=//p\" '$REMOTE_DIR/deploy/ui/.env' | tail -n 1; }; \
  azure=\$(local_value AZURE_STORAGE_CONNECTION_STRING); [ -n \"\$azure\" ] || azure=\$(value AZURE_STORAGE_CONNECTION_STRING); endpoint=\$(value CLICKHOUSE_ENDPOINT); \
  ch_user=\$(value CLICKHOUSE_USER); ch_password=\$(value CLICKHOUSE_PASSWORD); runtime_token=\$(value INVESTIGATION_RUNTIME_TOKEN); \
  if [ -z "\$runtime_token" ]; then runtime_token=\$(openssl rand -hex 32); printf 'INVESTIGATION_RUNTIME_TOKEN=%s\\n' "\$runtime_token" >> /opt/LibreChat/.env; fi; \
  native_url=\$(local_value LIBRECHAT_NATIVE_URL); [ -n \"\$native_url\" ] || native_url='$LIBRECHAT_NATIVE_URL'; native_email=\$(local_value LIBRECHAT_NATIVE_EMAIL); [ -n \"\$native_email\" ] || native_email='$LIBRECHAT_NATIVE_EMAIL'; native_password=\$(value BOOTSTRAP_ADMIN_PASSWORD); workflow_agent_id=\$(local_value LIBRECHAT_WORKFLOW_AGENT_ID); [ -n \"\$workflow_agent_id\" ] || workflow_agent_id='$LIBRECHAT_WORKFLOW_AGENT_ID'; container=\$(value AZURE_CONTAINER_NAME); \
  [ -n \"\$azure\" ] || { echo 'AZURE_STORAGE_CONNECTION_STRING is missing from /opt/LibreChat/.env' >&2; exit 1; }; \
  [ -n \"\$endpoint\" ] || { echo 'CLICKHOUSE_ENDPOINT is missing from /opt/LibreChat/.env' >&2; exit 1; }; \
  [ -n \"\$native_email\" ] || { echo 'LIBRECHAT_NATIVE_EMAIL is missing from the private UI .env' >&2; exit 1; }; \
  [ -n \"\$native_password\" ] || { echo 'BOOTSTRAP_ADMIN_PASSWORD is missing from /opt/LibreChat/.env' >&2; exit 1; }; \
  [ -n \"\$workflow_agent_id\" ] || { echo 'LIBRECHAT_WORKFLOW_AGENT_ID is missing from the private UI .env' >&2; exit 1; }; \
  umask 077; printf '%s\\n' \
  \"AZURE_STORAGE_CONNECTION_STRING=\$azure\" \
  \"AZURE_STORAGE_CONTAINER=\${container:-investigations}\" \
  \"CLICKHOUSE_DSN=\$endpoint\" \
  \"CLICKHOUSE_USERNAME=\${ch_user:-default}\" \
  \"CLICKHOUSE_PASSWORD=\$ch_password\" \
  \"CLICKHOUSE_DATABASE=default\" \
  \"LIBRECHAT_NATIVE_URL=\${native_url:-https://clickathon26librechat.nannan.in}\" \
  \"LIBRECHAT_NATIVE_EMAIL=\$native_email\" \
  \"LIBRECHAT_NATIVE_PASSWORD=\$native_password\" \
  \"LIBRECHAT_WORKFLOW_AGENT_ID=\$workflow_agent_id\" \
  \"INVESTIGATION_RUNTIME_TOKEN=\$runtime_token\" \
  \"MAX_UPLOAD_BYTES=$MAX_UPLOAD_BYTES\" \
  \"SAS_TTL_MINUTES=$SAS_TTL_MINUTES\" \
  \"POLL_INTERVAL_SECONDS=$POLL_INTERVAL_SECONDS\" \
  > '$REMOTE_DIR/deploy/ui/.env'; chmod 600 '$REMOTE_DIR/deploy/ui/.env'"
remote "sudo install -m 644 '$REMOTE_DIR/deploy/ui/nginx/clickathon26investigations.nannan.in.conf' /etc/nginx/sites-available/clickathon26investigations.nannan.in && \
  sudo ln -sfn /etc/nginx/sites-available/clickathon26investigations.nannan.in /etc/nginx/sites-enabled/clickathon26investigations.nannan.in && \
  sudo nginx -t && sudo systemctl reload nginx"
remote "cd '$REMOTE_DIR/deploy/ui' && docker compose up --build -d --remove-orphans"
