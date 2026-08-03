# Unseen incident dataset — diagnosis

**Dataset** `InMobi/unseen_data` · 1,500,000 events · 2026-07-06 → 2026-07-10 (5 weekdays) · $2,530.46 revenue
**Full window** `inmobi-hari.ad_events` now holds both batches unified: 10,500,000 events, 2026-06-01 → 2026-07-10
**Database** `inmobi-hari` on ClickHouse Cloud, fully self-contained · **Pipeline** unchanged from the June build

Two incidents in the unseen slice. Both are 48 contiguous hours, both start exactly on a UTC midnight boundary, and they overlap on Jul 9 — which is why Jul 9 is the worst revenue day of the window.

Scored against the full history, the same detector also re-derives every incident from the original June analysis, plus one it had not previously found — **7 incidents total across 40 days of data, zero false positives on any of the 24 clean days.** See [Full-window timeline](#full-window-timeline-2026-06-01--2026-07-10) below.

---

## Incident A — `os_version = iOS 17.5` fill-rate collapse

| | |
|---|---|
| **Window** | 2026-07-08 00:00 → 2026-07-09 23:59 UTC (48 contiguous hours) |
| **Metric** | `fill_rate` |
| **Segment** | `os_version = iOS 17.5` — 19.2% of requests |
| **Baseline → observed** | 0.79243 → 0.47773 (**−39.7%**) |
| **Score** | z = −117.19 (Jul 8), −116.47 (Jul 9) · **P1** |
| **Blast radius** | 115,642 requests · 36,836 fills lost |
| **Revenue impact** | **−$66.00** |

Ad requests from devices on iOS 17.5 stopped being filled at roughly half the normal rate for exactly two days. Every other OS version was untouched.

**The fault is the OS version alone — not the device, not the geography.** Three pieces of evidence:

1. The drop is uniform across all 16 countries: −37.3% (ZA) to −43.0% (DE), all within noise of the −39.8% global figure.
2. It is uniform across all three iPhone models carrying that OS: iPhone 13 −40.1%, iPhone 14 −40.0%, iPhone 15 −40.0%.
3. **The control case is decisive.** Holding hardware fixed at iPhone 14 and varying only the OS:

| OS on iPhone 14 | baseline | observed | change |
|---|---|---|---|
| **iOS 17.5** | 0.7950 | 0.4769 | **−40.0%** |
| iOS 18.1 | 0.7950 | 0.7901 | −0.6% |
| iOS 17.2 | 0.7949 | 0.7936 | −0.2% |
| iOS 16.4 | 0.7906 | 0.7954 | +0.6% |

Onset and recovery are single-hour sharp: 0.7945 at Jul 07 23:00 → 0.4798 at Jul 08 00:00, and 0.4732 at Jul 09 23:00 → 0.7858 at Jul 10 00:00. Consistent with a bidder or SDK-compatibility rule keyed on the OS string being switched on and then off, not with a gradual degradation.

At the total level the same incident reads `fill_rate` 0.79210 → 0.73138 (−7.66%, z = −51.56) on Jul 8 and 0.79218 → 0.73241 (−7.55%, z = −50.31) on Jul 9 — the 19.2% traffic share diluting a −39.7% segment move.

**What is *not* the cause.** The dimension scan also flags `device_model = iPhone 14` (−23.5%), `country = ID` (−23.8%) and `region = APAC` (−12.9%). These are composition bleed-through: they are the buckets that contain the most iOS 17.5 traffic. A 19%-share segment dropping 40% mechanically moves every overlapping bucket by up to 7.7%. Their |z| peaks at 71 against iOS 17.5's 117, and they resolve to flat once iOS 17.5 is held out.

---

## Incident B — `ad_format = video` price collapse, with displacement into `rewarded`

| | |
|---|---|
| **Window** | 2026-07-09 00:00 → 2026-07-10 23:59 UTC (48 contiguous hours, **still open at end of data**) |
| **Metric** | `ecpm` |
| **Segment** | `ad_format = video` — 11.9% of impressions |
| **Baseline → observed** | $6.032 → $4.231 (**−29.9%**) |
| **Score** | z = −59.70 (Jul 9), −59.52 (Jul 10) · **P1** |
| **Paired move** | `ad_format = rewarded` $4.497 → $5.660 (**+25.5%**), z = +50.97 |
| **Revenue impact** | video **−$93.74**, rewarded **+$41.50**, net **−$52.24** |

Video inventory repriced down ~30% while rewarded repriced up ~25%, in the same hour.

**This is a pricing change, not a delivery change.** Impression counts are flat on both formats across the whole window — video 26k–28k/day, rewarded 17k–19k/day — and the mix effect in the rate/mix split is ~0.0002 against a rate effect of −0.209. Only revenue-per-impression moved.

The cut is uniform across every other dimension, which rules out a single advertiser or region pulling budget:

| cut | range of change |
|---|---|
| 16 countries | −29.8% to −30.5% |
| 7 verticals | −29.0% to −30.3% |
| 3 publisher tiers | −29.7% to −30.1% |
| 3 campaign types | −29.5% to −30.1% |

**The two moves are one event, but not a clean swap.** They begin in the same hour (video 6.055 → 4.200 and rewarded 4.501 → 5.842 at Jul 09 00:00). But combined video+rewarded eCPM still falls from $5.39 to $4.81, so this is not a zero-sum relabeling of one format as the other — roughly $52/day of the $94/day video loss is genuinely gone. The signature is consistent with a bid-multiplier or floor-price table where the video and rewarded entries were changed together.

Unlike Incident A, **this one never recovers within the dataset.** It is still active at 2026-07-10 23:00, the last hour of data.

---

## Factor attribution

Exact LMDI decomposition of each day's revenue against the clean Jul 6–7 level. Contributions are additive and close to the observed delta with no residual.

| day | revenue | baseline | delta | requests | fill_rate | render_rate | eCPM | residual |
|---|---|---|---|---|---|---|---|---|
| 2026-07-08 | 502.86 | 536.63 | −33.77 | +1.31 | **−42.39** | −0.31 | +7.62 | 0.0024 |
| 2026-07-09 | 467.45 | 536.63 | −69.18 | −7.99 | **−40.20** | −0.27 | **−20.72** | 0.0001 |
| 2026-07-10 | 486.90 | 536.63 | −49.73 | −21.91 | −0.07 | +0.02 | **−27.77** | 0.0040 |

Jul 8 is Incident A alone. Jul 10 is Incident B alone. Jul 9 carries both, and is the only day where two factors fire together.

---

## Full-window timeline (2026-06-01 → 2026-07-10)

`inmobi-hari.ad_events` now holds both data drops as one unified fact table (10.5M rows), each event interpreted through the dimension snapshot that shipped with its own batch. Re-running the identical detector — no threshold or model changed — across all 40 days recovers all four incidents from the original June analysis and surfaces one new one, alongside the two above.

| day(s) | metric | root cause | baseline → observed | z | revenue impact |
|---|---|---|---|---|---|
| Jun 16–18 | eCPM | `region = EU` × `ad_format = interstitial` | $2.83 → $2.28 (**−19.7%**) | −13.7 to −13.9 | −$20.00 (3 days) |
| Jun 19–22 | eCPM | `category = finance` | $2.48 → $1.61 (**−35.0%**) | −69 to −70 | −$41.80 (4 days) |
| Jun 21 | requests | ingestion gap (whole pipeline) | 224,855 → 126,052 (**−43.9%**) | −10.0 | untyped — a volume gap has no price to net against |
| Jun 23–25 | fill_rate | `os_version = Android 15` | 0.784 → 0.433 (**−44.7%**) | −87 to −88 | −$68.11 (3 days) |
| Jun 28–30 | fill_rate | `os_version = iOS 18.1` × `country ∈ {ID, IN, JP, PH}` | 0.786 → 0.380 (**−51.6%**, interaction) | −22 to −26 (marginal, diluted) | −$20.66 (3 days) |
| Jul 8–9 | fill_rate | `os_version = iOS 17.5` | 0.792 → 0.477 (**−39.7%**) | −116 to −117 | −$66.00 (2 days) |
| Jul 9–10 | eCPM | `ad_format = video` (+ `rewarded` displacement) | $6.03 → $4.22 (**−29.8%**) | −60 | −$93.74 video / −$52.24 net (2 days) |

**Jun 21 needed a fifth detector.** The fill/eCPM detectors score *rates* — fills per request, revenue per impression — which are blind to a uniform drop in the request stream itself: a pipe that's flowing at half rate still has a normal fill rate. `v_request_alerts` closes that gap with a median + MAD check on daily request counts against the same-day-type history. It fires exactly once, on Jun 21, at z = −10.0. A volume-uniformity check (`rca_volume`-style retention ratio) confirms it's a pipeline-wide outage, not a demand shock: every one of the 9 dimensions shows 46.6–50.9% retention, all within noise of each other — nothing is disproportionately hit.

**Jun 16–18 is a genuine finding this rescore surfaced that the original June-only analysis missed.** It looked, at first, like bleed-through from the adjacent Jun 19–22 finance-eCPM incident — but the two don't overlap in time (finance eCPM is flat through Jun 18 and only breaks on Jun 19) or in mechanism (finance advertisers aren't concentrated in `interstitial` — only 18% share, banner is higher). Crossing `ad_format = interstitial` against country shows the real shape: FR/UK/ES/DE (the `region = EU` bucket) drop ~19.7% for exactly three days while every other country is flat at +1%; the ~5% dip visible at the `vertical` level is dilution from EU's share of interstitial volume, not a vertical-specific cause. This is the same rate-vs-mix and concentration-ranking method used throughout — applied here to a genuinely new signal, not a rehearsed one.

