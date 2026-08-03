---
id: reference-test-strategy
title: Test Strategy
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [operations, testing, quality]
related: ["[[Operations MOC]]", "[[CI Verification Workflow]]", "[[Dependency Boundaries]]"]
repo_path: .github/workflows/ci.yml
code_refs:
  - .github/workflows/ci.yml
  - vitest.workspace.ts
  - apps/zentra-os-e2e/playwright.config.ts
---

# Test Strategy

## Contract and domain

Pytest covers Agent Port models and Investigation lifecycle, outcomes, evidence,
attempt limits, approval semantics, and terminal immutability. Import Linter and
the known-bad fixture enforce architecture.

## Integration

Postgres tests apply real migrations and cover RLS, fail-closed context,
multi-Tenant Membership, provider bindings, constraints, locking, and outbox
atomicity. ClickHouse tests cover append/replay, deduplication, ordering,
metadata policy, tenant filters, and restricted grants. Cube tests query all
governed metrics and deterministic EU totals.

## API and frontend

API tests cover readiness, identity, roles, scenario validation, cross-Tenant
privacy, approval conflict/replay, safe failures, and traces. Vitest covers
frontend identity, role, approval, terminal, error, deep-link, and reduced-motion
states. Playwright provides browser and automated accessibility smoke coverage.

## The design system contract

`describeComponent` in `libs/foundation/design-system/src/test` asserts one
contract against every component: it accepts `className` and `ozid`, forwards a
ref to its root element, passes `lang`, `aria-*` and `data-*` through to that
root, and resolves its declared variants and modifiers from the theme. A
component declares what it supports; the harness generates the tests. That is
most of the suite's 510 assertions, and it is why adding a component costs
almost no test-writing.

Two escape hatches exist, and both narrow *where* the contract applies rather
than whether it does. `renderRoot` is for a compound component whose outer root
is a context provider rendering no DOM node — Modal, Drawer, Popover, Select and
Menu are all Base UI roots of this shape — so the component nominates the
element that does reach the document, usually its `Content` slot, and the
contract is asserted there. `rootSlot` names the theme slot that element is
styled from when it is not `root`. Neither removes an obligation: the component
still has to accept every one of those props somewhere.

The convention the harness depends on is that the plain `ozid` identifies the
element `theme.root` styles, and sub-slots take suffixed ids (`ozid__trigger`).
A component that inverts this will fail the contract, correctly.

## Recorded live runs

`nx run evals:replay` serves committed recordings of real model output through
the real graph, the real confidence bounds, and the real database, without
calling a provider. It is the offline regression gate for calibration: one paid
run became a permanent fixture, and a change that alters a gating decision fails
here for nothing.

Changing a prompt, an output schema, or anything feeding `render_catalog`
invalidates every recording — the cassettes key on a hash of the request. So
does changing the warehouse seed in a slice an existing scenario queries. Both
have happened. `evals:replay` doubles as the contamination check after a seed
change. See [[Record and Replay Agent Runs]].

Deterministic agent evals (`evals:check`) score agent logic against scripted
model responses and gate `agent_registry.eval_status`. They say nothing about
whether a model was right.

## Infrastructure and docs

Terraform runs formatting, validation, and non-destructive plan. `docs:check`
validates the knowledge graph's **structure** — frontmatter, links, index
coverage. It cannot tell whether a note is still true, which is how six notes
came to contradict the code while the check reported green. Re-read the notes a
change touches, including the ones it did not edit.

Run all tasks through Nx to retain dependency/caching behavior.

Parent: [[Operations MOC]]
