#!/usr/bin/env bash
# deploy-librechat.sh — render the Langfuse prompt, ship the LibreChat stack, bring it up.
#
#   LIBRECHAT_HOST=ec2-user@1.2.3.4 ./deploy/deploy-librechat.sh
#   LIBRECHAT_HOST=... ./deploy/deploy-librechat.sh --check    verify without shipping
#   LIBRECHAT_HOST=... ./deploy/deploy-librechat.sh --sync     prompt only, then restart api
#
# One-time box setup is in deploy/README.md: docker, nginx, /etc/sonyliv/librechat.env, and
# the security-group rule for 8443. This script assumes all of it and fails loudly if any
# is missing rather than half-configuring the box.
#
# Order matters: the prompt is rendered and validated LOCALLY first, so a Langfuse outage
# stops the deploy before anything on the box has been touched.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"

host="${LIBRECHAT_HOST:-${DEPLOY_HOST:-}}"
[[ -n "$host" ]] || { echo "deploy-librechat.sh: set LIBRECHAT_HOST=user@host" >&2; exit 2; }

remote_dir="${LIBRECHAT_DIR:-/opt/sonyliv/librechat}"

mode=deploy
case "${1:-}" in
    --check) mode=check ;;
    --sync)  mode=sync ;;
    "")      ;;
    *)       echo "deploy-librechat.sh: unknown flag $1" >&2; exit 2 ;;
esac

# Every `docker compose` call here is under sudo. Not laziness: the compose CLI -- not the
# daemon -- is what reads `env_file`, and /etc/sonyliv/librechat.env is 0600 root-owned on
# purpose, the same convention the systemd units use. Being in the docker group is enough
# to talk to the daemon and not enough to read that file, so an unprivileged
# `docker compose up` fails with a bare "permission denied" naming the env file.
#
# ---------------------------------------------------------------------------
# Verification. Run after every deploy, and on its own with --check.
#
# Each step fails for a different reason, so they are separate lines with separate
# messages: "LibreChat is up but the MCP server is unreachable" and "LibreChat is down" want
# very different next actions.
# ---------------------------------------------------------------------------
remote_check() {
    # shellcheck disable=SC2029
    ssh "$host" "set -uo pipefail
        cd '$remote_dir'
        fail=0

        echo '== containers =='
        sudo docker compose ps --format 'table {{.Service}}\t{{.Status}}'

        echo '== librechat =='
        if curl -fsS --max-time 10 http://127.0.0.1:3080/health >/dev/null; then
            echo '  ok  127.0.0.1:3080/health'
        else
            echo '  FAIL  LibreChat is not answering on 3080'; fail=1
        fi

        echo '== litellm -> gemini =='
        # python3, not curl -- see the healthcheck note in docker-compose.yml.
        if sudo docker compose exec -T litellm python3 -c \
             \"import urllib.request; urllib.request.urlopen('http://localhost:4000/health/liveliness', timeout=8)\" \
             >/dev/null 2>&1; then
            echo '  ok  proxy alive'
        else
            echo '  FAIL  LiteLLM is not alive; traces will not reach Langfuse'; fail=1
        fi

        echo '== mcp, from inside the api container =='
        # The step that actually proves the integration. Reaching the MCP server from the
        # host proves nothing about whether the CONTAINER can, and that gap -- host.docker
        # .internal unresolved, or the server still bound to the host loopback -- is the
        # most likely way this deployment fails.
        #
        # The probe is piped in on stdin so none of its JavaScript needs escaping through
        # ssh; it reports its own reason on failure.
        if sudo SONYLIV_MCP_TOKEN=\"\$(sudo bash -c 'sed -n \"s/^SONYLIV_MCP_TOKEN=//p\" /etc/sonyliv/mcp.env')\" \
             docker compose exec -T -e SONYLIV_MCP_TOKEN api node < mcp-probe.js; then
            :
        else
            echo '  FAIL  see reason above'; fail=1
        fi

        echo '== nginx =='
        if curl -fsSk --max-time 10 https://127.0.0.1/ -o /dev/null; then
            echo '  ok  :443  -> LibreChat'
        else
            echo '  FAIL  :443 is not serving LibreChat'; fail=1
        fi
        if curl -fsSk --max-time 10 https://127.0.0.1:8443/ -o /dev/null; then
            echo '  ok  :8443 -> fleet dashboard'
        else
            echo '  FAIL  :8443 is not serving the dashboard'; fail=1
        fi

        exit \$fail"
}

if [[ "$mode" == check ]]; then
    remote_check
    exit $?
fi

# ---------------------------------------------------------------------------
# 1. Prompt. Local, and before anything is shipped.
# ---------------------------------------------------------------------------
echo "== rendering librechat.yaml from Langfuse =="
"$repo/deploy/langfuse-prompt-sync.sh"

