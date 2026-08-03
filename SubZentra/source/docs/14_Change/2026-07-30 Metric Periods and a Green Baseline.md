---
id: release-2026-07-30-metric-periods-green-baseline
title: 2026-07-30 Metric Periods and a Green Baseline
type: release
status: active
owner: unassigned
source: release
created: 2026-07-30
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
priority: normal
tags: [release, change]
related:
  ["[[Change MOC]]", "[[Forensic Observatory]]", "[[Test Strategy]]", "[[Configuration Reference]]"]
repo_path: docs/14_Change
---

# 2026-07-30 Metric Periods and a Green Baseline

Closes the two issues left open after the confidence-calibration and
documentation work: a metric that could not state its own period, and a CI
baseline that had never been green in this repository's history.

## User-visible changes

**A metric now states the period it compares.** Every metric row used to read
"June X → July Y", hardcoded from the only scenario that existed when the
component was written, so the first live run of the second scenario captioned an
October–November finding as June–July. Correct numbers, invented period — the
failure the confidence ceilings exist to prevent, one layer up. `MetricComparison`
now carries `previous_label` and `current_label`, filled by the SQL Analyst,
which is the only party that knows because it chose the granularity. Where no
period applies the row shows values alone rather than a guess. See
[[Forensic Observatory]].

**Blank configuration means unconfigured, for every optional variable.** Not
just `CLERK_AUDIENCE`, which is the one that bit. See
[[Configuration Reference]].

**The design system enforces one contract across every component.** 510
assertions covering `className`, `ozid`, ref forwarding, HTML attribute
pass-through, variants and modifiers. Reaching it required fixing the components
that never forwarded props rather than relaxing anything. See [[Test Strategy]].

One convention changed: `Tooltip` put its plain `ozid` on the trigger while
`theme.root` styled the popup, inverting the rule every other component follows.
The popup now carries the plain `ozid` and the trigger takes `ozid__trigger`.

## Compatibility and migration

`previous_label` and `current_label` are optional in the domain and nullable in
the agent schema, so investigations persisted before this change still load and
render — the reader is told nothing rather than told a guess.

All six cassettes were re-recorded, because the analyst prompt changed and
recordings key on a hash of the request. `na_growth_premium` reproduced its 0.85
`capped_independence_partial` publish exactly. Three moved on live model
variance rather than on this change: `na_growth_free` now agrees on sample size
and publishes where it previously hit the contradiction gate, `free_collapsed`
now demonstrates the NONE independence ceiling binding rather than a recheck
retry, and `premium_tier` self-reported 0.35 instead of 0.55. Every calibration
method and both approval-gate reasons remain represented across the set; each
`expect.json` note records what its cassette now demonstrates. Twenty-seven
recordings orphaned by the prompt change were pruned.

No schema migration. No operator action.

## Verification

- `nx run-many -t lint test build typecheck` — all 32 projects
- `nx run evals:replay` — 6/6 reproduced, $0
- `nx run evals:check` — 20/20
- `ruff check` and `lint-imports` — clean, 3/3 contracts
- `nx run docs:check` — vault validating
- Read in a browser on **both** scenarios: North America captions
  `October 2026 → November 2026`, EU captions `June 2026 → July 2026`. Checking
  one alone is how the original bug survived, because the hardcoded caption
  matched EU by luck.

## Known limitations

Two changes warrant review before they are treated as settled. The `Tooltip`
`ozid` move is a convention change; no current consumer queries a tooltip's
`ozid`, but that is a fact about today's callers rather than a guarantee.

In `use-sync-status`, the hook keeps its own copy of `isOnline` and mirrors
context into it through an effect. Removing the duplicate is the better shape —
the provider already tracks it from the same coordinator events — but doing so
narrows a public hook's contract to require the provider, and nothing in the
suite would catch the difference. The duplicate stands, deliberately, with the
reasoning recorded at the call site.

The `CLERK_AUDIENCE` JWT-template hardening remains parked. It needs a Clerk
template, `tokenTemplates` wiring, and the environment variable to land
together.

Parent: [[Change MOC]]
