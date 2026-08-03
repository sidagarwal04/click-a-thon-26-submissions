#!/usr/bin/env bash
# One source of truth for shipped query text. Fails the build if that stops being true.
#
#   ./scripts/check_query_sources.sh
#
# TASK.md 2.2 asks for "a test that fails if any two copies of a query diverge". A diff-based
# test would need to know which copy is canonical and would pass whenever both copies were
# equally wrong, which is exactly the state the repo was in: demo/server.js and
# frontend/src/app/api/* both loaded the same measured-wrong query and agreed with each other
# perfectly. So this asserts the stronger property instead: THERE IS ONLY ONE COPY.
#
# How it went wrong the first time, for whoever has to keep this passing: the dashboard inlined
# its SQL, forked from sql/queries/benchmark/, and the corrected query in sql/queries/serving/
# was never ported across. Both directories existed for hours with a measured 2.1x difference in
# the headline average, and nothing failed.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
note() { printf '%s\n' "$1" >&2; fail=1; }

# 1. No SQL text inline in a route handler. Route handlers must load from sql/queries/serving/.
#    Matches SQL keywords in a template literal, which is how the inline copies were written.
inline="$(grep -rlnE '(^|[^a-zA-Z_])(SELECT|WITH)[[:space:]]+[a-zA-Z(]' \
            --include='route.ts' frontend/src/app/api 2>/dev/null || true)"
if [ -n "$inline" ]; then
  note "FAIL: SQL text inline in a route handler. Load it from sql/queries/serving/ instead:"
  printf '  %s\n' $inline >&2
else
  echo "ok: no route handler carries its own copy of a query"
fi

# 2. Every shipped query has at least one executor. An unexecuted serving query is how the
#    corrected average sat in the repo unused while the wrong one shipped: at that point
#    concurrency_curve.sql, user_concurrency_curve.sql and open_sessions.sql had zero readers.
missing=""
for q in sql/queries/serving/*.sql; do
  base="$(basename "$q")"
  # Referenced by anything that is not the file itself and not a doc describing it.
  if ! grep -rql --exclude-dir=node_modules --exclude-dir=.git --exclude="$base" \
        -e "$base" scripts frontend/src sql 2>/dev/null; then
    missing="$missing $base"
  fi
done
if [ -n "$missing" ]; then
  note "FAIL: serving queries with no executor (nothing in scripts/ or frontend/src/ reads them):"
  printf '  %s\n' $missing >&2
else
  echo "ok: every serving query has at least one executor"
fi

# 3. Nothing user-facing loads a known-wrong fixture. Only the validation harness may, and only
#    to reproduce the published wrong numbers on purpose.
badref="$(grep -rln 'known-wrong' frontend/src 2>/dev/null || true)"
if [ -n "$badref" ]; then
  note "FAIL: a UI loads a known-wrong regression fixture:"
  printf '  %s\n' $badref >&2
else
  echo "ok: no UI loads a known-wrong fixture"
fi

# 4. No live reference to a path that has been retired. Catches docs and scripts left pointing
#    at sql/queries/benchmark/ or demo/ after they were removed. Prose mentions in the review
#    and corrections records are allowed: those documents exist to describe what changed.
#
# Scans TRACKED files only, via git ls-files. Walking the filesystem instead picks up
# frontend/.next/ build output and .dual-graph/ caches, which are gitignored derivatives: a
# stale reference in a build artifact is not a defect, and failing on it trains people to
# ignore this script.
allow='^(docs/review/|docs/corrections\.md|docs/DECISIONS\.md|TASK\.md|sonyliv_|scripts/check_query_sources\.sh)'
for retired in 'sql/queries/benchmark/' 'demo/server\.js' 'demo/index\.html'; do
  hits="$(git ls-files -z | grep -zZv '^evidence/' \
            | xargs -0 grep -ln -e "$retired" 2>/dev/null | grep -Ev "$allow" || true)"
  if [ -n "$hits" ]; then
    note "FAIL: live reference to retired path '$retired':"
    printf '  %s\n' $hits >&2
  fi
done
[ "$fail" = 0 ] && echo "ok: no live references to retired query paths"

exit "$fail"
