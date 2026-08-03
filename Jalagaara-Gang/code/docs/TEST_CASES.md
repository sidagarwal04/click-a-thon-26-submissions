# Detection bake-off — test cases

Real anomalies found by manually inspecting the actual dataset (not invented, not tuned to
favor either detection approach). Both the statistical baseline and the ML approach should
be run against all 3 cases before deciding which to build the real pipeline on.

Queries used to derive these are reproducible against `hourly_summary` — see
[`backend/data/baseline.py`](../backend/data/baseline.py) for the like-for-like comparison
pattern used throughout.

---

## Case 1 — localized segment anomaly (fill rate)

**What:** fill rate collapses for one specific segment, everything else normal.

- **Metric**: `fill_rate`
- **Window**: Jun 23-25 2026 (3 full days)
- **Baseline**: Jun 9-11 2026 (same weekdays, 2 weeks prior) — median fill_rate ≈ **0.786**
- **Observed**: fill_rate ≈ **0.433** (a ~45% relative drop)
- **Responsible segment**: `os_version = Android 15` — confirmed via drill-down across
  region, country, os_version, device_model, ad_format, category, publisher_tier, vertical,
  campaign_type. Android 15's own drop (0.786 → 0.433) dwarfs every other dimension's top
  segment (next largest was region=EU at 0.786 → 0.730 — a much smaller, likely correlated
  effect, not the root cause).
- **Uniformity check**: the drop is consistent across every sub-slice *within* Android 15
  (region, ad_format, category, app_id all show ~0.40-0.45) — confirms the anomaly sits
  exactly at the `os_version` level, doesn't need to be drilled deeper.
- **Time bounds**: exactly Jun 23 00:00 → Jun 26 00:00. Jun 22 and Jun 26 are both back to
  ~0.785-0.788 — a clean on/off step, not a gradual drift.
- **Expected diagnosis shape**: *"Fill rate dropped ~45% for Android 15 devices, Jun 23-25.
  Other OS versions, regions, and ad formats were checked and stayed normal."*
- **What a method should be scored on**: does it isolate `os_version=Android 15`
  specifically (not just "somewhere in EU" or "somewhere in banner ads" — those are
  correlated but not causal)?

---

## Case 2 — global/systemic anomaly (request volume)

**What:** request volume drops everywhere at once — no single segment stands out.

- **Metric**: `requests`
- **Window**: Jun 21 2026, full day
- **Baseline**: Jun 14 2026 (same weekday — both Sundays, proper like-for-like, not a
  seasonality artifact)
- **Observed**: ~126k requests vs ~223k baseline (~55-56% ratio)
- **Responsible segment**: **none — genuinely global.** Drilled across region, country,
  os_version, device_model, ad_format, category, publisher_tier — every single dimension
  shows almost exactly the same ~0.55 target/baseline ratio. No segment is disproportionately
  affected.
- **Expected diagnosis shape**: *"Request volume dropped ~45% on Jun 21, uniformly across
  every region, device, and app category checked — no single segment explains it; likely a
  system-wide or upstream issue, not a segment-specific one."*
- **What a method should be scored on**: does it correctly **stop drilling and report
  "no localized segment found"** instead of forcing a false pick on whichever dimension
  happens to look marginally worse by noise? This is the opposite failure mode from Case 1 —
  Case 1 punishes under-drilling, Case 2 punishes over-drilling (inventing a culprit that
  isn't really there).

---

## Case 3 — seasonality decoy (must NOT be flagged)

**What:** a completely normal Saturday. The trap: naive flat-average detectors mistake every
weekend for an anomaly because weekends are always lower-volume than weekdays.

- **Metric**: `requests`
- **Windows to compare (same weekday only — Saturdays)**:
  | Date | Requests |
  |---|---|
  | Jun 6 | 214,353 |
  | Jun 13 | 219,420 |
  | Jun 20 | 224,327 |
  | Jun 27 | 228,266 |
- **Observed pattern**: a small, steady upward trend (~2-3% week over week) — this is the
  "slow growth trend" the metrics glossary explicitly mentions, not an anomaly.
- **Expected diagnosis shape**: **no anomaly should fire.** Any of these 4 Saturdays,
  compared against the *other* Saturdays (never against a weekday), should land well inside
  normal variance.
- **What a method should be scored on**: this is a **precision test, not a recall test.**
  A method that flags any of these Saturdays as anomalous has failed the single most
  explicit warning in the entire problem statement (*"a flat global average makes every
  weekend look like an anomaly... at least one planted movement is pure seasonality and
  should be ruled out, not alarmed on"*).

---

## Scoring both methods

For each case, record:
1. **Detected?** (yes/no — Case 3's correct answer is "no")
2. **Localization** — exact segment named, or correctly reported as "no segment" (Case 2)
3. **Numbers cited** — are they real, reproducible, sum/sum-correct per the glossary?
4. **Explainability** — can the method's own reasoning be stated in one sentence a judge
   could verify by rerunning a query?
5. **Time to build** — how many hours did getting this method working actually take?

Whichever approach wins should win on this scoreboard, not on which one felt more
technically impressive to build.
