#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ENV="${LIBRECHAT_DEPLOY_ENV:-$SCRIPT_DIR/.env}"

# LibreChat's .env contains prose and shell-looking examples, so it is not safe
# to source. Read only the deployment variables we need, and keep explicit
# shell environment values as the higher-priority override.
dotenv_value() {
  local key="$1"
  [[ -f "$DEPLOY_ENV" ]] || return 0
  sed -n "s/^${key}=//p" "$DEPLOY_ENV" | tail -n 1
}

set_from_env_file_if_unset() {
  local key="$1"
  local value
  [[ -n "${!key:-}" ]] && return 0
  value="$(dotenv_value "$key")"
  [[ -n "$value" ]] && printf -v "$key" '%s' "$value"
}

set_from_env_file_if_unset SSH_TARGET
set_from_env_file_if_unset SSH_PASSWORD
set_from_env_file_if_unset LIBRECHAT_REF
set_from_env_file_if_unset AGENT_MODEL

: "${SSH_TARGET:?Set SSH_TARGET in $DEPLOY_ENV or the shell environment}"
: "${LIBRECHAT_DIR:=/opt/LibreChat}"
: "${LIBRECHAT_REF:?Set LIBRECHAT_REF in $DEPLOY_ENV or the shell environment}"
: "${AGENT_MODEL:?Set AGENT_MODEL in $DEPLOY_ENV or the shell environment}"

if [[ "$LIBRECHAT_REF" == "main" || "$LIBRECHAT_REF" == "master" || "$LIBRECHAT_REF" == "latest" ]]; then
  echo "LIBRECHAT_REF must be an immutable reviewed tag or commit, not $LIBRECHAT_REF." >&2
  exit 1
fi

remote_quote() {
  printf '%q' "$1"
}

REMOTE_DIR_QUOTED="$(remote_quote "$LIBRECHAT_DIR")"
REMOTE_REF_QUOTED="$(remote_quote "$LIBRECHAT_REF")"
REMOTE_AGENT_MODEL_QUOTED="$(remote_quote "$AGENT_MODEL")"

SSH_OPTIONS=(-o StrictHostKeyChecking=accept-new)
ASKPASS=""
cleanup() {
  [[ -z "$ASKPASS" || ! -e "$ASKPASS" ]] || rm -f "$ASKPASS"
}
trap cleanup EXIT

if [[ -n "${SSH_PASSWORD:-}" ]]; then
  export SSH_PASSWORD
  ASKPASS="$(mktemp)"
  umask 077
  printf '%s\n' '#!/bin/sh' 'printf "%s" "$SSH_PASSWORD"' > "$ASKPASS"
  chmod 700 "$ASKPASS"
  export DISPLAY=codex SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force
fi

remote_ssh() {
  ssh "${SSH_OPTIONS[@]}" "$SSH_TARGET" "$@"
}

sync_config() {
  remote_ssh "mkdir -p $REMOTE_DIR_QUOTED/nginx"
  if command -v rsync >/dev/null 2>&1; then
    rsync -az --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
      -e "ssh -o StrictHostKeyChecking=accept-new" \
      deploy/librechat/librechat.yaml \
      deploy/librechat/deploy-compose.production.yml \
      deploy/librechat/otel-config.yaml \
      "$SSH_TARGET:$LIBRECHAT_DIR/"
    rsync -az --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
      -e "ssh -o StrictHostKeyChecking=accept-new" \
      deploy/librechat/nginx/default.conf \
      deploy/librechat/nginx/clickathon26librechat.nannan.in.conf \
      "$SSH_TARGET:$LIBRECHAT_DIR/nginx/"
  else
    scp "${SSH_OPTIONS[@]}" \
      deploy/librechat/librechat.yaml \
      deploy/librechat/deploy-compose.production.yml \
      deploy/librechat/otel-config.yaml \
      "$SSH_TARGET:$LIBRECHAT_DIR/"
    scp "${SSH_OPTIONS[@]}" \
      deploy/librechat/nginx/default.conf \
      deploy/librechat/nginx/clickathon26librechat.nannan.in.conf \
      "$SSH_TARGET:$LIBRECHAT_DIR/nginx/"
  fi
}

sync_agents() {
  if command -v rsync >/dev/null 2>&1; then
    rsync -az --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
      -e "ssh -o StrictHostKeyChecking=accept-new" \
      deploy/librechat/agents/ \
      "$SSH_TARGET:$LIBRECHAT_DIR/agents/"
  else
    scp -r "${SSH_OPTIONS[@]}" \
      deploy/librechat/agents/. \
      "$SSH_TARGET:$LIBRECHAT_DIR/agents/"
  fi
}

remote_ssh "
  set -eu
  test -f $REMOTE_DIR_QUOTED/.env
  cd $REMOTE_DIR_QUOTED
  if grep -q '^AGENT_MODEL=' .env; then
    sed -i 's|^AGENT_MODEL=.*|AGENT_MODEL=$REMOTE_AGENT_MODEL_QUOTED|' .env
  else
    printf 'AGENT_MODEL=%s\\n' $REMOTE_AGENT_MODEL_QUOTED >> .env
  fi
  git fetch --tags origin
  git checkout --detach $REMOTE_REF_QUOTED
