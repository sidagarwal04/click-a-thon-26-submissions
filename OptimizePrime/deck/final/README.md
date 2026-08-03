# Final submission deck — 12 slides, 2–5 minutes

> **Summary:** `deck.html` is the presentation deck for the SonyLIV foreground-only concurrency
> submission. Twelve slides, CSS scroll-snap navigation, no JavaScript, self-contained. Slide 08 is
> a **live demo cue** — the presenter switches to the ClickStack dashboard there. Timings are
> printed on each slide, bottom-right. Total 2 min at pace, 5 min with a full demo.

## Presenting it

Open `deck.html` in any browser, full-screen it, and drive with **↓ / space / arrow keys**. Slides
snap one at a time. Nothing to install, no network needed.

| | |
|---|---|
| Slides | 12 |
| Core narration | ~2 min |
| With the demo | up to 5 min |
| Flexible slide | **08 — live demo**, budgeted 60–120 s |

## The demo, slide 08

Switch to the ClickStack dashboard when you reach it. The slide carries the running order:

1. **Set the range to `2026-07-31 00:00 → 23:59 UTC`.** This is the single most important step —
   the unseen day holds 99.088% of the data, and outside that window the panels render empty and
   will look broken when they are not.
2. Show the ACCURATE curve, the ramp, the peak at 11:17.
3. Show NAIVE beside it — same data, session-span reading. The gap is backgrounded and paused time.
4. Apply a filter and watch the curve change **shape**, not just scale.
5. Say the `video_resolution` point: that column arrived *with the unseen file*, no migration,
   filterable the same day.
6. Show pipeline health — our own ingestion lag and query latency, in ClickStack.

**Say the `country` caveat before anyone asks.** 11 of 12 filters move the curve; `country` is the
constant `'india'` in all 7,000,000 rows and returns the identity curve. It is on the slide.

## Static copy

Print to PDF from the browser (`⌘P` → Save as PDF). The print stylesheet disables scroll-snap and
breaks one slide per page. The earlier checkpoint deck lives in `deck/checkpoint1/`.

## Where the numbers come from

Every figure is from the pipeline with a `query_id` in `system.query_log` — see
`evidence/submission/results-matrix.txt`. Nothing on these slides is hand-computed. Full detail
behind the deck: `docs/artifacts/2026-08-02-solution-atlas.html`.

## Editing notes

**The problem statement is deliberately not explained.** The judges wrote the brief; narrating it
back costs presenter time and tells them nothing. The deck opens on what we built and what it
measures. The one piece of problem framing that survives is slide 02 — and it survives because it is
*our measurement*, not the brief: heartbeats survive a pause at 0.756/min, which is why gap
detection alone cannot work and why there are two signals rather than one.

**Slide 10 is scale.** Measured at 1×/10×/100× from `evidence/scale.txt`: serving latency is flat
(2.1–17.2 ms at every scale, because hour-clipping makes reads window-bound), while the interval
build is what strains — at 100× it failed at default settings and needed spill plus two threads.
Naming what breaks first, with numbers, is stronger than claiming nothing does.
