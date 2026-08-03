# ZentraOS engineering knowledge vault

Open this `docs/` directory as an Obsidian vault. The vault uses standard
Markdown, frontmatter, wikilinks, backlinks, and graph navigation; it requires
no community plugins and commits no personal `.obsidian` workspace state.

Start at [[00_Index/ZentraOS Knowledge Base]]. Templates live in
[[98_Templates/Templates Guide]], while the governing rules live in
[[01_Overview/Documentation System Specification]] and
[[13_References/Documentation Quality Bar]].

## Source-of-truth hierarchy

1. Executable code, migrations, schemas, and configuration define current
   behavior.
2. `CONTEXT.md` files define canonical domain language.
3. `docs/adr/` records accepted architectural decisions.
4. This vault indexes and explains those sources without replacing them.
5. README files remain concise setup or package entry points.

## Obsidian setup

- Enable the core Backlinks, Graph view, Templates, and Properties features.
- Configure `98_Templates` as the Templates folder.
- Keep wikilinks enabled and allow Obsidian to update links after renames.
- Do not commit `.obsidian/workspace*.json` or machine-specific settings.

## Validation

Run the documentation contract through Nx:

```bash
npm exec -- nx run docs:check
```

The check validates metadata, stable IDs, links, source references, ADR
indexing, and active-note discoverability.
