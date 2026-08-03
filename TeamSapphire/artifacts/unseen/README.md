# The unseen incident — 2026-07-06 → 2026-07-10

`ad_events.parquet`, 1,500,000 events, five days, loaded and analysed cold.

**The primary output is [`FULL/`](FULL/)** — one command over the whole released
window, which is what the problem statement asks for. `A/` and `B/` are the same
pipeline pointed at the two sub-windows, once the full run showed the window
contained more than one thing. They are supporting analysis, not a second attempt.

Every number below is reproducible from the queries in each folder's `queries.md`,
and each folder carries the exported Langfuse trace that produced it.

---

## What is actually in the data

Two distinct anomalies, on two different dates, with two different mechanisms.

### A — 2026-07-06: a geographic traffic mix shift

Request **share** moved sharply and then held:

| | APAC | EU | LATAM | MEA | NAM |
|---|---:|---:|---:|---:|---:|
| Jul 4–5 | 28.4% | 24.6% | 6.8% | 10.3% | 29.9% |
| Jul 6 → | **37.5%** | **16.3%** | **14.5%** | **6.1%** | **25.5%** |

APAC and LATAM — the two lowest-priced regions (eCPM 1.59 and 1.37) — gained ~17
points of share, while EU and NAM (2.95 and 3.63) lost ~13.

**No region's own eCPM changed:**

| eCPM by region | APAC | EU | LATAM | MEA | NAM |
|---|---:|---:|---:|---:|---:|
| Jul 5 | 1.592 | 2.958 | 1.349 | 1.144 | 3.651 |
| Jul 6 | 1.594 | 2.950 | 1.375 | 1.150 | 3.627 |

Global eCPM still fell ~8%, because the *weights* moved rather than the prices — a
mix effect, not a pricing event. Ad-format share was unchanged across the same
boundary, which is what confirms the shift is geographic rather than inventory-wide.

### B — 2026-07-09: a genuine within-format price change

| eCPM by ad format | banner | interstitial | native | rewarded | video |
|---|---:|---:|---:|---:|---:|
| Jul 6–8 | 0.801 | 2.50 | 1.81 | 4.48 | 5.98 |
| Jul 9–10 | 0.811 | 2.53 | 1.82 | **5.72** | **4.23** |

Video **−30%**, rewarded **+26%**, everything else flat. Shares did not move, so
this one is a real price change, not dilution.

---

## What our system reported

| Run | Verdict | Assessment |
|---|---|---|
| [`FULL/`](FULL/) | one 119h event · `ecpm` in `ad_format=video` | **Partly right.** Correct metric and a real segment, but it merged A and B into one event and applied B's segment to A's window |
| [`A/`](A/) | `requests` in `campaign_type=CPC` **+139.5%** vs +8.6% globally | **Right window and factor.** It also named `region=APAC` — 5th of seven responsible dimensions — but the headline picked CPC |
| [`B/`](B/) | `ecpm` in `ad_format=video` **−35.0%** vs −12.0% globally | **Correct.** Segment, magnitude and direction all match the data |

### Two failures, both worth stating plainly

**1. Consolidation merged two incidents into one.** A begins Jul 6 and B begins
Jul 9 with no quiet gap between them, so the event clustering — which merges
flagged hours separated by less than six hours — treated 119 contiguous hours as a
single event. The full run therefore reports one incident where there are two. The
clustering is tuned to avoid shattering one incident into many; on back-to-back
incidents it errs the other way.

**2. Attribution cannot see a mix shift.** Our localizer asks *"did this segment's
metric move more than its own size explains?"* In anomaly A the answer is **no for
every segment** — APAC's eCPM did not move, EU's did not move. Only their *shares*
moved. So the system reached for segments whose metric did move (CPC, news,
iOS 17.5, iPhone 14), all of which are correlates of the incoming APAC/LATAM
traffic rather than causes of the eCPM decline.

Catching this properly needs a share-of-volume decomposition alongside the metric
decomposition — splitting a ratio change into "the parts moved" versus "the weights
moved". That is a standard technique and we did not build it.

**What did work:** the like-for-like baseline held across a dataset boundary; the
revenue identity closed to ~1e-17 on every run; the ruled-out ledger correctly
cleared publisher_tier, category, campaign_type and vertical as uniform on window
B; the shape analysis correctly separated a gradual onset (A) from a step (B); and
every narrated number was verified against computed evidence, with all three runs
exiting 0.

---

## A load-time trap worth recording

The spec regenerates the dimension tables: **the same IDs carry different
attributes.** `gd_00000` is `NAM / Galaxy A54 / Android 12` in the main dataset and
`APAC / iPhone 14 / iOS 17.5` in this one.

Our first load rebuilt the entire rollup against the new dimensions. That destroyed
the main dataset's segment structure, because relabelling June's events with July's
attribute assignment averages every June segment toward the global mean — regional
eCPM spread collapsed from 2.50 to 0.67. The detector then reported a confident
*"APAC eCPM −40.8%"* that was **entirely an artifact of the relabelling**, not a
property of the data.

The fix, and what the committed rollup now contains: **each period is joined to its
own dimension tables** — events before 2026-07-06 to the original tables, events
from 2026-07-06 to the regenerated ones. Verified two ways: the boundary is now
continuous (Jul 5 and Jul 6 agree to three decimals on every region), and all nine
dimensions sum to the raw total.

A second trap in the same step: on ClickHouse Cloud, `SYSTEM RELOAD DICTIONARY`
reloads **only the node it is issued against**. It reported success, verified
correct on that connection, and later queries hit a replica still serving the old
values — silently producing a rollup built from stale dimensions. The rebuild uses
direct table joins rather than `dictGet` for exactly this reason.