**Jun 28–30 needed the two-dimensional cross to see its true size.** The single-dimension marginal scan flags `os_version = iOS 18.1` at only −12% to −13% (z ≈ −22 to −26) — real, but visibly weaker than every other fill incident. Crossing against `rollup_os_country_1h` shows why: the fault is actually iOS 18.1 **and** APAC (ID, IN, JP, PH) together, dropping ~52% there while iOS 18.1 in every other country sits within 1% of baseline. The marginal os_version alert is diluted because most iOS 18.1 traffic is *not* in APAC. This is exactly the concentration-ranking method from `rca_scan`/`rca_seg`: a single-dimension hit that's real but weak is the signature of an interaction, and the fix is to cross the two flagged dimensions rather than trust the marginal number as the segment's true severity.

---

## Ruled out

**The −8% eCPM drop on Jul 6–8 is not an incident.** It is an artifact of the regenerated dimension tables. Measured against a naive June baseline, total eCPM is down 8.35%, 8.25% and 6.95% on the first three days. Measured against the June price book re-weighted to the observed July country mix, the gap is **+0.27%, +0.23%, +0.28%** — nothing. The `unseen_data` geo profiles moved traffic from expensive countries (US 20.1% → 12.4%, ES 12.3% → 4.9%) to cheap ones (ID 7.0% → 17.5%), and a blended average falls even though no price changed. A detector that skipped the mix correction would raise four false P1s and misstate the two real ones by a factor of two.

