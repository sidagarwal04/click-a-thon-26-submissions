# Unseen incident diagnosis (Day-2)

- **Dataset:** `InMobi/unseen_data` (1.5M events, 2026-07-06 … 2026-07-10)
- **Load mode:** `eda.ad_events` = unseen only (no append). Regenerated dims from unseen CSVs. T−7 baselines read from `default.ad_events` (history left untouched).
- **Pipeline:** `uv run python stack/scripts/upload_unseen.py` → `uv run clickathon materialize --rollup`
- **Catalog:** `eda.rca_incidents` → ids **A**, **B**, **C**

## Summary

Three ClickHouse-native incidents on the sealed Jul 6–10 slice:

1. **A / C — eCPM collapse on video × APAC** (layered price drop; requests up ~5%, fill flat/up).
2. **B — fill_rate collapse on iOS 17.5** (localized; strongest on iOS 17.5 × APAC).

Seasonality / weekend ruled out where applicable (weekday probes; thin seasonal history → gate allows).

---

## Incident A — 2026-07-07 · eCPM · video × APAC

On **2026-07-07** vs T−7 **2026-06-30**, primary factor is **eCPM**, localized to **video × APAC** (shape: layered).

Global WoW: requests +5.6%, fill +1.85 pp, eCPM **−22.2%**, revenue −1.5%.  
Contribution shares: eCPM **52.8%**, requests 33.1%, fill 14.1%.  
Counterfactual: if eCPM stayed at baseline, revenue would be **602.20** vs actual **537.84** (primary explained Δ **−64.36**).

---

## Incident B — 2026-07-08 · fill_rate · iOS 17.5

On **2026-07-08** vs T−7 **2026-07-01**, primary factor is **fill_rate**, localized to **os_version=iOS 17.5** (shape: localized). Window continues into 2026-07-09.

Global WoW: requests +5.4%, fill **−5.32 pp**, eCPM −16.3%, revenue −8.3%.  
iOS 17.5 fill: **0.478 vs 0.786 (−30.80 pp)**; fill_impact ≈ 17,984. Supporting: iOS 17.5 × APAC, region=APAC.  
Counterfactual: if fill stayed at baseline, revenue **550.70** vs actual **502.86** (Δ **−47.85**).

---

## Incident C — 2026-07-10 · eCPM · video × APAC

On **2026-07-10** vs T−7 **2026-07-03**, primary factor is **eCPM**, again **video × APAC** (layered).

Global WoW: requests +5.5%, fill +0.92 pp, eCPM **−32.1%**, revenue −7.1%.  
Shares: eCPM **66.0%**. video × APAC eCPM **2.94 vs 6.99**.  
Counterfactual: if eCPM at baseline → **570.75** vs actual **486.90** (Δ **−83.86**). Ruled out fill/requests as primary.
