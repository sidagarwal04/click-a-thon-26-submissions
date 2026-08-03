#!/usr/bin/env bash
# One-time repo + worktree setup so 4 Claude terminals never fight over files.
# Run once from the Captain's machine after the GitHub repo exists.
set -euo pipefail

# 0. from inside your cloned repo on `main`, with CLAUDE.md/CONTRACTS.md/TASKS.md committed:
git checkout main && git pull

# 1. skeleton directories, one owner each
mkdir -p sql agent integrations ui contracts/fixtures submission   # docs live in teamkit/
touch sql/.keep agent/.keep integrations/.keep ui/.keep
: > run_incident.py   # BUILD THIS FIRST (hour 2) — ingest→detect→attribute→narrate→trace

# 2. env template (real values go in .env, which is gitignored)
cat > .env.example <<'EOF'
CLICKHOUSE_HOST=
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=rca
LANGFUSE_HOST=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LLM_API_KEY=
EOF
# keep secrets and heavy raw data out of git — data-of-record is ClickHouse, not the repo
for pat in '.env' 'data/' '*.parquet' '__pycache__/' '.venv/' '.playwright-mcp/'; do
  grep -qxF "$pat" .gitignore 2>/dev/null || echo "$pat" >> .gitignore
done

git add -A && git commit -m "Scaffold: dirs, env template, contracts" && git push

# 3. one branch + one worktree per terminal — isolated working copies, no file conflicts
for ws in sql agent integrations ui; do
  git branch "ws/$ws" 2>/dev/null || true
  git worktree add "../rca-$ws" "ws/$ws"
done

echo
echo "Done. Assign terminals (3 people, 4 terminals — B drives 2):"
echo "  Terminal A -> cd ../rca-sql          (person A: sql/, the cube + all analysis SQL)"
echo "  Terminal B -> cd ../rca-agent        (person B: agent/ + run_incident.py, trust layer)"
echo "  Terminal C -> cd ../rca-integrations (person C: Langfuse/LibreChat/ClickStack)"
echo "  Terminal D -> cd ../rca-ui           (person C later: Streamlit page, then deliverables)"
echo
echo "Each terminal: copy .env.example to .env and paste the SHARED creds."
echo "Merge to main every ~90 min:  git pull origin main --rebase && ... && git push"
