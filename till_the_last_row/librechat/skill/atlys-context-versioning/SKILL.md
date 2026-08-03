---
name: atlys-context-versioning
description: Enforce provable context freshness for the Atlys knowledge bundle — bump context_version in overview.md and append a newest-first, dated changelog entry to the reserved log.md listing added/updated/contradiction files and the source, on every context change. Invoke after writing/updating concept docs and before regenerating the index.
---

# Skill: Context Versioning & Changelog

A silent update is a **stale-context bug**. Every change bumps the version and logs the diff —
this is what makes freshness provable in the Langfuse trace ("no stale snapshot" is
demonstrable).

## Step 1 — Bump `context_version`

In `overview.md` frontmatter, `context_version: N → N+1`.

## Step 2 — Append a `log.md` entry (newest first)

```markdown
## v{N+1} — {ISO-8601 datetime} — {trigger}
- added: /tables/{table}.md, /relationships/{...}.md
- updated: /metrics/conversion-rate.md (denominator clarified)
- contradictions: /contradictions/{slug}.md (dual conversion definition)
- source: Atlys/schemas/{schema_name}.sql + live atlys schema
```

The version + trigger + file list is the freshness proof: a judge (or the Analytics Agent) can
see exactly what changed, when, and why.

## Rules

- **Always** bump `context_version` **and** append a `log.md` entry on every change — never one
  without the other.
- `log.md` and `index.md` are **reserved** files — `log.md` is append-only (newest first);
  `index.md` is regenerated (see `atlys-okf-authoring` Step 7).
- Record the **trigger** and the **source** on every entry so provenance is legible.
- Keep the datetime ISO-8601.
