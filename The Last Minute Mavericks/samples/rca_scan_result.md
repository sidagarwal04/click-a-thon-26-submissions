# Sample RCA scan result

Output of `python run_incident.py` on the provided InMobi dataset (`rca` — 9M ad events, Jun 1 – Jul 5 2026).
All 4 planted incidents are found and localized; 6 look-alike segments are demoted with the reason.
Matches the ground truth in `teamkit/docs/DATA.md`.

```

 RCA SCAN — rca   ·   4 real anomalies, 6 ruled out

 REAL ANOMALIES
┌───────────┬─────────────────┬───────────────────────────────────┬───────────┬────────────────────┐
│ Metric    │ Duration        │ Anomaly (segment)                 │ Deviation │ Type               │
├───────────┼─────────────────┼───────────────────────────────────┼───────────┼────────────────────┤
│ ecpm      │ Jun 19 → Jun 22 │ category = finance                │    -34.8% │ LOCALIZED_1D       │
│ requests  │ Jun 21          │ — global (no segment) —           │    -44.2% │ GLOBAL_UNLOCALIZED │
│ fill_rate │ Jun 23 → Jun 25 │ os_version = Android 15           │    -44.8% │ LOCALIZED_1D       │
│ fill_rate │ Jun 28 → Jun 30 │ os_version=iOS 18.1 × region=APAC │    -50.6% │ LOCALIZED_2D       │
└───────────┴─────────────────┴───────────────────────────────────┴───────────┴────────────────────┘

 RULED OUT / FALSE  (checked and cleared)
┌───────────┬──────────────────────────────┬───────────┬───────────────────────────────────────────────────────────┐
│ Metric    │ Segment                      │ Deviation │ Why it's not the cause                                    │
├───────────┼──────────────────────────────┼───────────┼───────────────────────────────────────────────────────────┤
│ ecpm      │ ad_format = interstitial     │    -11.1% │ correlated with category=finance                          │
│ fill_rate │ device_model = Redmi Note 12 │    -10.7% │ correlated with os_version=Android 15                     │
│ fill_rate │ device_model = Galaxy S23    │    -12.3% │ correlated with os_version=Android 15                     │
│ fill_rate │ country = UK                 │    -10.2% │ correlated with os_version=Android 15                     │
│ fill_rate │ os_version = iOS 18.1        │    -12.5% │ dilution — explained by os_version=iOS 18.1 × region=APAC │
│ fill_rate │ country = JP                 │    -11.2% │ subsumed by the 2-D cause                                 │
└───────────┴──────────────────────────────┴───────────┴───────────────────────────────────────────────────────────┘

 Weekend seasonality handled by same-weekday baseline (not flagged).

```
