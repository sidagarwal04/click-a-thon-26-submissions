#!/usr/bin/env bash
# Assemble the self-contained official team folder for the click-a-thon-26-submissions PR.
#
# Usage:
#   tools/package-submission.sh "<Team Name>" /path/to/click-a-thon-26-submissions-fork
#
# What it does:
#   1. Copies every git-visible file (tracked + untracked-but-not-ignored) into
#      <fork>/<Team Name>/ — .env, data/*.csv and other gitignored files can never leak.
#   2. Promotes submission/README.md to the team folder's root README.md.
#   3. Promotes deck/final/pitch-deck.pdf to the root as pitch-deck.pdf.
#   4. Verifies every mandatory deliverable exists and fails on unfilled placeholders.
#
# After it passes: cd into the fork, commit, push, open the PR titled
#   [Submission] <Team Name>
set -euo pipefail

TEAM="${1:-}"; DEST_ROOT="${2:-}"
[ -n "$TEAM" ] && [ -n "$DEST_ROOT" ] || {
  echo "usage: tools/package-submission.sh \"<Team Name>\" /path/to/submissions-fork"; exit 1; }
[ -d "$DEST_ROOT" ] || { echo "FAIL: fork directory not found: $DEST_ROOT"; exit 1; }

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$DEST_ROOT/$TEAM"

echo "== packaging '$TEAM' -> $DEST"
rm -rf "$DEST"
mkdir -p "$DEST"

# 1. Copy git-visible files only (tracked + untracked, minus everything gitignored).
(cd "$SRC" && git ls-files --cached --others --exclude-standard -z) |
  (cd "$SRC" && tar --null -T - -cf -) | (cd "$DEST" && tar -xf -)

# 2. The team folder's README is the submission README; drop the staging dir.
[ -f "$DEST/submission/README.md" ] || { echo "FAIL: submission/README.md missing"; exit 1; }
mv "$DEST/submission/README.md" "$DEST/README.md"
rmdir "$DEST/submission" 2>/dev/null || true

# 3. Pitch deck at the root, as the guidelines' example names it.
[ -f "$DEST/deck/final/pitch-deck.pdf" ] || {
  echo "FAIL: deck/final/pitch-deck.pdf missing — run deck/final/build.sh first"; exit 1; }
cp "$DEST/deck/final/pitch-deck.pdf" "$DEST/pitch-deck.pdf"

# 4. Gate: mandatory deliverables + no secrets + no unfilled placeholders.
fail=0
for f in README.md pitch-deck.pdf .env.example docker-compose.yml LICENSE \
         docs/ARCHITECTURE.md docs/FILTERS.md tools/reconcile.sh; do
  [ -e "$DEST/$f" ] || { echo "FAIL: mandatory file missing: $f"; fail=1; }
done
[ -e "$DEST/.env" ] && { echo "FAIL: .env leaked into the package"; fail=1; }
find "$DEST/data" -name '*.csv' 2>/dev/null | grep -q . && {
  echo "FAIL: raw data leaked into the package"; fail=1; }

placeholders=$(grep -nE '<TEAM NAME>|<HOSTED_DEMO_URL>|<VIDEO_URL>|<github-handle>|<Name>' \
  "$DEST/README.md" || true)
[ -n "$placeholders" ] && {
  echo "FAIL: unfilled placeholders in README.md:"; echo "$placeholders"; fail=1; }

size=$(du -sh "$DEST" | cut -f1)
files=$(find "$DEST" -type f | wc -l | tr -d ' ')
[ "$fail" -eq 0 ] || { echo "== NOT submittable ($files files, $size)"; exit 1; }
echo "== OK: $files files, $size — self-contained and placeholder-free"
echo "== next: cd \"$DEST_ROOT\" && git add \"$TEAM\" && git commit && push, then open the PR:"
echo "==   [Submission] $TEAM"
