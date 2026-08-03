# Compound segments

Two-dimension combinations that broke together while **neither dimension looked abnormal on its own** — invisible to any scan that checks one dimension at a time.

A cell is only reported when it moved at least **2× more than its strongest parent**. An earlier rule required both parents to be flat, which was backwards: a compound large enough to matter drags its own parent, so that rule discarded the largest finding in the dataset and reported a diluted proxy instead.

| Day | Combination | Combined | First dim alone | Second dim alone | Requests |
|---|---|---:|---:|---:|---:|
| 2026-06-28 | `os_version=iOS 18.1` × `country=PH` | -55.4% | -12.1% | -1.9% | 638 |
| 2026-06-29 | `os_version=iOS 18.1` × `country=ID` | -53.7% | -12.7% | -3.5% | 1,324 |
| 2026-06-29 | `os_version=iOS 18.1` × `country=PH` | -52.7% | -12.7% | -1.3% | 756 |
| 2026-06-30 | `os_version=iOS 18.1` × `country=ID` | -52.0% | -13.3% | -3.4% | 1,337 |
| 2026-06-30 | `os_version=iOS 18.1` × `country=IN` | -52.0% | -13.3% | -3.1% | 938 |
| 2026-06-30 | `region=APAC` × `os_version=iOS 18.1` | -51.4% | -4.4% | -13.3% | 7,128 |
| 2026-06-30 | `os_version=iOS 18.1` × `country=JP` | -51.3% | -13.3% | -11.6% | 4,107 |
| 2026-06-30 | `os_version=iOS 18.1` × `country=PH` | -50.5% | -13.3% | -1.0% | 746 |
| 2026-06-28 | `region=APAC` × `os_version=iOS 18.1` | -50.4% | -4.5% | -12.1% | 5,696 |
| 2026-06-28 | `os_version=iOS 18.1` × `country=JP` | -50.3% | -12.1% | -11.5% | 3,245 |
| 2026-06-29 | `region=APAC` × `os_version=iOS 18.1` | -50.0% | -4.1% | -12.7% | 7,075 |
| 2026-06-29 | `os_version=iOS 18.1` × `country=IN` | -49.2% | -12.7% | -2.9% | 934 |
| 2026-06-28 | `os_version=iOS 18.1` × `country=ID` | -48.8% | -12.1% | -3.0% | 1,035 |
| 2026-06-29 | `os_version=iOS 18.1` × `country=JP` | -48.4% | -12.7% | -10.5% | 4,061 |
| 2026-06-28 | `os_version=iOS 18.1` × `country=IN` | -48.0% | -12.1% | -2.7% | 778 |
| 2026-06-28 | `device_model=iPhone 14` × `country=JP` | -37.6% | -5.9% | -11.5% | 3,700 |
| 2026-06-30 | `device_model=iPhone 14` × `country=JP` | -36.6% | -6.3% | -11.6% | 4,675 |
| 2026-06-29 | `device_model=iPhone 14` × `country=JP` | -35.1% | -6.0% | -10.5% | 4,586 |
| 2026-06-28 | `region=APAC` × `device_model=iPhone 14` | -23.2% | -4.5% | -5.9% | 7,943 |
| 2026-06-30 | `region=APAC` × `device_model=iPhone 14` | -21.9% | -4.4% | -6.3% | 9,906 |
| 2026-06-29 | `region=APAC` × `device_model=iPhone 14` | -20.9% | -4.1% | -6.0% | 9,803 |
| 2026-06-28 | `device_model=iPhone 14` × `country=PH` | -18.2% | -5.9% | -1.9% | 804 |
| 2026-06-29 | `device_model=iPhone 13` × `country=ID` | -17.0% | -1.8% | -3.5% | 1,806 |
| 2026-06-29 | `device_model=iPhone 14` × `country=PH` | -16.5% | -6.0% | -1.3% | 955 |
| 2026-06-30 | `device_model=iPhone 13` × `country=ID` | -15.8% | -1.4% | -3.4% | 1,749 |
| 2026-06-30 | `device_model=iPhone 14` × `country=PH` | -15.2% | -6.3% | -1.0% | 976 |
| 2026-06-29 | `device_model=iPhone 15` × `country=ID` | -15.0% | -1.4% | -3.5% | 1,659 |

*Scanned 21 dimension pairs, 1,211,930,496 rows, 51,032 ms. This stage reads raw `ad_events` rather than a rollup, because an unpivoted rollup cannot represent combinations — see ARCHITECTURE.md for the cost and the fix.*