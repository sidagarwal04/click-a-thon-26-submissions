---
id: overview-documentation-system
title: Documentation System Specification
type: overview
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-30
reviewed: 2026-07-30
confidence: mixed
priority: critical
tags: [documentation, governance, obsidian]
related: ["[[Overview MOC]]", "[[Documentation Quality Bar]]", "[[Templates Guide]]"]
repo_path: docs
code_refs: [package.json, nx.json, .github/workflows/ci.yml, CONTEXT-MAP.md]
---

# Documentation System Specification

## 1. Repository understanding

ZentraOS is a trust-first analytical investigation product. Its current
end-to-end workflow runs one deterministic Cube-governed scenario, persists a
tenant-isolated Investigation in Postgres, pauses at Human Approval, and emits
an immutable metadata-only timeline to ClickHouse.

The Nx monorepo contained 31 software/workspace projects before this vault; the
governed documentation project makes 32. They span React/TypeScript and Python.
Major surfaces are the `zentra-os` Vite application, FastAPI composition root,
domain and application packages, infrastructure adapters, reusable frontend
foundation libraries, local Docker services, Terraform, and GitHub Actions.

## 2. Documentation strategy

- Document intent, boundaries, behavior, failure modes, operational procedures,
  and architectural rationale.
- Do not duplicate source code, schemas, raw configuration, customer data, or
  generated API references.
- Layer knowledge from MOCs to overview, architecture/domain, component/API/data,
  workflow, and operational detail.
- Keep setup commands in READMEs, canonical language in `CONTEXT.md`, local
  implementation comments in code, hard-to-reverse trade-offs in ADRs, and
  cross-system understanding in this vault.
- Mark verified facts, mixed notes, and inference explicitly.

## 3. Vault architecture

| Folder | Purpose and admission rule | Examples |
| --- | --- | --- |
| `00_Index` | One root entry and cross-vault reading paths | ZentraOS Knowledge Base |
| `01_Overview` | Product/repository orientation that applies across contexts | repository overview, boundaries, current status |
| `02_Architecture` | System shape, runtime boundaries, qualities, and constraints | system context, tenancy security |
| `03_Domains` | Behavioral context notes that index canonical `CONTEXT.md` language | Investigation, Identity and Tenancy |
| `04_Components` | Deployable or independently owned project responsibilities | FastAPI service, adapters, frontend |
| `05_APIs` | Consumer-visible HTTP capabilities and privacy/error contracts | Investigation API |
| `06_Data` | Store/model authority, grain, isolation, consistency, and retention | Postgres, ClickHouse, Cube |
| `07_Workflows` | Cross-component sequences with triggers, invariants, and failure semantics | trust loop, outbox delivery |
| `08_Operations` | Environment, configuration, test, and infrastructure reference | local development, readiness |
| `09_Decisions` | Decision MOC and ADR governance; canonical records stay in `adr/` | Decisions MOC |
| `10_Runbooks` | Executable diagnosis/recovery procedures with verification | degraded readiness, migration failure |
| `11_Onboarding` | Outcome-oriented learning paths for engineers | First Day, First Change |
| `12_Glossary` | Navigation to canonical terms; never competing definitions | Glossary MOC |
| `13_References` | Catalogs, standards, source maps, backlog, and explicit unknowns | Nx catalog, quality bar |
| `14_Change` | Durable release, incident, research, and open-question records | future dated records |
| `98_Templates` | Governed creation prompts; placeholders never become active notes | runbook and ADR templates |
| `99_Archive` | Obsolete notes with replacement/history links | deprecated prior designs |
| `adr` | Existing accepted architectural decisions | ADR-0001 through ADR-0007 |
| `agents` | Instructions for engineering agents, not product knowledge | domain and issue-tracker guidance |

## 4. Note taxonomy

