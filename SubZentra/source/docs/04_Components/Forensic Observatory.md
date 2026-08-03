---
id: component-forensic-observatory
title: Forensic Observatory
type: component
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: critical
tags: [component, frontend, react]
aliases: [zentra-os, frontend]
related: ["[[Components MOC]]", "[[Chat Surface]]", "[[User Workflows]]", "[[Investigation API]]", "[[Connector API]]", "[[Design Token Pipeline]]"]
depends_on: ["[[FastAPI Service]]", "[[TypeScript Foundation Library Catalog]]", "[[Design Token Pipeline]]"]
repo_path: apps/zentra-os
code_refs:
  - apps/zentra-os/src/app/app.tsx
  - apps/zentra-os/src/app/shell/app-shell.tsx
  - apps/zentra-os/src/app/pages
  - apps/zentra-os/src/app/pages/chat
  - apps/zentra-os/src/app/pages/connections
  - apps/zentra-os/src/app/pages/datasets
  - apps/zentra-os/src/app/providers.tsx
  - apps/zentra-os/src/styles.css
---

# Forensic Observatory

The React/Vite application is the authenticated product UI. It uses Clerk,
foundation authentication/authorization, the internal design system, React
Query, React Router, and Motion.

It presents itself as **Oddessy**. The Nx project, package and module names stay
`zentra`; the displayed name is decided in one place,
`src/app/constants/product.ts`.

## Shell

`AppShell` composes the design system `SideNav` with the routed page and draws
nothing above it. The rail carries the wordmark, the workspace lockup (tenant,
role, and whether dependencies answered), the destinations, and the account
control. A header bar was built across every route first and removed: repeated
chrome earns its space only if it does something, and its tabs pointed at
sections that do not exist yet.

The rail collapses to a column of 44px tiles. Collapsed, each label is only
hidden visually — never `display: none` — so the link keeps its accessible
name, and a tooltip carries the label for sighted users. The state that drives
it reaches the items twice over: as a `data-collapsed` attribute the CSS reads
through the root's `group`, and as React context the item reads to decide
whether to wrap itself in a tooltip.

Destinations are listed in `shell/nav-items.ts`. Investigations is the launcher
at `/`; Connections and Datasets are built; Chat is a working surface over a
fixture that says so; Dashboard and Settings still answer with an explicit
placeholder rather than a dead link or a mock that looks finished.

The launcher renders whatever `GET /v1/scenarios` returns — currently the
eight-order EU refund spike and the three-hundred-order NA channel growth — so
the question text lives in the API rather than being compiled into the bundle.
Each card carries neutral descriptors of its data and never a predicted outcome:
the demo shows what the system decides, not what was promised in advance.

The Investigation workspace composes the evidence spine, Finding, metric
comparisons, typed validation, audit-delivery state, and Human Approval
inspector. The timeline names the model that served each step and the rungs that
failed before it, so a degraded provider chain is visible rather than implied.

Metric rows caption their before and after with the periods the metric itself
reports. `MetricComparison` carries `previous_label` and `current_label`, filled
by the agent that chose the granularity, because nothing downstream can recover
it. They once read "June X → July Y", hardcoded from the only scenario that
existed, and captioned an October–November finding with the wrong months. Both
labels are optional: where the agent named no period — an older recording, or a
comparison that is not over time — the row shows values alone rather than a
guess.

Motion reveals already-persisted causality. Reduced-motion preferences disable
transform/layout motion while keeping content present in the accessibility tree.
Status changes use live regions and the approval heading receives focus.

The app explicitly handles missing Clerk configuration, signed-out, missing
organization, unbound membership, degraded dependencies, read-only approval,
completed, and rejected states.

## Chat

`pages/chat` is a working surface over a fixture. Threads, answers and the
canned reply all come from `mock-chat-data.ts`, which is the only file that has
to be deleted when the conversation endpoints exist — every component reads
`types/chat.ts`, written as the contract the API will be held to rather than as
a description of the mock.

