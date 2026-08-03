#!/usr/bin/env bash
# tools/fetch_data.sh — download the provided SonyLIV datasets into data/.
#
# The organiser repo stores the CSVs in Git LFS, so the normal
# raw.githubusercontent.com URL returns a 132-byte *pointer file*, not data.
# We fetch from media.githubusercontent.com instead, which resolves LFS objects
# server-side — plain curl, no git-lfs install, no clone of a 330 MB repo.
#
# Every file is checksum-pinned to the sha256 in the upstream LFS pointer, so a
# truncated download or a silently re-published dataset fails loudly here rather
# than showing up as wrong concurrency numbers three hours later.
#
#   tools/fetch_data.sh              # fetch what is missing, verify what is there
#   tools/fetch_data.sh --force      # re-download even if present and valid
#   tools/fetch_data.sh --verify     # verify only, download nothing
#   DATA_DIR=/tmp/x tools/fetch_data.sh
set -euo pipefail

cd "$(dirname "$0")/.."
DATA_DIR="${DATA_DIR:-data}"
BASE="${DATA_BASE_URL:-https://media.githubusercontent.com/media/sidagarwal04/click-a-thon-2026/main/SonyLiv/data}"

# name  sha256  bytes — from the upstream LFS pointers (git cat-file blob HEAD:<path>)
FILES=(
  "ch-hackathon-raw-data.csv     15ce6df78e7239820fb9951f2a5c68de2abb47a0950068947e1a0344a0283a96 232827255"
  "ch-hackathon-content-data.csv e013c4958e9b6396f9cc6cd2681bb6944bb65dc810b7f0925f78254ed9c7ddd4 1181455"
)

# The spec docs live beside the CSVs upstream. Fetching only the data is how we
# built for a day and a half against ONE of three spec files: README_START_HERE.md
# and dataset_details.md were never read, and between them they require content
# enrichment, user-level concurrency and 10 filter dimensions. Never again — the
# docs come down with the data.
DOCS_BASE="${DOCS_BASE_URL:-https://raw.githubusercontent.com/sidagarwal04/click-a-thon-2026/main/SonyLiv}"
SUBMISSION_DOCS_BASE="${SUBMISSION_DOCS_BASE_URL:-https://raw.githubusercontent.com/sidagarwal04/click-a-thon-26-submissions/main}"
# source path|vendored name. The unseen spec lives in a subdirectory upstream
# but is flattened here so every contract can be found with docs/upstream/*.md.
DOCS=(
  "PROBLEM_STATEMENT.md|PROBLEM_STATEMENT.md"
  "README_START_HERE.md|README_START_HERE.md"
  "dataset_details.md|dataset_details.md"
  "unseen_data/spec.md|unseen_spec.md"
)
SUBMISSION_DOCS=(
  "SONYLIV_SUBMISSION_GUIDELINES.md|SONYLIV_SUBMISSION_GUIDELINES.md"
  "README.md|SUBMISSIONS_README.md"
)

fetch_docs() {
  mkdir -p docs/upstream
  local entry src dest
  for entry in "${DOCS[@]}"; do
    src="${entry%%|*}"; dest="${entry#*|}"
    if curl -fsSL --retry 2 -o "docs/upstream/$dest.tmp" "$DOCS_BASE/$src"; then
      if [ -f "docs/upstream/$dest" ] && ! cmp -s "docs/upstream/$dest.tmp" "docs/upstream/$dest"; then
        echo "  !! UPSTREAM SPEC CHANGED: docs/upstream/$dest — re-read it before trusting the model"
      fi
      mv "docs/upstream/$dest.tmp" "docs/upstream/$dest"
    else
      rm -f "docs/upstream/$dest.tmp"
      echo "  could not fetch $src (continuing)" >&2
    fi
  done
  for entry in "${SUBMISSION_DOCS[@]}"; do
    src="${entry%%|*}"; dest="${entry#*|}"
    if curl -fsSL --retry 2 -o "docs/upstream/$dest.tmp" "$SUBMISSION_DOCS_BASE/$src"; then
      if [ -f "docs/upstream/$dest" ] && ! cmp -s "docs/upstream/$dest.tmp" "docs/upstream/$dest"; then
        echo "  !! SUBMISSION CONTRACT CHANGED: docs/upstream/$dest — re-read it before submitting"
      fi
      mv "docs/upstream/$dest.tmp" "docs/upstream/$dest"
    else
      rm -f "docs/upstream/$dest.tmp"
      echo "  could not fetch submission $src (continuing)" >&2
    fi
  done
  echo "problem and submission docs synced to docs/upstream/"
}

MODE=fetch
case "${1:-}" in
  --force)  MODE=force ;;
  --verify) MODE=verify ;;
  "")       ;;
  *) echo "usage: tools/fetch_data.sh [--force|--verify]" >&2; exit 2 ;;
esac

# macOS ships shasum, most Linux images ship sha256sum. Take whichever exists.
if command -v sha256sum >/dev/null 2>&1; then
  sha256() { sha256sum "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
  sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }
else
  echo "need sha256sum or shasum on PATH" >&2; exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "need curl on PATH" >&2; exit 1; }
mkdir -p "$DATA_DIR"

rc=0
for entry in "${FILES[@]}"; do
  # shellcheck disable=SC2086
  set -- $entry
  name="$1" want="$2" bytes="$3"
  dest="$DATA_DIR/$name"
  human=$(( (bytes + 524288) / 1048576 ))

  if [ -f "$dest" ] && [ "$MODE" != force ]; then
    printf 'verifying %s ... ' "$name"
    got=$(sha256 "$dest")
    if [ "$got" = "$want" ]; then
      echo "ok (${human} MB)"
      continue
    fi
    echo "CHECKSUM MISMATCH"
    echo "  expected $want"
    echo "  got      $got"
    if [ "$MODE" = verify ]; then rc=1; continue; fi
    echo "  re-downloading"
  elif [ "$MODE" = verify ]; then
    echo "missing $dest"; rc=1; continue
  fi

  # Download to .part and rename only after the checksum passes, so an
  # interrupted run never leaves a half file that looks complete to load.sh.
  # -C - resumes an earlier interrupted attempt instead of restarting 222 MB.
  echo "downloading $name (${human} MB) from $BASE"
  curl -fL --retry 3 --retry-delay 2 -C - --progress-bar -o "$dest.part" "$BASE/$name"

  got=$(sha256 "$dest.part")
  if [ "$got" != "$want" ]; then
    # curl -f already aborts a truncated transfer, so a bad checksum here means
    # the bytes themselves are wrong, not incomplete. Resuming would re-verify
    # the same wrong file forever — discard it so the next run starts clean.
    rm -f "$dest.part"
    echo "checksum mismatch after download for $name" >&2
    echo "  expected $want" >&2
    echo "  got      $got" >&2
    echo "  upstream may have republished the dataset — check $BASE" >&2
    rc=1
    continue
  fi
  mv "$dest.part" "$dest"
  echo "verifying $name ... ok (${human} MB)"
done

[ $rc -eq 0 ] || exit $rc

fetch_docs

echo
echo "datasets ready in $DATA_DIR/ — next: tools/load.sh"
