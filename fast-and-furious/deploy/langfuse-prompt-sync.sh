#!/usr/bin/env bash
# langfuse-prompt-sync.sh — render the production Langfuse prompt into librechat.yaml.
#
#   ./deploy/langfuse-prompt-sync.sh
#
# Reads the prompt labelled `production` from Langfuse prompt management and expands
# deploy/librechat/librechat.yaml.tmpl into deploy/librechat/librechat.yaml. That file is
# generated, gitignored, and shipped by deploy-librechat.sh -- this script does not touch
# the box.
#
# FAILS CLOSED. If Langfuse is unreachable, unauthenticated, or has no `production` label
# for this prompt, the existing librechat.yaml is left exactly as it was and the script
# exits non-zero. An analyst deployed without the additivity and grouping rules would
# confidently report a nine-fold overcount, so no prompt is strictly better than a lost
# one, and a half-written file is worse than both -- hence the render-to-temp-then-move.
#
# Also writes agent-instructions.txt beside it: the same text, unwrapped, for pasting into
# a LibreChat Agent if the chat-area MCP path is not used.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"
out_dir="$repo/deploy/librechat"

PROMPT_NAME="${PROMPT_NAME:-sonyliv-serving-analyst}"
LABEL="${LABEL:-production}"
TEMPLATE="${TEMPLATE:-$out_dir/librechat.yaml.tmpl}"
TARGET="${TARGET:-$out_dir/librechat.yaml}"

if [[ -f "$repo/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    . "$repo/.env"
    set +a
fi

: "${LANGFUSE_BASE_URL:?set LANGFUSE_BASE_URL}"
: "${LANGFUSE_PUBLIC_KEY:?set LANGFUSE_PUBLIC_KEY}"
: "${LANGFUSE_SECRET_KEY:?set LANGFUSE_SECRET_KEY}"

command -v jq >/dev/null || { echo "sync: jq is required" >&2; exit 1; }
[[ -r "$TEMPLATE" ]] || { echo "sync: cannot read $TEMPLATE" >&2; exit 1; }

base="${LANGFUSE_BASE_URL%/}"
url="$base/api/public/v2/prompts/$PROMPT_NAME?label=$LABEL"

echo "== fetching $PROMPT_NAME (label: $LABEL) from $base =="
if ! resp="$(curl -sS --fail-with-body --max-time 30 -u "$LANGFUSE_PUBLIC_KEY:$LANGFUSE_SECRET_KEY" "$url")"; then
    echo "sync: could not fetch the prompt from Langfuse." >&2
    echo "sync: $TARGET left unchanged. Seed it first with langfuse-prompt-seed.sh." >&2
    exit 1
fi

text="$(jq -r '.prompt // empty' <<<"$resp")"
version="$(jq -r '.version // empty' <<<"$resp")"
if [[ -z "$text" || -z "$version" ]]; then
    echo "sync: Langfuse returned no prompt text or version for $PROMPT_NAME@$LABEL." >&2
    echo "sync: response was: $resp" >&2
    echo "sync: $TARGET left unchanged." >&2
    exit 1
fi

# The provenance stamp. Langfuse links a trace to a prompt version only when the SDK is
# handed the prompt object, and LibreChat -> LiteLLM has no channel to carry one. Putting
# the version in the first line of the system prompt is the honest substitute: it shows up
# in the trace input in Langfuse, so a trace can still be tied back to what produced it.
stamped="<!-- langfuse:$PROMPT_NAME v$version -->
$text"

# A JSON string literal is also a valid YAML double-quoted scalar, so encoding the prompt
# with jq gives correct YAML for any content -- backticks, quotes, colons, newlines and
# all. Building this with a here-doc or an unquoted block scalar is how markdown containing
# `key: value` silently becomes two YAML keys.
prompt_yaml="$(jq -Rs . <<<"$stamped")"

# awk with index/substr, not sed: the encoded prompt contains backslashes and ampersands,
# which sed's replacement syntax would interpret.
#
# Passed through the environment, NOT `awk -v`. `-v` runs escape processing on the value,
# so every \n inside the JSON string becomes a real newline and the one-line scalar becomes
# a hundred lines of broken YAML. ENVIRON does no such processing. (Found by the parse
# check below, which is the entire reason it is there.)
tmp="$(mktemp "${TMPDIR:-/tmp}/librechat.yaml.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

# The agent id, written by sync-agent.sh on the box. Absent on a first deploy -- the agent
# cannot exist before LibreChat is running to create it -- so fall back to a placeholder
# that still parses as YAML. LibreChat then falls back to the model picker, which is
# degraded but not broken, and the next deploy fills it in.
agent_id="$(cat "$out_dir/agent-id" 2>/dev/null || true)"
if [[ -z "$agent_id" ]]; then
    agent_id='AGENT_NOT_YET_CREATED'
    echo "  note: no agent-id yet; run sync-agent.sh on the box, then re-sync"
fi

LANGFUSE_PROMPT_YAML="$prompt_yaml" AGENT_ID="$agent_id" awk '
    {
        line = $0
        i = index(line, "<<LANGFUSE_PROMPT>>")
        if (i > 0) {
            line = substr(line, 1, i - 1) ENVIRON["LANGFUSE_PROMPT_YAML"] substr(line, i + length("<<LANGFUSE_PROMPT>>"))
            found = 1
        }
        j = index(line, "<<AGENT_ID>>")
        if (j > 0) line = substr(line, 1, j - 1) ENVIRON["AGENT_ID"] substr(line, j + length("<<AGENT_ID>>"))
        print line
    }
    END { if (!found) exit 3 }
' "$TEMPLATE" >"$tmp" || {
    echo "sync: $TEMPLATE contains no <<LANGFUSE_PROMPT>> placeholder." >&2
    echo "sync: $TARGET left unchanged." >&2
    exit 1
}

# Parse before publishing. A malformed librechat.yaml makes LibreChat start and silently
# ignore the whole file, which looks like "MCP is not working" rather than "the yaml is
# broken" -- an expensive hour to spend. Skipped with a warning if no parser is present.
if command -v python3 >/dev/null; then
    if ! python3 -c 'import sys,yaml; yaml.safe_load(open(sys.argv[1]))' "$tmp" 2>/dev/null; then
        if python3 -c 'import yaml' 2>/dev/null; then
            echo "sync: rendered YAML does not parse. $TARGET left unchanged." >&2
            exit 1
        fi
        echo "  (pyyaml not installed; skipping the parse check)"
    else
        echo "  yaml parses"
    fi
fi

mv "$tmp" "$TARGET"
trap - EXIT

printf '%s\n' "$stamped" >"$out_dir/agent-instructions.txt"

echo "  rendered $TARGET from $PROMPT_NAME v$version"
echo "  wrote    $out_dir/agent-instructions.txt (paste target for the Agent fallback)"