Assistant turns are markdown, parsed by `components/markdown.tsx`
(`react-markdown` with GFM). There is no raw-HTML plugin and no
`dangerouslySetInnerHTML`: model output is untrusted input, and the one thing it
must never be able to do is inject markup. The design system carries no
typography plugin, so element styles are supplied per node from the same tokens
as the rest of the product.

The page says on screen that it is a fixture. A chat that answers convincingly
and knows nothing is the one thing a governed product cannot ship by accident.

## Connections

`pages/connections` is the first surface wired to [[Connector API]]. Three
routes: `/connections` lists registered sources with their health,
`/connections/new` is the connector picker, `/connections/new/:connectorId`
configures one.

Registering, listing, re-testing and deleting a source work end to end; the
Data Source repository behind them landed with this page. Harvest and catalog
persistence followed, and Datasets is what reads them.

**One connector connects.** `SourceCredentialsRequest` is host, port, database,
username, password and `secure` — a ClickHouse-shaped credential — and the API
carries no notion of which *kind* of source it is talking to. So ClickHouse has
a real form and the other eleven entries in `constants.ts` are marked
`available: false` and route to `placeholder-config.tsx`, which has no fields at
all. A disabled form would imply the credential shape is settled and only a
click is missing; a form that posts nowhere still collects credentials.

**Save is the test.** `ConnectorService.register_source` opens the connection
before it persists anything and refuses to store a source it could not reach, so
there is no separate "Test connection" button on the create form — one button
reads `Test and save connection`, and a rejection means nothing was stored.
`POST /sources/{id}/test-connection` needs a `data_source_id`, so it can only
re-check something already registered; that is the `Re-test` action on each row
of the list.

A failed connection comes back as a coarse code — `unreachable`,
`authentication_failed`, `database_not_found` — deliberately carrying no text
from the source itself, since a warehouse's own error messages contain
hostnames and topology. `CONNECTION_FAILURE_HELP` turns each code into the field
to go and look at.

`connector-logos.tsx` holds inline vendor marks. `foundation-icons` wraps lucide,
which ships no brand logos, and a picker where twelve sources share one database
glyph has to be read rather than recognised.

## Datasets

`pages/datasets` reads the catalog a harvest produced, one section per connected
source. It is built on Connections rather than beside it: a dataset here is
always a table in a source someone registered, so with none registered the page
says so and links to the connector rather than rendering an empty shell.

Three states per source, kept distinct because each needs something different
offered — a catalog to browse, a harvest to watch, or nothing yet and a button
to start one. `GET /sources/{id}/catalog` answers **404 until a harvest has
completed**, which the page treats as an answer rather than an error; React
Query is told not to retry it, since "not harvested yet" will not become true by
asking again.

Harvest progress is polled, because the work is scheduled *after* the 202 and
cannot be awaited. The progress bar is deliberately indeterminate: the total is
unknown until listing finishes, and a percentage of an unknown total is a
fiction — so counts are shown instead.

Clicking a table opens a modal listing every column with its position, declared
type, family and nullability. Statistics carry the sample size they came from,
and a field that was never profiled says *not profiled* rather than showing
`0%` — the latter would claim the column was measured and had no nulls, which is
a different statement from never having looked.

## Styling

Pages are written in design system components and Tailwind utilities resolved
through [[Design Token Pipeline]]. The 1000-line `app.module.scss` of literal
hex values it replaced existed because Tailwind had never actually compiled in
this app. `draft-finding-panel.module.scss` is the one CSS module left and is
still to migrate.

## Phase 2 gap

The current Finding shows opaque `artifact://` values. Phase 2 requires each
substantive claim to expose authorized, resolvable Evidence Citations and to
render explicit missing, denied, and Tombstone states. The phase is not complete
until an uncoached design-partner reviewer can explain both an automatically
published and a gated Investigation from Replay.

Parent: [[Components MOC]]
