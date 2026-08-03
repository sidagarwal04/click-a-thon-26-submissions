---
name: atlys-registry-sync
description: Optionally mirror the Atlys context bundle into a queryable ClickHouse context_registry table (so the Analytics Agent can fetch the current context version over the ClickHouse MCP) and/or commit + PR the knowledge bundle. Invoke only when queryable lineage or a PR is explicitly requested — files remain the source of truth.
---

# Skill: Registry Sync & Commit/PR (optional)

Both steps are **optional** — the markdown files under `KB_DIR` are always the source of truth.
Only do these when explicitly requested.

## A — Mirror to ClickHouse `context_registry`

Lets the Analytics Agent fetch "current context version" over the ClickHouse MCP. This is a
mirror, not the source.

```sql
CREATE TABLE IF NOT EXISTS atlys.context_registry
(
    context_version  UInt32,
    updated_at       DateTime64(3, 'UTC') DEFAULT now64(3),
    trigger          LowCardinality(String),
    concept_path     String,
    change_kind      LowCardinality(String),   -- added | updated | contradiction
    summary          String,
    body_md          String
)
ENGINE = MergeTree
PARTITION BY context_version
ORDER BY (context_version, concept_path);
```

Insert one row per changed concept for the new version. Skip entirely if files-only is the
chosen design.

## B — Commit + PR

Only when explicitly requested **and** shell/git is available (the pure filesystem-MCP path just
writes files — no git). Uses the same portable env vars as the Instrumentation Agent.

```bash
CH_TARGET_REPO="${CH_TARGET_REPO:-https://github.com/srinidhi-22/tillthelastrow.git}"
CH_TARGET_BRANCH="${CH_TARGET_BRANCH:-master}"
CH_REPO_SLUG="$(echo "${CH_TARGET_REPO%.git}" | sed -E 's#https?://[^/]+/##')"

cd "$REPO_DIR"
git checkout "$CH_TARGET_BRANCH" && git pull --ff-only origin "$CH_TARGET_BRANCH"
EPOCH=$(date +%s)
git checkout -b context/update-v{N+1}-${EPOCH}
git add librechat/context_docs/
git commit -m "chore(context): update living context to v{N+1} ({trigger})"
git push --set-upstream origin context/update-v{N+1}-${EPOCH}
gh pr create --repo "$CH_REPO_SLUG" --base "$CH_TARGET_BRANCH" \
  --head context/update-v{N+1}-${EPOCH} \
  --title "chore(context): living context v{N+1}" \
  --body "Context bump to v{N+1}. See librechat/context_docs/log.md for the diff."
```

Report the PR URL when done. For the correct-GitHub-host handling (enterprise vs github.com),
follow the same host-derivation approach as the Instrumentation Agent's `atlys-git-pr` skill.