**Request volume is within trend.** Weekday requests grow at +0.27%/day across the June import. July sits +5.4%, +5.3%, +5.2%, +3.0%, −0.1% above the fitted trend — a ~2σ wobble that decays back to trend, against an in-sample June residual range of −3.5% to +1.9%. It contributes −$21.91 to Jul 10 by LMDI purely because the Jul 6–7 comparison baseline was itself slightly elevated. Watch-level, not an incident.

**`render_rate` and `CTR`: nothing.** Zero segments breach on any day.

**No entity-level fault.** A sweep of all 2,000 `app_id`s and 500 `advertiser_id`s finds no app-specific or advertiser-specific break. The worst app-level hits (app_00000 −7.3%, app_00002 −7.4%) are all ≈−7.7%, the exact arithmetic bleed-through of Incident A.

---

## Trace

Alert volume, and how it collapses:

| day | fill_rate alerts | eCPM alerts | total-scope | root causes |
|---|---|---|---|---|
| 2026-07-06 | 0 | 0 | 0 | — |
| 2026-07-07 | 0 | 0 | 0 | — |
| 2026-07-08 | 26 | 0 | 1 | iOS 17.5 |
| 2026-07-09 | 27 | 59 | 2 | iOS 17.5 + video |
| 2026-07-10 | 0 | 59 | 1 | video |

**Zero alerts on the two clean days.** 171 raw segment alerts across the window reduce to 4 incident rows and 2 root causes.

Over the full 40-day window the same pattern holds at scale: **277 raw alerts** (270 segment + 7 total-scope, across fill/render/eCPM) reduce to **17 incident rows across 6 rate/price root causes**, plus the 1 requests-volume detection, for **7 incidents total — a combined −$310.31 revenue impact — and zero false positives on any of the 24 clean days.**

Reproduce end to end:

```bash
clickhouse client --secure --host <host> --port 9440 --user default --password '<pw>' --multiquery < notes/rca/unseen/u03_baselines.sql
```

```sql
SELECT * FROM `inmobi-hari`.v_incidents_unseen;
SELECT * FROM `inmobi-hari`.alerts_unseen WHERE scope = 'total' ORDER BY day, metric;
SELECT * FROM `inmobi-hari`.rca_scan(test_from='2026-07-08', test_to='2026-07-09',
                                     base_from='2026-07-06', base_to='2026-07-07', metric='fill_rate');
SELECT * FROM `inmobi-hari`.rca_seg(test_from='2026-07-09', test_to='2026-07-10',
                                    base_from='2026-07-06', base_to='2026-07-07',
                                    metric='ecpm', dim='ad_format');
```

Files: `u01_schema.sql` → `u02_pipeline.sql` → `u03_baselines.sql` → `u04_alerts.sql` → `u05_rca_scan.sql`. Method and the relabeling trap are in `README.md`.
