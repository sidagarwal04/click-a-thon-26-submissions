<!-- Keep it small: one logical change, < ~200 lines, mergeable this hour. -->

## What & why
<!-- One or two lines. What does this change and why now? -->

## Scope
- Directory/owner: <!-- sql / agent / integrations / ui / infra -->
- Contract change? <!-- no · or: yes → link the teamkit/CONTRACTS.md + teamkit/DECISIONS.md edit -->

## Checklist
- [ ] Branched off latest `main`; rebased before opening
- [ ] One logical change, < ~200 lines
- [ ] Only touches my directory (or a contract change is announced + logged in `teamkit/DECISIONS.md`)
- [ ] `main` still runs — `run_incident.py` end-to-end didn't break
- [ ] Docs updated in THIS PR if behavior/interface changed
- [ ] No secrets, no data files (`.env`, `*.parquet`)

<!-- 1 approval + squash-merge. If CI/dry-run is red, it doesn't merge. -->
