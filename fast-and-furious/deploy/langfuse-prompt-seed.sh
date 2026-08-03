#!/usr/bin/env bash
# langfuse-prompt-seed.sh — publish the analyst prompt to Langfuse prompt management.
#
#   ./deploy/langfuse-prompt-seed.sh              # from the repo root, reads .env
#   ./deploy/langfuse-prompt-seed.sh --dry-run    # show what would be posted
#
# The repo file deploy/librechat/prompts/serving-analyst.md is the AUTHORED source: it is
# what review reads and what git records. Langfuse is the RUNTIME source of truth: it is
# what langfuse-prompt-sync.sh loads into the deployed LibreChat, and it is what records
# who changed the prompt and when. Editing the prompt in the Langfuse UI is legitimate --
# copy it back into the repo file afterwards so the two do not drift.
#
# NOT idempotent, deliberately. Langfuse prompts are append-only: every POST creates a new
# version and moves the `production` label to it. That is the correct model for a prompt
# (you want the history), but it means running this twice makes v1 and v2 with identical
# text. Run it once to seed; after that, edit in Langfuse or re-run only when the repo file
# has actually changed.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"

PROMPT_NAME="${PROMPT_NAME:-sonyliv-serving-analyst}"
PROMPT_FILE="${PROMPT_FILE:-$repo/deploy/librechat/prompts/serving-analyst.md}"
LABEL="${LABEL:-production}"

dry_run=false
[[ "${1:-}" == "--dry-run" ]] && dry_run=true

# .env is gitignored and holds the Langfuse keys. Environment wins, so CI can inject them
# without the file existing.
if [[ -f "$repo/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    . "$repo/.env"
    set +a
fi

: "${LANGFUSE_BASE_URL:?set LANGFUSE_BASE_URL (e.g. https://cloud.langfuse.com)}"
: "${LANGFUSE_PUBLIC_KEY:?set LANGFUSE_PUBLIC_KEY}"
: "${LANGFUSE_SECRET_KEY:?set LANGFUSE_SECRET_KEY}"

command -v jq >/dev/null || { echo "seed: jq is required" >&2; exit 1; }
[[ -r "$PROMPT_FILE" ]] || { echo "seed: cannot read $PROMPT_FILE" >&2; exit 1; }

base="${LANGFUSE_BASE_URL%/}"

# jq --rawfile, not a shell here-doc: the prompt is markdown full of backticks, quotes and
# newlines, and building this JSON by string interpolation is how you ship a truncated
# prompt without noticing.
body="$(jq -n \
    --arg name "$PROMPT_NAME" \
    --arg label "$LABEL" \
    --rawfile text "$PROMPT_FILE" \
    '{type: "text", name: $name, prompt: $text, labels: [$label]}')"

if $dry_run; then
    echo "POST $base/api/public/v2/prompts"
    jq . <<<"$body"
    exit 0
fi

echo "== publishing $PROMPT_NAME to $base (label: $LABEL) =="
resp="$(curl -sS --fail-with-body --max-time 30 \
    -X POST "$base/api/public/v2/prompts" \
    -u "$LANGFUSE_PUBLIC_KEY:$LANGFUSE_SECRET_KEY" \
    -H "Content-Type: application/json" \
    --data-binary "$body")" || {
    echo "seed: Langfuse rejected the prompt (response above)" >&2
    exit 1
}

version="$(jq -r '.version // empty' <<<"$resp")"
[[ -n "$version" ]] || { echo "seed: no version in response: $resp" >&2; exit 1; }

echo "  published $PROMPT_NAME v$version, labelled $LABEL"
echo
echo "next: ./deploy/langfuse-prompt-sync.sh renders it into librechat.yaml"
