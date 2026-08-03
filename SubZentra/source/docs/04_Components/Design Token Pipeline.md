---
id: component-design-token-pipeline
title: Design Token Pipeline
type: component
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [component, frontend, design-system, tailwind]
aliases: [design tokens, tailwind setup]
related: ["[[Components MOC]]", "[[Forensic Observatory]]", "[[TypeScript Foundation Library Catalog]]"]
repo_path: libs/foundation/design-system
code_refs:
  - libs/foundation/design-system/src/tokens/tokens.css
  - libs/foundation/design-system/src/tokens/themes/dark.ts
  - libs/foundation/design-system/src/tokens/themes/light.ts
  - apps/zentra-os/src/styles.css
---

# Design Token Pipeline

How a design system class becomes a colour on screen.

## The chain

1. `tokens.css` imports Tailwind and declares the token scales inside `@theme`.
2. A second `@theme inline` block maps the semantic names components are written
   against — `primary`, `foreground`, `card`, `border`, `danger` — onto the
   runtime variables the themes set (`--interactive-primary`, `--text-primary`,
   `--bg-layer-01`, `--border-default`, `--interactive-destructive`).
3. `:root` and `.light` / `[data-theme='light']` supply those runtime variables.
4. `apps/zentra-os/src/styles.css` imports `tokens.css` and declares
   `@source` for the design system directory.

`inline` is load-bearing. A plain `@theme` computes each alias once against
`:root`, so a `.light` subtree would keep dark values; `inline` substitutes at
the point of use.

## Three faults this replaced

Every design system component renders semantic Tailwind utilities, but until
2026-08-01 none of them resolved in the product:

- **No bridge.** `tokens.css` defined `--interactive-primary`; components asked
  for `bg-primary`. The utility was never generated, so components rendered
  unstyled and the app carried ~1000 lines of hand-written SCSS with literal
  hex values instead.
- **A preprocessed entry point.** The stylesheets were `.scss`.
  `@tailwindcss/vite` does not compile Sass output, so `@import 'tailwindcss'`
  was inlined verbatim and Tailwind never ran at all. Both files are now `.css`;
  neither used any Sass syntax.
- **A shadowed scale.** The phi-based spacing scale lived in `@theme` as
  `--spacing-4xl` and friends. Tailwind reads that namespace for sizing, so
  `max-w-4xl` resolved to 5.657rem rather than 56rem and every `max-w-*` in the
  design system silently collapsed. The scale now sits in a plain `:root`
  block: still readable as `var(--spacing-lg)`, no longer a Tailwind scale.

A fourth belongs to the consuming app: global element rules must be written
inside `@layer base`. Unlayered CSS outranks every Tailwind layer, so a bare
`button { font: inherit }` overrides the utility classes on that element.

## Palette

Dark is the primary theme: a green-tinted near-black canvas, signal lime
(`hsl(88 100% 70%)`) as the single interactive accent, violet
(`hsl(263 83% 58%)`) reserved for navigation state and agent surfaces. Light
mode darkens lime to `hsl(88 72% 28%)` so it can carry white text.

`themes/dark.ts` and `themes/light.ts` mirror the same values for the contrast
tests in `src/__tests__/tokens.test.ts`. They are not read at runtime; keep them
in step with `tokens.css` by hand.

Parent: [[Components MOC]]
