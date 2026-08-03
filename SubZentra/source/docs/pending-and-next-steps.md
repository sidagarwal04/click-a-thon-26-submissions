# Pending Work and Next Steps

**Status briefing — 30 July 2026 · `main` at `ab1b99b`**

> This is an ungoverned working document, placed alongside
> `foundation-architecture-review-plan.md` rather than in a managed vault folder,
> so `docs:check` does not validate it. It is a point-in-time snapshot and will
> go stale — treat the repository and GitHub as the source of truth, not this file.

Issues #5 and #4 are closed, PR #8 is merged, and CI passed on `main` for the
first time in this repository's history. What follows is every open thread
evidenced from the repo — separated by who has to act, and ordered by
recommended sequence.

## At a glance

| | |
| --- | --- |
| Open PRs | **0** — #1, #3, #7, #8 all merged |
| Open issues | **0** — #5 and #4 auto-closed by #8 |
| `main` | `ab1b99b` |
| CI on `main` | **pass** (run `30530911382`) |
| Vault | 80 governed notes, validating |
| `foundation-design-system` | 510/510 |

Every figure was read from `gh` and the toolchain, not remembered. The three
merges before #8 — for PRs #7, #3 and #1 — all failed CI.

---

## 1. Only you can do these

Credentials and account access. These cannot be delegated regardless of
authorisation.

### Rotate the Clerk secret key — **do first**

It appeared in an earlier session transcript. Nothing in the repository reads
it: token verification is JWKS-based via `PyJWKClient` with no server-side Clerk
SDK call. Rotation needs no code change and cannot break the build or CI.

The variables that *do* matter to the app are `CLERK_ISSUER` and the browser's
`VITE_CLERK_PUBLISHABLE_KEY`. Neither is the secret being rotated.

- **Where:** Clerk dashboard → API keys
- **Blast radius:** none in this repo
- **Effort:** minutes

### Decide whether the `gh` account switch should stick

The active GitHub CLI account kept reverting to `gtg-lyric`, which cannot
resolve `openzentra/nexus`. That is why the first `gh pr create` failed, and why
the first CI monitor sat silent instead of reporting — it was swallowing an auth
error and retrying, which looks identical to "still running". It is currently
switched to `GowthamTG`.

Git pushes were never affected; those go through the `github-personal` SSH alias.

- **Effort:** minutes
- **Risk if ignored:** confusing tooling failures later

---

## 2. Two decisions that deserve a second opinion

Both shipped in PR #8 and are recorded in the release note. Neither is a bug;
both are judgement calls where a reviewer could reasonably choose otherwise.

### Tooltip moved its `ozid` from trigger to popup

Every other component puts the plain `ozid` on the element `theme.root` styles,
with suffixed ids on sub-slots. Tooltip inverted that: the plain id sat on the
trigger `<span>` while `theme.root` styled the popup `<div>` — and the spec's
`rootInstanceOf` has always been `HTMLDivElement`, which only the popup is. The
plain id now sits on the popup; the trigger takes `ozid__trigger`.

**Argument against:** it is a public convention change. No consumer anywhere
currently queries a tooltip's `ozid`, but that is a fact about today's callers,
not a guarantee about analytics selectors or future E2E tests.

- **File:** `libs/foundation/design-system/src/components/tooltip/tooltip.tsx`
- **Reversible:** yes, one line

### `use-sync-status` keeps a duplicate `isOnline` on purpose

The hook mirrors context into local state through an effect, which the React
Compiler flags as a cascading render. The duplicate was originally removed —
the provider already tracks `isOnline` from the identical coordinator events —
and that was challenged. Testing proved the challenge right: the existing spec
injects the internals context directly, so removing the local copy silently
narrows a public hook's contract from *"self-sufficient given a coordinator"* to
*"requires the provider to track connectivity for me"*, and no test in the suite
would catch it.

The change was reverted and the single lint error suppressed with that reasoning
at the call site. If the narrower contract is later judged correct, the change is
small — but it wants its own PR and a test pinning the coupling.

- **File:** `libs/foundation/data-layer/src/hooks/use-sync-status.ts`
- **Currently:** lint-suppressed, behaviour unchanged

---

## 3. Documented debt, sized and diagnosed

Real, evidenced, and nobody's emergency. Each is a candidate GitHub issue.

### Four foundation libraries have zero tests

PR #3 added placeholder specs to stop vitest exiting non-zero on an empty run,
but these have no real coverage. Two are nearly empty and arguably fine; two are
not.

| Library | Specs | Source files | Read |
| --- | ---: | ---: | --- |
| `foundation-hooks` | 0 | 5 | Consumed by data-layer and auth. Small, but real logic. |
| `foundation-mocks` | 0 | 5 | Test-support code; low value to test directly. |
| `foundation-adapters` | 0 | 1 | Effectively a stub. |
| `foundation-trackers` | 0 | 1 | Effectively a stub. |

For contrast, the covered libraries: `design-system` 33 specs over 269 sources
(510 tests), `utils` 20, `data-layer` 18, `http` 9, `query-engine` 8, `auth` 8.

- **Effort:** hours, per library · **Blocks:** nothing

### `foundation-metrics` is the last library not source-first

Its `package.json` exports resolve to `./dist/index.js` and `./dist/index.d.ts`,
while `http`, `query-engine`, `icons` and the rest resolve straight to
`./src/index.ts`. It works today only because a built `dist/` happens to be
present.