| Type | Purpose and typical sections | Filename and links | Lifecycle |
| --- | --- | --- | --- |
| `moc` | Scope, core notes, reading paths, source authority | `Topic MOC.md`; parent/root plus every child | active while area exists |
| `overview` | Orientation, boundaries, current/deferred behavior | `Topic.md`; Overview MOC plus architecture/workflows | review quarterly |
| `architecture` | Purpose, context, structure, invariants, failures, decisions | `Concern.md`; Architecture MOC, ADRs, components | update with architecture |
| `domain` | Capability, canonical language, invariants, relationships, deferred behavior | `Domain Name.md`; Domains/Glossary MOCs and context file | update with context |
| `component` | Responsibility, interfaces, dependencies, config, failures, verification | `Component Name.md`; Components MOC and dependencies | update with component |
| `api` | Consumers, endpoints, contracts, errors/privacy, observability | `Capability API.md`; APIs MOC and workflow/component | update with routes |
| `data-model` | Authority, entities/grain, isolation, consistency, sensitivity, recovery | `Store or Model.md`; Data MOC and adapters/workflows | update with migrations |
| `workflow` | Trigger/result, participants, sequence, invariants, retry/audit | `Outcome Workflow.md`; Workflows MOC and every participant | update with behavior |
| `adr` | Status, context, decision, alternatives, consequences, verification | `NNNN-kebab-case.md`; Decisions MOC and affected architecture | immutable/superseded |
| `runbook` | Use-when, safety/access, diagnosis, recovery, verification, escalation | `Verb Failure.md`; Runbooks MOC and failed component | review after use |
| `incident` | Impact, timeline, detection/response, cause, follow-up | `YYYY-MM-DD Summary.md`; Change MOC and resulting runbooks | close then retain |
| `release` | Visible change, compatibility/migration, verification, limitations | `YYYY-MM-DD Release.md`; Change MOC and changed capabilities | immutable |
| `onboarding` | Outcome, prerequisites, guided path, mental model, completion | milestone title; Onboarding MOC and required reading | review quarterly |
| `glossary` | Canonical-source link, usage, avoided synonyms, language questions | canonical term; Glossary MOC and owning domain | follows context |
| `investigation` | Question, primary evidence, findings, conclusion, durable follow-up | `YYYY-MM-DD Question.md`; Change MOC and evidence | draft to completed |
| `open-question` | Decision needed, facts, unknowns/options, resolution criteria, outcome | `Question - Short Name.md`; Change/References MOC | open to resolved |
| `reference` | Catalog, standard, source map, or configuration index | subject title; References/Operations MOC and consumers | update on source change |

All types use the required metadata below. Every non-MOC note links to a parent
MOC, source artifacts, related concepts, and dependencies where applicable.

## 5. Metadata standard

| Field | Requirement | Rule |
| --- | --- | --- |
| `id` | required | globally unique stable lowercase ID with type prefix |
| `title` | required | canonical human title matching the note |
| `type` | required | one taxonomy value from Section 4 |
| `status` | required | `draft`, `active`, `deprecated`, or `archived` |
| `owner` | required | verified registry value; currently `unassigned` |
| `source` | required | `repository`, `context-map`, `decision`, `governance`, `operations`, `release`, or `research` as appropriate |
| `created`, `updated`, `reviewed` | required | `YYYY-MM-DD` |
| `confidence` | required | `verified`, `mixed`, or `inferred` |
| `tags` | required | small discovery vocabulary; never empty |
| `domain`, `component` | contextual | canonical context or Nx project |
| `priority` | contextual | `critical`, `high`, `normal`, or `low` |
| `implementation` | contextual | `current`, `planned`, or `unknown` |
| `related`, `depends_on` | contextual | wikilinks, not free-text names |
| `repo_path` | contextual | repository-root source area that must exist |
| `code_refs` | contextual | repository-root paths; optional `#symbol` |
| `aliases` | contextual | package names and established search synonyms |

Allowed status values are `draft`, `active`, `deprecated`, and `archived`.
Confidence is `verified`, `mixed`, or `inferred`. Implementation is `current`,
`planned`, or `unknown`. Dates use `YYYY-MM-DD`. Until ownership is recorded in
the repository, owner is `unassigned`.

Example:

