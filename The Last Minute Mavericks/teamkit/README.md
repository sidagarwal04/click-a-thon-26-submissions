# teamkit/ — the team's shared context

Everything the team and its AI agents need to build in sync, in one place. This is **planning,
reference, and process** — not solution code (code lives in the root `sql/ agent/ integrations/
ui/` dirs). Read `../CLAUDE.md` first (it auto-loads into every terminal), then use this folder
as the source of truth for *how* and *what*.

| File | What it's for | When you read it |
|---|---|---|
| [`RUNBOOK.md`](RUNBOOK.md) | **Run the live system** — hit the deployed API + run the UI against shared services, no local data | **First, to see it running** (`RCOS_API=http://23.101.175.68:8077`) |
| [`UNSEEN_DATASET.md`](UNSEEN_DATASET.md) | **Run a new/sealed slice locally** — load into `rca_unseen`, scan, swap the UI's input | When the unseen data drops (or to rehearse the swap beforehand) |
| [`prd/`](prd/) | **Per-person PRDs** (A/B/C) — your complete marching orders + the shared acceptance test | Find your PRD first, then build against `CONTRACTS.md` |
| [`CONTRACTS.md`](CONTRACTS.md) | Frozen interfaces between workstreams — schema, cube, Evidence Store/Bundle, algorithm shapes | Before writing any code; **freeze at hour 1** |
| [`STACK_INTEGRATION.md`](STACK_INTEGRATION.md) | How all 4 OSS integrate deeply — "ClickHouse three ways", per-stack superficial✗/deep✓ | Before wiring Langfuse / ClickStack / LibreChat |
| [`TASKS.md`](TASKS.md) | The 12-hour plan, 3-person role split, phase-by-phase checklist | At kickoff, then to pick your next task |
| [`DEMO.md`](DEMO.md) | The 5-minute demo beat sheet + the one-page UI spec | Person C; and everyone before recording |
| [`DECISIONS.md`](DECISIONS.md) | Append-only changelog of every contract/scope change | **Skim on every `git pull`** |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | PR & branching workflow — small PRs, pull-first, one owner per dir | Before your first commit |
| [`docs/`](docs/) | Organizer ground truth (problem statement, glossary) + our data profile | Reference; read `docs/DATA.md` before SQL |
| [`setup.sh`](setup.sh) | Scaffolds code dirs, `.env`, and per-terminal git worktrees | Run once, right after the hack begins |

**Why a folder and not the repo root:** keeps the shared context together and out of the way of
the code dirs that appear during the hack. The one exception is `CLAUDE.md`, which *must* sit at
the repo root so Claude Code auto-loads it into every teammate's terminal.

**Golden rule:** the repo is the single source of truth. Any interface change goes
`CONTRACTS.md` → `DECISIONS.md` → code, announced in the channel — never a side conversation.
