#!/usr/bin/env bash
# ============================================================================
# tools/evidence.sh — make an interrupted evidence file FAIL instead of lying.
#
# Every evidence writer here follows `: > "$OUT"` then append. Kill one
# mid-write and you do not get a broken file — you get a file whose header is
# intact, whose timestamp and commit hash are fresh and plausible, and whose
# body and verdict are simply absent. It reads as valid and asserts nothing.
#
# That happened on 2026-08-02: evidence/q37/agreement.txt was left with its
# header and none of its four fixture rows or its VERDICT line, after the
# worktree running it was deleted mid-suite. It was caught by eye in `git diff`.
# Nothing would have caught it in review, because there is nothing visibly wrong
# with a short file.
#
# It is the same shape as two other failures the same day, and that is why this
# exists rather than a one-line fix to one script:
#   - a two-sided test reporting CONVERGES on both halves, its sabotage half
#     silent (tools/truncation-test.sh, commit 82382be);
#   - a suite tally reading "3 passed · 2 failed · 8 skipped" with five suites
#     absent, after its own scripts vanished from under it.
# In all three the artifact looks fine and the ABSENCE is the signal. Readers
# check what is present; nobody checks what is missing. So make the writer
# assert its own completeness and let the reader verify one line.
#
# The seal is meaningful only because it is the LAST thing a successful run
# does. Under `set -e` an interrupted run never reaches it, so an unsealed file
# is precisely an incomplete one. Do not move it earlier, do not seal on a
# failure path, and do not seal a file you did not just finish writing.
#
#   . tools/evidence.sh
#   evidence_seal "$OUT"              # last line of a successful run
#   evidence_require_sealed "$OUT"    # in a reader/CI: exits 1 if incomplete
#
# tools/reconcile.sh already does this by hand — it fails when minutes_compared
# is zero or missing, precisely so a gate that saw no data cannot pass by
# silence. This generalises that idea to every evidence file.
# ============================================================================

EVIDENCE_SEAL_TOKEN='#EVIDENCE-COMPLETE'

# evidence_seal <file> — terminator line. Carries the commit so a stale file
# left by an older run is identifiable, not merely present.
evidence_seal() {
  local f="$1"
  [ -n "$f" ] || { echo "evidence_seal: no file given" >&2; return 1; }
  [ -f "$f" ] || { echo "evidence_seal: $f does not exist — nothing was written" >&2; return 1; }
  printf '%s %s %s\n' "$EVIDENCE_SEAL_TOKEN" \
    "$(git rev-parse --short HEAD 2>/dev/null || echo nocommit)" \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" >> "$f"
}

# evidence_require_sealed <file> — exit 1 unless the file ends with the seal.
# Checks the LAST line specifically: a seal anywhere else means the file was
# appended to after it was sealed, which is its own kind of wrong.
evidence_require_sealed() {
  local f="$1"
  if [ ! -f "$f" ]; then
    echo "EVIDENCE MISSING: $f was never written." >&2
    return 1
  fi
  if [ ! -s "$f" ]; then
    echo "EVIDENCE EMPTY: $f exists but has no content." >&2
    return 1
  fi
  local last; last="$(tail -1 "$f")"
  case "$last" in
    "$EVIDENCE_SEAL_TOKEN"*) return 0 ;;
  esac
  if grep -q "^${EVIDENCE_SEAL_TOKEN}" "$f"; then
    echo "EVIDENCE APPENDED AFTER SEAL: $f has a seal, but not as its last line." >&2
    echo "  Something wrote to it after the run that produced it finished." >&2
    return 1
  fi
  echo "EVIDENCE INCOMPLETE: $f has no completion seal." >&2
  echo "  The run that wrote it did not finish — it was killed, or it died on a" >&2
  echo "  path that skips the seal. The file may look complete and be missing its" >&2
  echo "  body and verdict entirely. Do NOT commit it and do NOT read it as a" >&2
  echo "  result. Re-run the producing script." >&2
  echo "  Last line was: ${last}" >&2
  return 1
}
