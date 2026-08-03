# Domain Docs

How engineering skills consume this repository's domain documentation.

This Nx monorepo uses a multi-context domain layout.

## Before exploring

- Read the root `CONTEXT-MAP.md`.
- Read each linked `CONTEXT.md` relevant to the work.
- Read system-wide decisions under `docs/adr/`.
- Check for context-specific `docs/adr/` directories in the affected area.

If an optional context or ADR directory does not exist, proceed silently. Domain
documentation is created lazily when terminology or a durable architectural
decision is actually resolved.

## Current structure

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                              ← system-wide decisions
└── libs/
    └── domain/
        ├── CONTEXT.md                    ← shared ZentraOS language
        ├── agent-execution/
        │   └── CONTEXT.md
        └── investigation/
            └── CONTEXT.md
```

The context map is authoritative for which contexts exist and how they relate.
Do not infer contexts merely from workspace package boundaries.

## Use the glossary's vocabulary

When output names a domain concept—in an issue title, specification, test,
hypothesis, or implementation—use the canonical term from the relevant
`CONTEXT.md`. Do not drift to synonyms listed under `_Avoid_`.

If a required concept is absent, either reconsider whether it is genuinely a
domain term or resolve it through domain modeling before introducing it.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly.
Do not silently override an accepted decision. Accepted ADRs are superseded by
a new linked ADR rather than rewritten.