This is Critical #1 in `foundation-architecture-review-plan.md`, verified still
current. Only `foundation-data-model` imports it, so the blast radius is small.

- **Effort:** ~1h

### The architecture review plan is unreconciled and ungoverned

`docs/foundation-architecture-review-plan.md` is 358 lines of findings across 13
libraries — critical/high/medium/low buckets, per-library remediation, a public
API change list, and a three-phase execution order. It sits at the vault root
rather than in a managed folder, so `docs:check` never validates it and it
carries no frontmatter, status, or owner.

`Documentation Backlog` already flags this: *"reconcile and complete … without
treating its planned findings as current behavior."* Three findings were
spot-checked — the metrics packaging item is still live; the `http` and
`query-engine` export-map items no longer match those `package.json` files, so
they need re-verifying rather than trusting.

- **Effort:** half a day to triage
- **Risk:** a stale plan mistaken for current state

### `.scratch/` does not exist, but three places say it does

`CLAUDE.md` states *"Issues and specs live as markdown files under
`.scratch/`"*, `docs/agents/issue-tracker.md` documents the workflow, and the
Change MOC points at it. The directory is absent — in practice this work has
been tracked in GitHub issues.

Either adopt `.scratch/` or delete the references. Right now an agent reading
`CLAUDE.md` will look for a tracker that is not there.

- **Effort:** minutes · **Affects:** every future agent session

### `zentra-os-e2e` fails locally for anyone with a Clerk key

The test asserts the "Connect Clerk" setup screen, which stops rendering once
`apps/zentra-os/.env.local` supplies a publishable key. That file is gitignored,
so CI is unaffected and passed — but every developer with a working local setup
sees a red e2e run and has to remember it is a false alarm.

The fix is for the test to set up its own environment rather than depend on the
absence of one.

- **Effort:** ~1h · **CI impact:** none

### Nx reports three flaky typecheck tasks

`foundation-bridge`, `foundation-metrics` and `foundation-query-engine` were
flagged flaky across runs. They pass now. Flakiness in `tsc --build` usually
means stale `tsbuildinfo` or project-reference ordering — worth watching before
trusting a green run unconditionally.

- **Status:** unverified cause

---

## 4. Not built yet

From `Current Implementation Status` and `Known Unknowns`. Roadmap, not debt —
listed so nothing surprises you later.

**Product surface not implemented:** Insight and Root-Cause agents and the
remaining Growth-stage agents; deletion tombstones; the cost-ceiling circuit
breaker; a cross-vendor Evaluator for the premium tier; recovery for a pipeline
interrupted mid-run; generalized scheduling; arbitrary datasets and questions;
production deployment; a release process.

**Ten open questions** the repository cannot answer alone: component ownership
(no CODEOWNERS), release and versioning strategy, production hosting, deployment
promotion and rollback, secret management, Neon/ClickHouse connectivity checks,
a Langfuse tenant trace, incident and on-call process, agent behaviour against a
live model with known-answer cases, and mid-run pipeline recovery.

> **Operational constraint worth remembering.** Gemini's free tier caps at 20
> requests per day — roughly three investigations. Past that the free chain
> collapses onto a single provider and its independence grade drops to `NONE`,
> which caps confidence at 0.50 and gates everything. That is the system behaving
> correctly, but it looks like a regression if the cap has been forgotten.

---

## 5. Recommended order

1. **Rotate the Clerk secret key.** Minutes, no code change, and the only item
   with an actual exposure attached.

2. **Protect `main` now that it is green.** CI has passed exactly once. A branch
   protection rule requiring the `CI` check is the cheapest way to bank the work
   in PR #8. Without it the baseline can quietly go red again — which is exactly
   how it stayed red through four merges.

3. **Resolve the two review decisions.** Tooltip's `ozid` and the
   `use-sync-status` duplicate. Both are cheap to reverse today and get more
   expensive as callers accumulate.

4. **Fix the `.scratch/` mismatch.** Minutes, and it removes a documented
   instruction pointing at nothing — which affects every future agent session.

5. **Triage the architecture review plan into real issues.** The largest body of
   diagnosed-but-unactioned work in the repo. Re-verify each finding against
   current code — at least one appears to have moved since it was written — then
   file what survives and delete what does not. Give the surviving document
   proper frontmatter so `docs:check` governs it.

6. **Then pick a direction: coverage, or product.** The foundation test gaps and
   the metrics packaging fix are contained and safe. The Insight and Root-Cause
   agents are the next real product capability. Both are reasonable; they are not
   the same kind of work, and alternating tends to finish neither.

---

## 6. What is deliberately not being chased

Recorded so it is a decision rather than an oversight.

- **The local `zentra-os-e2e` failure**, until someone is annoyed enough by it.
  CI passes; it is a false alarm with a known cause.
- **Tests for `foundation-adapters` and `foundation-trackers`.** One source file
  each; there is nothing meaningful to assert yet.
- **The `CLERK_AUDIENCE` JWT-template hardening.** Still parked. It needs a Clerk
  template, `tokenTemplates` wiring, and the environment variable to land
  together — any one alone breaks authentication.
- **Re-recording cassettes** without a reason. Each pass costs money and moves
  the calibration story; three of six scenarios changed which bound they
  demonstrate on the last run, purely from live model variance.

---

*Compiled from the repository and GitHub on 30 July 2026. Every count verified
in-session.*
