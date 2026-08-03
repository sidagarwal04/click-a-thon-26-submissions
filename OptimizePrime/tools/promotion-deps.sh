#!/usr/bin/env bash
# tools/promotion-deps.sh — what does a promotion candidate actually REFERENCE
# that it does not carry?
#
#   tools/promotion-deps.sh <branch>       # e.g. promo/core
#
# WHY THIS EXISTS. Six promotion attempts were rejected; two of them for the
# same structural reason — the branch carried a coherent-looking set of files
# chosen BY CATEGORY (all of tools/, all of sql/) while the tools it promoted
# referenced files outside that category. Check 1 kept failing on "promoted
# tools require omitted dev files", found by hand each time.
#
# A file set should be derived from REFERENCES, not from directory names. This
# derives it: for every file the branch changes, find the repo paths it names,
# and report any that differ from dev but are absent from the branch.
set -euo pipefail
cd "$(dirname "$0")/.."
BR="${1:?usage: tools/promotion-deps.sh <branch>}"
BASE="${2:-main}"

git rev-parse --verify -q "$BR" >/dev/null || { echo "no such branch: $BR" >&2; exit 2; }

CARRIED="$(git diff --name-only "$BASE".."$BR")"
printf 'candidate %s carries %s files\n\n' "$BR" "$(printf '%s\n' "$CARRIED" | grep -c . || true)"

MISSING=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  case "$f" in *.md|evidence/*|docs/*) continue ;; esac      # prose references prove nothing
  git cat-file -e "$BR:$f" 2>/dev/null || continue
  # repo-relative paths mentioned inside the file
  refs="$(git show "$BR:$f" 2>/dev/null \
          | grep -oE '\b(sql|tools|queries|internal|cmd)/[A-Za-z0-9_./-]+' \
          | sort -u || true)"
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    [ -f "$r" ] || continue                                   # FILES only: a Go import path
                                                              # like internal/config is a
                                                              # directory, and sql/. is a glob
                                                              # artifact — neither is a
                                                              # dependency. Reporting them
                                                              # buries the one that is.
    printf '%s\n' "$CARRIED" | grep -qxF "$r" && continue      # the branch carries it
    git diff --quiet "$BASE" dev -- "$r" 2>/dev/null && continue  # identical on main anyway
    printf '  MISSING  %-34s referenced by %s\n' "$r" "$f"
    MISSING=$((MISSING + 1))
  done <<< "$refs"
done <<< "$CARRIED"

echo
if [ "$MISSING" -eq 0 ]; then
  echo "COHERENT — every referenced file that differs from $BASE is carried."
else
  echo "INCOHERENT — $MISSING referenced file(s) differ from $BASE and are NOT carried."
  echo "Add them to the candidate, or explain in the ledger why the reference is inert."
  exit 1
fi