# ---------------------------------------------------------------------------
# 2. Preflight the box. Cheaper to find a missing env file now than after a transfer.
# ---------------------------------------------------------------------------
echo "== preflight =="
# shellcheck disable=SC2029
ssh "$host" "set -euo pipefail
    command -v docker >/dev/null || { echo 'docker is not installed (see deploy/README.md)' >&2; exit 1; }
    sudo docker compose version >/dev/null || { echo 'docker compose v2 is missing' >&2; exit 1; }
    sudo bash -c 'test -r /etc/sonyliv/librechat.env' \
        || { echo '/etc/sonyliv/librechat.env is missing (see deploy/librechat/.env.example)' >&2; exit 1; }
    sudo mkdir -p '$remote_dir'
    sudo chown \"\$(id -u):\$(id -g)\" '$remote_dir'

    # LibreChat + Mongo + LiteLLM want roughly 2 GB. Discovering that after the images are
    # pulled costs ten minutes and an OOM-killed container that looks like a config bug.
    avail=\$(free -m | awk '/^Mem:/{print \$7}')
    echo \"  available memory: \${avail} MB\"
    if [ \"\$avail\" -lt 1800 ]; then
        echo \"  WARNING: under 1.8 GB available. Expect the OOM killer.\" >&2
    fi"

# ---------------------------------------------------------------------------
# 3. Ship. rsync so a redeploy moves only what changed.
# ---------------------------------------------------------------------------
echo "== ship =="
rsync -az --delete \
    --exclude 'data-node/' --exclude 'images/' --exclude 'uploads/' --exclude 'logs/' \
    "$repo/deploy/librechat/" "$host:$remote_dir/"
echo "  synced $remote_dir"

if [[ "$mode" == sync ]]; then
    # shellcheck disable=SC2029
    ssh "$host" "cd '$remote_dir' && sudo docker compose up -d --force-recreate api"
    echo "  api restarted on the new prompt"
    remote_check
    exit $?
fi

# ---------------------------------------------------------------------------
# 4. Up, then verify. `up -d` and not `restart`: the compose file itself may have changed.
# ---------------------------------------------------------------------------
echo "== up =="
# shellcheck disable=SC2029
ssh "$host" "set -euo pipefail
    cd '$remote_dir'
    sudo docker compose pull --quiet
    sudo docker compose up -d
    # LibreChat builds its client on first boot and is slow to answer until it has.
    for i in \$(seq 1 60); do
        curl -fsS --max-time 3 http://127.0.0.1:3080/health >/dev/null && break
        sleep 3
    done
    # And wait out LiteLLM's health start_period. Without this the check below runs
    # against a container that is still starting and reports a failure that resolves
    # itself thirty seconds later -- the most annoying kind of red.
    for i in \$(seq 1 40); do
        sudo docker compose ps --format '{{.Service}} {{.Status}}' | grep -q 'litellm.*healthy' && break
        sleep 3
    done"

# ---------------------------------------------------------------------------
# 5. The agent. Must come AFTER `up -d`, because it is created through LibreChat's own
#    API, which needs LibreChat running -- and librechat.yaml's default modelSpec needs
#    the resulting agent id. That circularity is why this is two passes rather than one.
#
#    Skipped, with a warning rather than a failure, if no owner account is configured:
#    a first deploy has no account yet, and the stack is still usable via the picker.
# ---------------------------------------------------------------------------
echo "== agent =="
# shellcheck disable=SC2029
if ssh "$host" "cd '$remote_dir'
    eval \"\$(sudo bash -c 'grep -E \"^LIBRECHAT_(EMAIL|PASSWORD|CODE_API_KEY)=\" /etc/sonyliv/librechat.env' | sed 's/^/export /')\"
    if [ -z \"\${LIBRECHAT_EMAIL:-}\" ]; then
        echo '  skipped: set LIBRECHAT_EMAIL/LIBRECHAT_PASSWORD in /etc/sonyliv/librechat.env' >&2
        exit 1
    fi
    ./sync-agent.sh"; then
    # Pull the id back and re-render, so the default modelSpec points at the agent that
    # actually exists rather than at whatever this checkout last saw.
    scp -q "$host:$remote_dir/agent-id" "$repo/deploy/librechat/agent-id" 2>/dev/null || true
    "$repo/deploy/langfuse-prompt-sync.sh" >/dev/null
    scp -q "$repo/deploy/librechat/librechat.yaml" "$host:$remote_dir/librechat.yaml"
    # shellcheck disable=SC2029
    ssh "$host" "cd '$remote_dir' && sudo docker compose up -d --force-recreate api >/dev/null 2>&1
        until curl -fsS --max-time 3 http://127.0.0.1:3080/health >/dev/null 2>&1; do sleep 2; done"
    echo "  agent bound, librechat.yaml re-rendered against it"
else
    echo "  WARNING: no agent. Tools will need attaching from the chat-area dropdown," >&2
    echo "  which nobody remembers to do -- and the failure is an empty reply." >&2
fi

echo
remote_check
rc=$?

echo
if [[ $rc -eq 0 ]]; then
    echo "done."
    echo "  LibreChat  https://<host>/       (register once, then set ALLOW_REGISTRATION=false)"
    echo "  dashboard  https://<host>:8443/"
    echo "  traces     your Langfuse project"
else
    echo "deploy finished with failing checks above -- the stack is up but not proven." >&2
fi
exit $rc
