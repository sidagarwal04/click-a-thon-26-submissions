# `destination_card_clicked`

**Kind:** funnel, step 1 (top of funnel) · **Grain:** one row per card-tap
**Rows:** 1,000,000 · **Span:** 2026-01-01 → 2026-06-30 · **Distinct users:** 1,000,000 (1:1, see overview)

## What it captures
User taps a destination card (browse, search result, or deeplink). No application exists
yet for most of these — this is pure discovery/intent signal, the widest and noisiest
part of the funnel.

## Data quality
- `application_id` empty **84.6%** of the time (not 100% — see overview contradiction #2).
- `os` NULL only for `android` rows (18.0% of android rows); 0% null for ios/web/Desktop.
- `duplicate_id` populated 3.0%, `is_back_filled=1` 2.0% — standard background noise.
- `gclid` present 22.0% → roughly a fifth of top-of-funnel traffic is paid search.

## Key distributions
| field | breakdown |
|---|---|
| `device_type` | ios 42.1%, android 33.0%, web-user-b2c 18.0%, Desktop 7.0% |
| `flow` | explore 50.0%, search 39.9%, deeplink 10.0% |
| `card_type` | visa_card 80.0%, eta_card 15.0%, arrival_card 5.0% |
| `visa_type` | tourist 86.0%, business 9.0%, transit 3.0%, medical 2.0% |
| `funnel_type` | b2c 86.0%, b2c_afc 10.0%, b2c_black 4.0% |
| `destination` (top) | AE 16.4%, US 9.9%, ID 8.8%, TH 6.3%, VN 5.3% |
| flags | is_guest 35%, is_guest_browse 35%, is_referral 8%, is_enterprise 3% |

## Notes for instrumentation / analytics design
- Highest cardinality, highest volume table — any join against it should filter first
  (time + segment), never scan-then-join.
- `card_type`/`funnel_type`/`flow` look like good low-cardinality segment cuts for a
  materialized "clicks by day x segment" rollup — this table is 4x the volume of
  everything else combined, and most funnel questions start here.
- AE (UAE) dominates the destination mix at every funnel stage checked so far — expect
  it to also dominate revenue/volume asks; worth its own baseline rather than lumping
  into "top 10 destinations."
