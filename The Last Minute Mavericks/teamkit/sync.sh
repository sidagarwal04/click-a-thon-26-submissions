#!/usr/bin/env bash
# What changed on main since my local copy? Run this BEFORE starting any task.
#   bash teamkit/sync.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

git fetch -q origin main

echo "== commits on origin/main you don't have yet =="
git log --oneline --no-merges HEAD..origin/main || true
echo

echo "== new teamkit/DECISIONS.md entries (origin vs your local) =="
diff=$(git diff --no-color HEAD..origin/main -- teamkit/DECISIONS.md | grep -E '^\+' | grep -vE '^\+\+\+' | sed 's/^+//' || true)
[ -n "$diff" ] && echo "$diff" || echo "(none)"
echo

echo "== context/contract files changed on origin =="
git diff --stat HEAD..origin/main -- CLAUDE.md teamkit/CONTRACTS.md teamkit/TASKS.md || true
echo

echo "Next: 'git pull --rebase origin main' to sync."
echo "If CLAUDE.md or teamkit/CONTRACTS.md changed, tell your agent to re-read them (or open a fresh terminal)."
