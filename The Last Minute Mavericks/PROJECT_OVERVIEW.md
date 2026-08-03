# clickathon-inmobi-2026 — Automated Root-Cause Analyst

ClickHouse Click-a-thon India 2026 · **InMobi track**: *from alert to answer.* A metric moves;
this system detects it, drills down **in ClickHouse SQL** to the responsible segment, and an LLM
narrates a diagnosis where **every number is computed, never invented** — with a Langfuse trace
a judge can audit.

## ▶ Just want to run it? → **[`USAGE.md`](USAGE.md)** (3 minutes, no local data)

## Start here (in order)
1. **[`CLAUDE.md`](CLAUDE.md)** — the shared agent context; auto-loads into every Claude Code terminal. Read first.
2. **[`teamkit/`](teamkit/)** — all shared context lives here. Open **[`teamkit/README.md`](teamkit/README.md)** for the map. In short:
   - [`teamkit/docs/`](teamkit/docs/) — organizer problem statement, glossary, and our data profile
   - [`teamkit/CONTRACTS.md`](teamkit/CONTRACTS.md) — frozen interfaces (freeze at hour 1)
   - [`teamkit/TASKS.md`](teamkit/TASKS.md) — the 12-hour plan + role split
   - [`teamkit/DEMO.md`](teamkit/DEMO.md) — the 5-minute demo beat sheet + UI spec
   - [`teamkit/CONTRIBUTING.md`](teamkit/CONTRIBUTING.md) — **PR & branching workflow (read before your first commit)**
   - [`teamkit/DECISIONS.md`](teamkit/DECISIONS.md) — changelog; skim on every `git pull`

## Repo layout
```
CLAUDE.md            auto-loaded context (root — required here)
README.md  LICENSE   this file + MIT
teamkit/             shared context: contracts, plan, demo, decisions, docs, setup
  ├─ CONTRIBUTING.md PR workflow
  └─ setup.sh        run once after the hack begins → scaffolds the code dirs below
sql/ agent/ integrations/ ui/   solution code (one owner each), created during the hack
run_incident.py      one-command pipeline (build first)
```

## How we work (the short version)
- **ClickHouse computes, the LLM only narrates.** All detection/attribution is deterministic SQL. The LLM is called once, and a validator makes it impossible to state a number no query produced.
- **The repo is the single source of truth.** Contracts change by: announce → edit `teamkit/CONTRACTS.md` → log in `teamkit/DECISIONS.md` → then code.
- **Small PRs, pull `main` first, one owner per directory.** See [`teamkit/CONTRIBUTING.md`](teamkit/CONTRIBUTING.md).
- **Data lives in ClickHouse**, not in git. Load once into the team service; everyone queries it.

Run [`teamkit/setup.sh`](teamkit/setup.sh) once (after the hack begins) from the repo root to scaffold directories, `.env`, and per-terminal worktrees.

> Licensed under [MIT](LICENSE). Make the repo **public before the submission deadline** (a hard requirement).