```yaml
---
id: workflow-investigation-trust-loop
title: Investigation Trust Loop
type: workflow
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
tags: [investigation, workflow]
repo_path: libs/application/investigation
code_refs:
  - libs/application/investigation/src/zentra_application_investigation/service.py
related: ["[[Investigation Domain]]"]
---
```

An ADR uses `type: adr`, `source: decision`, `id: adr-NNNN`, and links
`[[Decisions MOC]]`. A runbook uses `type: runbook`, declares implementation
state, links the failed component/workflow, and points to executable operational
sources. An inferred open question uses `confidence: inferred` and
`implementation: unknown`; it must never be presented as current behavior.

## 6. Naming and linking conventions

- Human knowledge notes use Title Case; ADRs retain numbered kebab-case.
- Stable IDs are lowercase and use a type prefix.
- Canonical titles use product vocabulary, not implementation nicknames.
- Aliases capture package names and common search terms.
- Wikilinks connect knowledge notes. Markdown links point to repository files.
- `repo_path` names the owning source area; `code_refs` lists concrete sources.
- Symbols may follow a path after `#`, but the path before `#` must exist.
- Avoid line-number links in committed docs because they decay quickly.

## 7. Vault templates

Templates in [[Templates Guide]] cover MOCs, architecture, domains, components,
APIs, data models, workflows, ADRs, runbooks, incidents, onboarding, glossary,
investigations, releases, and open questions. Each prompts for intent,
boundaries, source authority, failure modes, unknowns, relationships, and review
criteria.

## 8. Documentation map for this repository

The root map is [[ZentraOS Knowledge Base]]. The highest-value path follows
[[Investigation Trust Loop]] through [[Investigation Domain]],
[[Cube Semantic Model]], [[Postgres Control Plane]],
[[Audit Outbox Delivery]], [[ClickHouse Audit Ledger]],
[[Trust and Verification]], [[Investigation API]], and
[[Forensic Observatory]].

Architecture, domains, APIs, data, operations, onboarding, and runbooks each
have a dedicated MOC. [[Repository Source Map]] points back to authoritative
files and [[Nx Project Catalog]] records the actual workspace topology.

## 9. Prioritized documentation backlog

The phases in this section describe vault maturity, not product delivery. Product
Phase 2 is defined separately in
[[Phase 2 - Insight Auditor and Replay]].

- Phase 1: root navigation, repository overview, system context, trust loop,
  local development, and first-day onboarding.
- Phase 2: domain, component, API, data, and workflow depth.
- Phase 3: configuration, testing, infrastructure, and recovery runbooks.
- Phase 4: enrich ADR metadata, record unknowns, add source catalog, and repair
  weak links.
- Phase 5: enforce PR maintenance, quarterly review, incident learning, release
  notes, and archival.

Current status is tracked in [[Documentation Backlog]].

## 10. Quality bar

Good documentation is discoverable from a MOC, correct against a source
artifact, explicit about uncertainty, readable without source-code duplication,
owned or visibly unassigned, and inexpensive to refresh. See
[[Documentation Quality Bar]] for measurable acceptance criteria.

## 11. Maintenance workflow

Documentation impact is considered in the same PR as architecture, behavior,
API, schema, operations, or ownership changes. ADRs are superseded rather than
rewritten. Runbooks are reviewed after use. Active notes follow priority-based
review cadence. Stale notes become deprecated before moving to `99_Archive`.
See [[Documentation Maintenance Workflow]].

## 12. Final deliverables

A documentation engineer should create or verify, in order:

1. [[ZentraOS Knowledge Base]] and all MOCs.
2. [[Repository Overview]], [[System Context]], and [[Product Boundaries]].
3. [[Investigation Trust Loop]] and its linked domain/data/API/component notes.
4. [[Local Development]], [[First Day]], and [[First Change]].
5. Operational runbooks and [[Configuration Reference]].
6. ADR metadata and [[Decisions MOC]].
7. [[Nx Project Catalog]], [[Known Unknowns]], and maintenance governance.
8. Automated `docs:check` validation in CI.

Parent: [[Overview MOC]]
