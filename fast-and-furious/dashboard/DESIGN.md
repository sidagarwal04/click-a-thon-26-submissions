# Design system — sonyliv-mock dashboard

Recorded from the built surface, not from intentions. Every value below is in
`app/globals.css` or a component; if the two disagree, the code is right and this
file is stale.

**Not to be confused with [`docs/DESIGN.md`](../docs/DESIGN.md)**, which is the
ClickHouse solution architecture. This file is the visual system only.

## Where it comes from

Measured off `sonyliv.com` on 2026-08-02 with a headless browser, reading computed
styles rather than recalling the brand:

| | measured | how |
|---|---|---|
| Ground | `#000000` | 6.2M px² of painted area, dominant by a wide margin |
| Surface | `#222222` | 950k px² |
| Text | `#FFFFFF`, `#AAAAAA`, `#A5A5A5` | by element count |
| Accent | `#FFA800` | logo tick, active-nav border, Subscribe control |
| Type | Inter 400/500/600 | `Inter-Regular` / `-Medium` / `-Semibold` in computed `font-family` |
| Radii | `4px` (39 uses), `10px` (30 uses) | a strict two-step system |

The site also embeds SF Pro Display/Text and Roboto as fallbacks. Inter is what
actually renders, so Inter is what this app self-hosts.

## The one rule

**One signal colour.** SonyLIV's whole home page carries a single non-neutral —
`#FFA800`. Everything else is black, white and two greys. This app keeps that,
which means hierarchy is carried by **form**, not by inventing hues:

- fill vs outline vs text (`Button`'s three variants)
- solid vs dashed (the two lines in `DualCurveChart`)
- weight and size

`--color-live` is deliberately the *same value* as `--color-accent`. The token
exists so component code reads by meaning. **Do not fork it into a teal or a
green.** Where two live quantities must be distinguished — fleet vs pipeline on the
concurrency chart — the second is white and dashed, which is SonyLIV's own
gold-over-white hierarchy rather than a colour we made up.

Red (`#FF5A5F`) is the one addition, and it is an addition: an operator's tool has
to be able to say "this is wrong" and a brand surface never needs to.

## Tokens

```
ground   #000000      sunken  #0a0a0a      panel  #141414      raised  #222222
line     #2e2e2e      line-soft #1c1c1c
ink      #ffffff      ink-2   #aaaaaa      ink-3  #8a8a8a
accent   #ffa800      accent-dim #7a5200   accent-wash #2a1c00
bad      #ff5a5f      bad-wash #2a1011
radius-sm/DEFAULT 4px          radius-lg 10px
```

Contrast on `#000`: accent 10.9:1, ink-2 9.0:1, ink-3 6.0:1. `ink-3` is derived,
not measured — SonyLIV needs two text steps, a dashboard needs three, and the third
still has to pass 4.5:1 as body text.

## Type

Inter, self-hosted by `next/font` (latin, 400/500/600). Mono is the system stack
and carries only measurements, timestamps and ids — never used as a costume for
"technical".

`.eyebrow` (10px/600/0.1em, uppercase) is set in Inter, not mono: SonyLIV sets its
chrome in the text face, and at 10px mono's wider figures cost more room than they
earn.

## Conventions worth keeping

- **No coloured left rules.** Panels are flat fields separated by a hairline; state
  lands on the title, which is the element that names it. The 2px accent
  `border-l` this replaced made eight distinct panels read as eight identical cards.
- **`min-w-0` on every grid/flex item that contains a table.** `Panel` and `main`
  both carry it. Without it a grid item's default `min-width: auto` refuses to
  shrink below content — measured at a 537px column inside 350px, which put the
  whole page into horizontal scroll on a 390px viewport.
- **The nav scrolls, it does not wrap.** Five items plus a two-line lockup do not
  fit at 390px.
- **The lockup uses both parties' real marks**, not lettering set in Inter:
  SonyLIV's own header PNG (`public/sonyliv-mark.png`, from their CDN) over
  ClickHouse's own SVG (`components/BrandMarks.tsx`, verbatim from clickhouse.com,
  `fill="currentColor"` so the lockup tints it). Two brands in one lockup is
  exactly where an approximation shows.
  Stacked with the `×` between them: side by side, two wordmarks read as a
  hyphenated product name. The ClickHouse mark sits at `ink-2`, a step below the
  liv mark's own gold — a lockup where both parties shout has no hierarchy, and
  this is the SonyLIV problem statement. The `×` is the only gold in the header.
  The ClickHouse mark is 16px tall, not 13px: at 13px its cap height was ~7px,
  present but not readable.

## Deliberately not done

- No light theme. Dark is the brand's own ground and the operator's real scene
  (beside a terminal, watching a live curve), not a category default.
- No charting library. Two series and a hover readout do not justify the bytes in a
  static export.
- No icon set. Nothing here needed one; if it does, draw SVGs in one stroke weight
  rather than reaching for emoji.
