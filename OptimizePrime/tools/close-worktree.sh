#!/usr/bin/env bash
# tools/close-worktree.sh — close a managed worktree ONLY if its work is safe.
#
# Written after the orchestrator batch-closed six worktrees on 2026-08-02 without
# checking each one individually. Nothing was lost — T7 had never committed and
# W1 happened to have been pushed earlier — but that was luck, not process.
#
#   tools/close-worktree.sh <worktree-suffix> [branch]
#
# Refuses unless the branch is EITHER fully merged into dev/main OR present on
# origin. "The agent said it was done" is not evidence.
set -euo pipefail
cd "$(dirname "$0")/.."
WT="${1:?usage: close-worktree.sh <worktree-suffix> [branch]}"
BR="${2:-}"
PROJ=36:a2e7c870-4ff3-41fe-946e-62df32fd1c9d

die() { printf 'close-worktree: %s\n' "$*" >&2; exit 1; }

D="$HOME/.superconductor/worktrees/clickathon-project/$WT"
[ -d "$D" ] || die "no such worktree dir: $D"

# Which branch is checked out there?
[ -n "$BR" ] || BR="$(git -C "$D" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
[ -n "$BR" ] || die "cannot determine branch for $WT"

# 1 · Uncommitted work is an automatic refusal — this is how hours get lost.
if [ -n "$(git -C "$D" status --porcelain 2>/dev/null)" ]; then
  git -C "$D" status --short | head -15
  die "$WT has UNCOMMITTED changes on $BR. Commit and push them first."
fi

# 2 · Committed work must be merged somewhere, or pushed.
git fetch -q origin 2>/dev/null || true
MERGED=no
for base in dev main; do
  git merge-base --is-ancestor "$BR" "origin/$base" 2>/dev/null && MERGED="origin/$base"
done
ON_ORIGIN="$(git ls-remote --heads origin "$BR" 2>/dev/null | wc -l | tr -d ' ')"

if [ "$MERGED" = no ] && [ "$ON_ORIGIN" = "0" ]; then
  AHEAD="$(git rev-list --count "origin/dev..$BR" 2>/dev/null || echo '?')"
  die "$BR is NOT merged into dev/main and NOT on origin ($AHEAD commits ahead).
Push it first:  git -C $D push origin $BR
Closing now would lose it."
fi

# KNOWN LIMITATION: "commits ahead" counts inherited merge commits too, so a
# freshly-spawned worktree that has only done its step-zero `git merge origin/dev`
# looks like it has work. Check `git diff origin/dev...HEAD` before overriding —
# if the only diff came from the base branch, there is nothing original to lose.
# Refusing in that case is the safe direction, so this is left as-is deliberately.
printf 'safe to close %s (%s): %s\n' "$WT" "$BR" \
  "$([ "$MERGED" != no ] && echo "merged into $MERGED" || echo 'present on origin')"

chmod -R u+w "$D/.devbox/gopath/pkg/mod" 2>/dev/null || true
sc worktree delete "$PROJ:$WT" --force
