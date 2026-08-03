# Contributing — PR & branching workflow (3 people, 12 hours)

The goal: everyone builds on everyone else's work continuously, nobody blocks anyone, and `main`
is always runnable. In a 12-hour sprint the enemy is a big PR that lands at hour 9 and breaks
three things. **Small PRs, merged fast, are the whole game.**

## The loop (every task, no exceptions)
```
git checkout main && git pull            # 1. start from everyone's latest
skim teamkit/DECISIONS.md                 # 2. what changed since I last pulled?
git checkout -b <ws>/<short-thing>        # 3. branch off main  e.g. sql/mad-baseline
... build one small thing ...             # 4. ONE reviewable change
git pull --rebase origin main             # 5. rebase on latest before opening the PR
open PR → review → squash-merge           # 6. small, green, merged within ~60–90 min
```
**Pull `main` before you start anything.** Building on a 3-hour-old `main` is how you get conflicts
and duplicated work. Pull first, every time.

## Branch naming — encodes the owner, prevents collisions
`sql/…` (A) · `agent/…` (B) · `integrations/…` `ui/…` (C) · `infra/…` (shared).
Example: `agent/evidence-store`, `sql/adtributor`, `ui/metric-tree`.

## Keep PRs SMALL (this is the ask)
- **One PR = one thing.** "Add MAD baseline MV" — not "detection + attribution + a bug fix."
- Target **< ~200 changed lines**. If it's bigger, split it: land the query, then the wiring, then the test.
- A PR should be **reviewable in 5 minutes** and mergeable the same hour it opened. Stale branches rot.
- Prefer **many small merges** over one perfect big one. Incremental > complete.

## Stay in your lane
- **One owner per directory** (`sql/ agent/ integrations/ ui/`). Edit only yours → near-zero conflicts.
- Need something across a boundary? It's a **contract**, not a shared file: edit
  `teamkit/CONTRACTS.md`, log it in `teamkit/DECISIONS.md`, announce it — then both sides code to it.
- `CLAUDE.md` + `teamkit/CONTRACTS.md` change **by announcement only**.

## PR checklist (paste into the PR description)
```
- [ ] Branched off latest main; rebased before opening
- [ ] One logical change, < ~200 lines
- [ ] Only touches my directory (or a contract change is announced + logged)
- [ ] main still runs (run_incident.py end-to-end didn't break)
- [ ] Docs updated in THIS PR if behavior/interface changed
- [ ] No secrets, no data files committed (.env, *.parquet)
```

## Review — fast, not heavy
- **1 approval** is enough. Trust + speed over ceremony. If the reviewer is heads-down, self-merge
  a small in-lane change and post the diff link in the channel — but never for a contract change.
- **Squash-merge** so `main` history is one line per change (clean, easy to bisect).
- If CI/dry-run is red, it doesn't merge. `main` runnable is sacred.

## Conflicts & sync
- Two PRs touching the same file = a missing contract. Add the contract; don't both edit the file.
- Merge conflict on a rebase? It's small because the PR is small — resolve in your lane and move on.
- **Hourly:** everyone pulls `main`. At the hour-7 and hour-9 checkpoints, a 2-min "what merged
  since?" so no one is building on a stale mental model.

## When to relax this
Last ~90 min before the freeze: stop opening new feature PRs. Only merge fixes that make the demo
and the unseen-incident run solid. Freeze the code ~2h before the unseen drop; branch for anything risky.
