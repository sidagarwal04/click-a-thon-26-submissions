# design-ch-schema

A portable agent skill (for **opencode**, and compatible with Claude Code / agents-style
skill loaders) that onboards a product/spec into ClickHouse: it reads a raw **NDJSON** events
file, applies the `clickhouse-best-practices` skill, and generates a production-ready DDL
schema — a single `JSON`-column table per event type (with typed hints only for the
`ORDER BY` / `PARTITION BY` paths), a `ch_insert_time` materialized column, a
`CREATE DATABASE` guard, and materialized views when warranted. It validates the DDL locally
with `chdb`, smoke-tests it on ClickHouse Cloud, then commits and raises a PR.

## Contents

```
design-ch-schema/
├── SKILL.md                       # the skill definition (entrypoint)
├── install.sh                     # installer
├── README.md                      # this file
└── references/
    ├── production-ddl-template.md
    ├── chdb-validation.md
    ├── test-walkthrough.md
    └── materialized-views.md
```

## Install

From inside this folder:

```bash
# opencode (global) — ~/.config/opencode/skills
./install.sh

# into the current project — ./.opencode/skills
./install.sh --project

# Claude Code — ~/.claude/skills
./install.sh --target claude

# any explicit directory
./install.sh --dir /path/to/skills
```

Then **restart opencode** — skills and config are loaded once at startup.

### Manual install

Copy the `design-ch-schema/` folder (containing `SKILL.md` and `references/`) into any
skills directory the agent scans, e.g.:

- opencode global: `~/.config/opencode/skills/design-ch-schema/SKILL.md`
- opencode project: `<repo>/.opencode/skills/design-ch-schema/SKILL.md`
- Claude / agents: `~/.claude/skills/…` or `~/.agents/skills/…`

You can also register a custom location in `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "skills": { "paths": ["/abs/path/to/skills"] }
}
```

## Configuration (portable via environment variables)

The skill has no machine-specific hardcoding at runtime — everything is driven by env vars
with sensible defaults. On another user's device, export only what differs:

| Env var | Purpose | Default |
|---|---|---|
| `CH_TARGET_REPO` | Git repo (URL) the schema is committed to | `https://github.com/srinidhi-22/tillthelastrow.git` |
| `CH_TARGET_BRANCH` | Base branch to branch from / open the PR against | `master` |
| `CH_REPO_DIR` | Local clone directory | `$HOME/<repo-name>` |
| `CH_DATABASE` | ClickHouse database all tables/MVs live under | `atlys` |
| `CH_HOST`, `CH_USER`, `CH_PASSWORD` | ClickHouse Cloud credentials (Step 6 smoke test) | — |

Example for a different user/fork:

```bash
export CH_TARGET_REPO=https://github.com/acme/analytics-schemas.git
export CH_TARGET_BRANCH=main
export CH_DATABASE=analytics
export CH_HOST=xxx.clickhouse.cloud CH_USER=default CH_PASSWORD=secret
```

## Prerequisites

The skill installs/checks these automatically at runtime, but for reference it uses:

- `gh` CLI (authenticated) — branch/commit/push/PR
- `git`
- Python 3 with `chdb` (a recent version that supports the `JSON` type)
- Access to a ClickHouse Cloud instance for the smoke test

## Usage

After installing and restarting, trigger the skill by asking the agent, e.g.:

- "onboard product in clickhouse"
- "onboard this spec into clickhouse"
- "design a ClickHouse schema from this ndjson"

The agent then asks three questions — the **spec name**, the **frequently-filtered field(s)**,
and the **metrics most commonly fetched** — and drives the rest end-to-end.