"

sync_config

# LibreChat has a second, host-level Nginx hop in front of its internal client
# proxy. Install the matching long-lived agent-request timeout there as well.
remote_ssh "
  set -eu
  sudo install -m 644 $REMOTE_DIR_QUOTED/nginx/clickathon26librechat.nannan.in.conf \\
    /etc/nginx/sites-available/clickathon26librechat.nannan.in
  sudo ln -sfn /etc/nginx/sites-available/clickathon26librechat.nannan.in \\
    /etc/nginx/sites-enabled/clickathon26librechat.nannan.in
  sudo nginx -t
  sudo systemctl reload nginx
"

remote_ssh "
  set -eu
  sudo -n mkdir -p $REMOTE_DIR_QUOTED/analytics_agent
  sudo -n chown -R \"\$(id -u):\$(id -g)\" $REMOTE_DIR_QUOTED/analytics_agent
  mkdir -p \
    $REMOTE_DIR_QUOTED/agents/context-agent \
    $REMOTE_DIR_QUOTED/agents/finalizer-agent \
    $REMOTE_DIR_QUOTED/context-store-mcp \
    $REMOTE_DIR_QUOTED/runtime-context
"

sync_agents

# The analytics runner, DDL, tests, and role contracts are runtime assets. They
# are deliberately separate from agents/ so the filesystem MCP allowlist cannot
# expose them to ordinary agent conversations.
if command -v rsync >/dev/null 2>&1; then
  rsync -az --delete --exclude '__pycache__/' --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
    -e "ssh -o StrictHostKeyChecking=accept-new" \
    deploy/librechat/analytics_agent/ \
    "$SSH_TARGET:$LIBRECHAT_DIR/analytics_agent/"
else
  echo 'rsync is required to synchronize the analytics runtime safely.' >&2
  exit 1
fi

# The Context Store is a tiny self-contained build context. Stream it directly
# so deployment cannot silently retain an old MCP implementation through an
# rsync transport/cache mismatch.
tar -C deploy/librechat/context-store-mcp -czf - . | \
  ssh "${SSH_OPTIONS[@]}" "$SSH_TARGET" "tar -xzf - -C $REMOTE_DIR_QUOTED/context-store-mcp"
LOCAL_CONTEXT_STORE_SHA="$(sha256sum deploy/librechat/context-store-mcp/server.py | awk '{print $1}')"
remote_ssh "test \"\$(sha256sum $REMOTE_DIR_QUOTED/context-store-mcp/server.py | awk '{print \$1}')\" = $LOCAL_CONTEXT_STORE_SHA"

if command -v rsync >/dev/null 2>&1; then
  rsync -az --chmod=Fu=rw,Fgo=r \
    -e "ssh -o StrictHostKeyChecking=accept-new" \
    deploy/librechat/agents/businesslogic.md \
    "$SSH_TARGET:$LIBRECHAT_DIR/runtime-context/businesslogic.seed.md"
else
  scp "${SSH_OPTIONS[@]}" \
    deploy/librechat/agents/businesslogic.md \
    "$SSH_TARGET:$LIBRECHAT_DIR/runtime-context/businesslogic.seed.md"
fi

remote_ssh "
  set -eu
  if [ ! -f $REMOTE_DIR_QUOTED/runtime-context/businesslogic.md ]; then
    cp $REMOTE_DIR_QUOTED/runtime-context/businesslogic.seed.md \
      $REMOTE_DIR_QUOTED/runtime-context/businesslogic.md
  fi
"

remote_ssh "
  set -eu
  cd $REMOTE_DIR_QUOTED
  docker compose -f deploy-compose.yml -f deploy-compose.production.yml config --quiet
  docker compose -f deploy-compose.yml -f deploy-compose.production.yml pull
  docker compose -f deploy-compose.yml -f deploy-compose.production.yml build analytics-runner-mcp
  docker compose -f deploy-compose.yml -f deploy-compose.production.yml run --rm --no-deps \
    analytics-runner-mcp python /opt/atlys/init_schema.py
  # The client contains an Nginx proxy for the API. Recreate both together so
  # it resolves the API's current Docker-network address after a deployment.
  # Context Store is a locally built service; recreate it after synchronizing
  # its deterministic schema/context-diff implementation as well as the API.
  docker compose -f deploy-compose.yml -f deploy-compose.production.yml up -d --build --remove-orphans --force-recreate context-store-mcp analytics-runner-mcp api client
  for attempt in {1..30}; do
    if curl --fail --silent --show-error --max-time 2 http://127.0.0.1:8080/health >/dev/null; then
      exit 0
    fi
    sleep 2
  done
  echo 'LibreChat client did not become ready within 60 seconds.' >&2
  docker compose -f deploy-compose.yml -f deploy-compose.production.yml ps >&2
  exit 1
"
