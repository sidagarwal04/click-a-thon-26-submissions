# ClickStack tile verification

Database `sonyliv_prod`, granularity 60s, generated 2026-08-01 23:26:26Z.

## hot-hour — `2026-07-26 10:00:00` .. `2026-07-26 11:00:00`

| Tile | Type | Result | Rows | First row |
|---|---|---|---|---|
| 01 Concurrent now | number | OK | 1 | `0` |
| 01 Peak (ungrouped) | number | OK | 1 | `0` |
| 01 Viewer-hours | number | OK | 1 | `0` |
| 01 Layer lag (s) | number | OK | 1 | `247` |
| 01 Concurrent viewers | line | OK | 0 | `—` |
| 01 Peak vs average (ungrouped) | line | OK | 0 | `—` |
| 01 Top titles | line | OK | 0 | `—` |
| 01 Title leaderboard | table | OK | 0 | `—` |
| 02 Average concurrency | number | OK | 1 | `855.603469` |
| 02 Viewer-hours | number | OK | 1 | `855.6` |
| 02 Intervals started | number | OK | 1 | `16173` |
| 02 By platform | line | OK | 407 | `2026-07-26 10:00:00ANDROID_TAB1` |
| 02 By content type | line | OK | 140 | `2026-07-26 10:00:00vod48.04` |
| 02 Viewer-hours by category | pie | OK | 12 | `cdbgg128.71` |
| 02 Titles | table | OK | 25 | `wekek kedlivecdbgg119.7225532.8` |
| 02 Peak (ungrouped) | number | OK | 1 | `2305` |
| 02 Layer lag (s) | number | OK | 1 | `149` |
| 02 Peak minute | table | OK | 1 | `2026-07-26 10:55:0023052283.98` |
| 02 Peak by grouping | table | OK | 60 | `totalall23052026-07-26 10:55:00855.660` |
| 03 Ingest lag p50/p95/p99 (s) | line | OK | 0 | `—` |
| 03 Rows/s by producer | line | OK | 0 | `—` |
| 03 Read volume by query | table | OK | 30 | `full log  selected range predates it470813130237996833-- =` |
| 03 Recent queries | table | OK | 200 | `full log  selected range predates it2026-08-01 23:26:29253` |
| 03 Rollup duration (ms) | line | OK | 0 | `—` |
| 03 Sessions dirtied/min | line | OK | 0 | `—` |
| 03 Layer freshness | table | OK | 3 | `intervals2026-08-01 23:30:59.957-269131225478sonyliv-activ` |
| 03 Dedup collapse | table | OK | 1 | `46908164667861229550.48940` |
| 03 Storage | table | OK | 11 | `events_raw4.69 million75.91 MiB13.4102` |
| 03 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:26:2963708071 hour, 2 min` |
| 04 By platform | stacked_bar | OK | 407 | `2026-07-26 10:00:00ANDROID_TAB1` |
| 04 Platform totals | table | OK | 10 | `ANDROID_PHONE552.4764.579979` |
| 04 By content type | stacked_bar | OK | 140 | `2026-07-26 10:00:00vod48.04` |
| 04 Content type totals | table | OK | 3 | `vod700.1381.8312800` |
| 04 By app version | stacked_bar | OK | 1648 | `2026-07-26 10:00:006.34.834.12` |
| 04 App version totals | table | OK | 30 | `6.34.8444.2151.927895` |
| 04 By category | stacked_bar | OK | 610 | `2026-07-26 10:00:00dhddd1` |
| 04 Category totals | table | OK | 30 | `cdbgg128.7115.042700` |
| 04 By title (top 10) | stacked_bar | OK | 521 | `2026-07-26 10:00:00dijoj jeh1` |
| 04 Title totals | table | OK | 30 | `wekek kedlivecdbgg119.7213.992553` |
| 05 Peak (ungrouped) | number | OK | 1 | `2305` |
| 05 Average (ungrouped) | number | OK | 1 | `855.603469` |
| 05 Viewer-hours (ungrouped) | number | OK | 1 | `855.6` |
| 05 Rows read | number | OK | 1 | `60` |
| 05 Peak by dimension value | table | OK | 50 | `countryindia23052026-07-26 10:55:00855.603469855.6` |
| 05 Peak per minute | line | OK | 118972 | `2026-07-26 10:00:00total: all50` |
| 05 Peak per hour | line | OK | 9308 | `2026-07-26 10:00:00content: zigog gaj1` |
| 05 Per day | table | OK | 9308 | `2026-07-26countryindia23052026-07-26 10:55:0035.6501855.60` |
| 05 Query evidence | table | OK | 20 | `full log  selected range predates it9bc5671e-e2f4-47fb-872` |
| 05 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:26:29631 hour, 2 minutes ` |
| 06 Worst retention — location | number | OK | 1 | `0.974403` |
| 06 Worst retention — platform | number | OK | 1 | `0.898311` |
| 06 Worst retention — content type | number | OK | 1 | `0.864345` |
| 06 Worst retention — category | number | OK | 1 | `0.776935` |
| 06 Detector lag (s) | number | OK | 1 | `157` |
| 06 Slices breaching | number | OK | 1 | `0` |
| 06 Slices watched | number | OK | 1 | `1` |
| 06 Settled through | table | OK | 1 | `2026-08-01 23:24:00.000158174586` |
| 06 Retention by location (alert below 0.70) | line | OK | 60 | `2026-07-26 10:00:00india1` |
| 06 Observed vs baseline by location | line | OK | 120 | `2026-07-26 10:00:00india observed48.042383` |
| 06 Breaching slices, any dimension | table | OK | 0 | `—` |
| 06 Retention by platform | line | OK | 155 | `2026-07-26 10:00:00ANDROID_PHONE1` |
| 06 Retention by content type | line | OK | 97 | `2026-07-26 10:00:00vod1` |
| 06 Retention by category | line | OK | 200 | `2026-07-26 10:39:00cdbgg1` |

63 passed, 0 failed.

## hot-day — `2026-07-26 00:00:00` .. `2026-07-27 00:00:00`

| Tile | Type | Result | Rows | First row |
|---|---|---|---|---|
| 01 Concurrent now | number | OK | 1 | `0` |
| 01 Peak (ungrouped) | number | OK | 1 | `0` |
| 01 Viewer-hours | number | OK | 1 | `0` |
| 01 Layer lag (s) | number | OK | 1 | `260` |
| 01 Concurrent viewers | line | OK | 0 | `—` |
| 01 Peak vs average (ungrouped) | line | OK | 0 | `—` |
| 01 Top titles | line | OK | 0 | `—` |
| 01 Title leaderboard | table | OK | 0 | `—` |
| 02 Average concurrency | number | OK | 1 | `147.290321` |
| 02 Viewer-hours | number | OK | 1 | `1671.75` |
| 02 Intervals started | number | OK | 1 | `30706` |
| 02 By platform | line | OK | 1668 | `2026-07-26 00:10:00ANDROID_PHONE0.44` |
| 02 By content type | line | OK | 988 | `2026-07-26 00:10:00vod0.44` |
| 02 Viewer-hours by category | pie | OK | 12 | `cdbgg184.24` |
| 02 Titles | table | OK | 25 | `wekek kedlivecdbgg170.1346042.2` |
| 02 Peak (ungrouped) | number | OK | 1 | `2305` |
| 02 Layer lag (s) | number | OK | 1 | `162` |
| 02 Peak minute | table | OK | 1 | `2026-07-26 10:55:0023052283.98` |
| 02 Peak by grouping | table | OK | 60 | `totalall23052026-07-26 10:55:001671.75637` |
| 03 Ingest lag p50/p95/p99 (s) | line | OK | 0 | `—` |
| 03 Rows/s by producer | line | OK | 0 | `—` |
| 03 Read volume by query | table | OK | 30 | `full log  selected range predates it470813130237996833-- =` |
| 03 Recent queries | table | OK | 200 | `full log  selected range predates it2026-08-01 23:26:29253` |
| 03 Rollup duration (ms) | line | OK | 0 | `—` |
| 03 Sessions dirtied/min | line | OK | 0 | `—` |
| 03 Layer freshness | table | OK | 3 | `intervals2026-08-01 23:30:59.957-256131225478sonyliv-activ` |
| 03 Dedup collapse | table | OK | 1 | `46929764670017229590.48920` |
| 03 Storage | table | OK | 11 | `events_raw4.69 million75.95 MiB13.4112` |
| 03 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:26:2963708071 hour, 3 min` |
| 04 By platform | stacked_bar | OK | 1668 | `2026-07-26 00:10:00ANDROID_PHONE0.44` |
| 04 Platform totals | table | OK | 10 | `ANDROID_PHONE1097.9465.6818991` |
| 04 By content type | stacked_bar | OK | 988 | `2026-07-26 00:10:00vod0.44` |
| 04 Content type totals | table | OK | 3 | `vod1412.4984.4924097` |
| 04 By app version | stacked_bar | OK | 5097 | `2026-07-26 00:10:006.28.140.44` |
| 04 App version totals | table | OK | 30 | `6.34.8867.1851.8714907` |
| 04 By category | stacked_bar | OK | 2707 | `2026-07-26 00:10:00other0.44` |
| 04 Category totals | table | OK | 30 | `cdbgg184.2411.024824` |
| 04 By title (top 10) | stacked_bar | OK | 1945 | `2026-07-26 00:10:00other0.44` |
| 04 Title totals | table | OK | 30 | `wekek kedlivecdbgg170.1310.184604` |
| 05 Peak (ungrouped) | number | OK | 1 | `2305` |
| 05 Average (ungrouped) | number | OK | 1 | `147.290321` |
| 05 Viewer-hours (ungrouped) | number | OK | 1 | `1671.75` |
| 05 Rows read | number | OK | 1 | `637` |
| 05 Peak by dimension value | table | OK | 50 | `totalall23052026-07-26 10:55:00147.2903211671.75` |
| 05 Peak per minute | line | OK | 255642 | `2026-07-26 00:10:00total: all1` |
| 05 Peak per hour | line | OK | 19646 | `2026-07-26 00:00:00app version: 6.34.42` |
| 05 Per day | table | OK | 12357 | `2026-07-26countryindia23052026-07-26 10:55:0069.656157.464` |
| 05 Query evidence | table | OK | 20 | `full log  selected range predates it9bc5671e-e2f4-47fb-872` |
| 05 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:26:29631 hour, 3 minutes ` |
| 06 Worst retention — location | number | OK | 1 | `0` |
| 06 Worst retention — platform | number | OK | 1 | `0` |
| 06 Worst retention — content type | number | OK | 1 | `0` |
| 06 Worst retention — category | number | OK | 1 | `0` |
| 06 Detector lag (s) | number | OK | 1 | `172` |
| 06 Slices breaching | number | OK | 1 | `29` |
| 06 Slices watched | number | OK | 1 | `1` |
| 06 Settled through | table | OK | 1 | `2026-08-01 23:24:00.000173174586` |
| 06 Retention by location (alert below 0.70) | line | OK | 1440 | `2026-07-26 00:00:00india1` |
| 06 Observed vs baseline by location | line | OK | 2880 | `2026-07-26 00:00:00india observed0` |
| 06 Breaching slices, any dimension | table | OK | 29 | `categorycdbgg202026-07-26 11:01:002026-07-26 11:35:000100-` |
| 06 Retention by platform | line | OK | 455 | `2026-07-26 08:37:00ANDROID_PHONE1` |
| 06 Retention by content type | line | OK | 269 | `2026-07-26 08:37:00vod1` |
| 06 Retention by category | line | OK | 752 | `2026-07-26 10:39:00cdbgg1` |

63 passed, 0 failed.

## gap-no-data — `2026-07-16 00:00:00` .. `2026-07-18 00:00:00`

| Tile | Type | Result | Rows | First row |
|---|---|---|---|---|
| 01 Concurrent now | number | OK | 1 | `0` |
| 01 Peak (ungrouped) | number | OK | 1 | `0` |
| 01 Viewer-hours | number | OK | 1 | `0` |
| 01 Layer lag (s) | number | OK | 1 | `275` |
| 01 Concurrent viewers | line | OK | 0 | `—` |
| 01 Peak vs average (ungrouped) | line | OK | 0 | `—` |
| 01 Top titles | line | OK | 0 | `—` |
| 01 Title leaderboard | table | OK | 0 | `—` |
| 02 Average concurrency | number | OK | 1 | `0` |
| 02 Viewer-hours | number | OK | 1 | `0` |
| 02 Intervals started | number | OK | 1 | `0` |
| 02 By platform | line | OK | 0 | `—` |
| 02 By content type | line | OK | 0 | `—` |
| 02 Viewer-hours by category | pie | OK | 0 | `—` |
| 02 Titles | table | OK | 0 | `—` |
| 02 Peak (ungrouped) | number | OK | 1 | `0` |
| 02 Layer lag (s) | number | OK | 1 | `177` |
| 02 Peak minute | table | OK | 0 | `—` |
| 02 Peak by grouping | table | OK | 0 | `—` |
| 03 Ingest lag p50/p95/p99 (s) | line | OK | 0 | `—` |
| 03 Rows/s by producer | line | OK | 0 | `—` |
| 03 Read volume by query | table | OK | 30 | `full log  selected range predates it470813130237996833-- =` |
| 03 Recent queries | table | OK | 200 | `full log  selected range predates it2026-08-01 23:26:56600` |
| 03 Rollup duration (ms) | line | OK | 0 | `—` |
| 03 Sessions dirtied/min | line | OK | 0 | `—` |
| 03 Layer freshness | table | OK | 3 | `intervals2026-08-01 23:30:59.957-240131225478sonyliv-activ` |
| 03 Dedup collapse | table | OK | 1 | `46956224672662229600.4890` |
| 03 Storage | table | OK | 11 | `events_raw4.70 million75.98 MiB13.4102` |
| 03 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:26:5663712771 hour, 3 min` |
| 04 By platform | stacked_bar | OK | 0 | `—` |
| 04 Platform totals | table | OK | 0 | `—` |
| 04 By content type | stacked_bar | OK | 0 | `—` |
| 04 Content type totals | table | OK | 0 | `—` |
| 04 By app version | stacked_bar | OK | 0 | `—` |
| 04 App version totals | table | OK | 0 | `—` |
| 04 By category | stacked_bar | OK | 0 | `—` |
| 04 Category totals | table | OK | 0 | `—` |
| 04 By title (top 10) | stacked_bar | OK | 0 | `—` |
| 04 Title totals | table | OK | 0 | `—` |
| 05 Peak (ungrouped) | number | OK | 1 | `0` |
| 05 Average (ungrouped) | number | OK | 1 | `0` |
| 05 Viewer-hours (ungrouped) | number | OK | 1 | `0` |
| 05 Rows read | number | OK | 1 | `0` |
| 05 Peak by dimension value | table | OK | 0 | `—` |
| 05 Peak per minute | line | OK | 0 | `—` |
| 05 Peak per hour | line | OK | 0 | `—` |
| 05 Per day | table | OK | 0 | `—` |
| 05 Query evidence | table | OK | 20 | `full log  selected range predates it9bc5671e-e2f4-47fb-872` |
| 05 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:26:59631 hour, 3 minutes ` |
| 06 Worst retention — location | number | OK | 1 | `1` |
| 06 Worst retention — platform | number | OK | 1 | `1` |
| 06 Worst retention — content type | number | OK | 1 | `1` |
| 06 Worst retention — category | number | OK | 1 | `1` |
| 06 Detector lag (s) | number | OK | 1 | `183` |
| 06 Slices breaching | number | OK | 1 | `0` |
| 06 Slices watched | number | OK | 1 | `0` |
| 06 Settled through | table | OK | 1 | `2026-08-01 23:24:00.000184174586` |
| 06 Retention by location (alert below 0.70) | line | OK | 0 | `—` |
| 06 Observed vs baseline by location | line | OK | 0 | `—` |
| 06 Breaching slices, any dimension | table | OK | 0 | `—` |
| 06 Retention by platform | line | OK | 0 | `—` |
| 06 Retention by content type | line | OK | 0 | `—` |
| 06 Retention by category | line | OK | 0 | `—` |

63 passed, 0 failed.

## full-extract — `2026-07-14 00:00:00` .. `2026-07-27 00:00:00`

| Tile | Type | Result | Rows | First row |
|---|---|---|---|---|
| 01 Concurrent now | number | OK | 1 | `0` |
| 01 Peak (ungrouped) | number | OK | 1 | `0` |
| 01 Viewer-hours | number | OK | 1 | `0` |
| 01 Layer lag (s) | number | OK | 1 | `286` |
| 01 Concurrent viewers | line | OK | 0 | `—` |
| 01 Peak vs average (ungrouped) | line | OK | 0 | `—` |
| 01 Top titles | line | OK | 0 | `—` |
| 01 Title leaderboard | table | OK | 0 | `—` |
| 02 Average concurrency | number | OK | 1 | `6.27036` |
| 02 Viewer-hours | number | OK | 1 | `1779.53` |
| 02 Intervals started | number | OK | 1 | `31948` |
| 02 By platform | line | OK | 5073 | `2026-07-14 15:43:00IPHONE0.01` |
| 02 By content type | line | OK | 4187 | `2026-07-14 15:43:00vod0.01` |
| 02 Viewer-hours by category | pie | OK | 12 | `cdbgg185.53` |
| 02 Titles | table | OK | 25 | `wekek kedlivecdbgg170.1346042.2` |
| 02 Peak (ungrouped) | number | OK | 1 | `2305` |
| 02 Layer lag (s) | number | OK | 1 | `188` |
| 02 Peak minute | table | OK | 1 | `2026-07-26 10:55:0023052283.98` |
| 02 Peak by grouping | table | OK | 60 | `totalall23052026-07-26 10:55:001779.533662` |
| 03 Ingest lag p50/p95/p99 (s) | line | OK | 0 | `—` |
| 03 Rows/s by producer | line | OK | 0 | `—` |
| 03 Read volume by query | table | OK | 30 | `full log  selected range predates it470813130237996833-- =` |
| 03 Recent queries | table | OK | 200 | `full log  selected range predates it2026-08-01 23:26:59161` |
| 03 Rollup duration (ms) | line | OK | 0 | `—` |
| 03 Sessions dirtied/min | line | OK | 0 | `—` |
| 03 Layer freshness | table | OK | 3 | `intervals2026-08-01 23:30:59.957-229131225478sonyliv-activ` |
| 03 Dedup collapse | table | OK | 1 | `46974844674522229620.48880` |
| 03 Storage | table | OK | 11 | `events_raw4.70 million76.01 MiB13.492` |
| 03 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:26:5963717151 hour, 3 min` |
| 04 By platform | stacked_bar | OK | 5073 | `2026-07-14 15:43:00IPHONE0.01` |
| 04 Platform totals | table | OK | 10 | `ANDROID_PHONE1198.9267.3720134` |
| 04 By content type | stacked_bar | OK | 4187 | `2026-07-14 15:43:00vod0.01` |
| 04 Content type totals | table | OK | 3 | `vod1517.3685.2725304` |
| 04 By app version | stacked_bar | OK | 10065 | `2026-07-14 15:43:008.9.50.01` |
| 04 App version totals | table | OK | 30 | `6.34.8928.4752.1815573` |
| 04 By category | stacked_bar | OK | 6833 | `2026-07-14 15:43:00other0.01` |
| 04 Category totals | table | OK | 30 | `cdbgg185.5310.434831` |
| 04 By title (top 10) | stacked_bar | OK | 5295 | `2026-07-14 15:43:00other0.01` |
| 04 Title totals | table | OK | 30 | `wekek kedlivecdbgg170.139.564604` |
| 05 Peak (ungrouped) | number | OK | 1 | `2305` |
| 05 Average (ungrouped) | number | OK | 1 | `6.27036` |
| 05 Viewer-hours (ungrouped) | number | OK | 1 | `1779.53` |
| 05 Rows read | number | OK | 1 | `3662` |
| 05 Peak by dimension value | table | OK | 50 | `countryindia23052026-07-26 10:55:006.270361779.53` |
| 05 Peak per minute | line | OK | 308913 | `2026-07-14 15:43:00total: all1` |
| 05 Peak per hour | line | OK | 22484 | `2026-07-14 15:00:00all dimensions: IPHONE  india  vod  bhb` |
| 05 Per day | table | OK | 13548 | `2026-07-14platform + contentIPHONE  jipep dih12026-07-14 1` |
| 05 Query evidence | table | OK | 20 | `full log  selected range predates it9bc5671e-e2f4-47fb-872` |
| 05 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:26:59631 hour, 3 minutes ` |
| 06 Worst retention — location | number | OK | 1 | `0` |
| 06 Worst retention — platform | number | OK | 1 | `0` |
| 06 Worst retention — content type | number | OK | 1 | `0` |
| 06 Worst retention — category | number | OK | 1 | `0` |
| 06 Detector lag (s) | number | OK | 1 | `199` |
| 06 Slices breaching | number | OK | 1 | `29` |
| 06 Slices watched | number | OK | 1 | `1` |
| 06 Settled through | table | OK | 1 | `2026-08-01 23:24:00.000200174586` |
| 06 Retention by location (alert below 0.70) | line | OK | 18720 | `2026-07-14 00:00:00india1` |
| 06 Observed vs baseline by location | line | OK | 37440 | `2026-07-14 00:00:00india observed0` |
| 06 Breaching slices, any dimension | table | OK | 29 | `categorycdbgg202026-07-26 11:01:002026-07-26 11:35:000100-` |
| 06 Retention by platform | line | OK | 455 | `2026-07-26 08:37:00ANDROID_PHONE1` |
| 06 Retention by content type | line | OK | 269 | `2026-07-26 08:37:00vod1` |
| 06 Retention by category | line | OK | 752 | `2026-07-26 10:39:00cdbgg1` |

63 passed, 0 failed.

## live-30m — `2026-08-01 22:56:26` .. `2026-08-01 23:26:26`

| Tile | Type | Result | Rows | First row |
|---|---|---|---|---|
| 01 Concurrent now | number | OK | 1 | `16012` |
| 01 Peak (ungrouped) | number | OK | 1 | `20517` |
| 01 Viewer-hours | number | OK | 1 | `1967.3` |
| 01 Layer lag (s) | number | OK | 1 | `304` |
| 01 Concurrent viewers | line | OK | 27 | `2026-08-01 22:56:00273.68` |
| 01 Peak vs average (ungrouped) | line | OK | 27 | `2026-08-01 22:56:00557272.68` |
| 01 Top titles | line | OK | 212 | `2026-08-01 22:56:00sulal lac2` |
| 01 Title leaderboard | table | OK | 25 | `zawew kebvoddbchh30472194246.39` |
| 02 Average concurrency | number | OK | 1 | `5290.749409` |
| 02 Viewer-hours | number | OK | 1 | `2380.84` |
| 02 Intervals started | number | OK | 1 | `57969` |
| 02 By platform | line | OK | 280 | `2026-08-01 22:57:00JIO_ANDROID_TV38.24` |
| 02 By content type | line | OK | 58 | `2026-08-01 22:57:00vod631.87` |
| 02 Viewer-hours by category | pie | OK | 12 | `dhddd464.73` |
| 02 Titles | table | OK | 25 | `tifif fehvoddhddd463.3396942.9` |
| 02 Peak (ungrouped) | number | OK | 1 | `20517` |
| 02 Layer lag (s) | number | OK | 1 | `206` |
| 02 Peak minute | table | OK | 1 | `2026-08-01 23:17:002051718637.74` |
| 02 Peak by grouping | table | OK | 60 | `totalall205172026-08-01 23:17:002380.8427` |
| 03 Ingest lag p50/p95/p99 (s) | line | OK | 31 | `2026-08-01 22:56:0056.06869.11118.233` |
| 03 Rows/s by producer | line | OK | 67 | `2026-08-01 22:56:00generator31.3` |
| 03 Read volume by query | table | OK | 30 | `selected range5475469029478965798SELECT toStartOfInterval(` |
| 03 Recent queries | table | OK | 200 | `selected range2026-08-01 23:26:254820.00121.4INSERT INTO s` |
| 03 Rollup duration (ms) | line | OK | 76 | `2026-08-01 22:56:00live379` |
| 03 Sessions dirtied/min | line | OK | 31 | `2026-08-01 22:56:00628` |
| 03 Layer freshness | table | OK | 3 | `intervals2026-08-01 23:30:59.957-211131225478sonyliv-activ` |
| 03 Dedup collapse | table | OK | 1 | `47006064677641229650.48860` |
| 03 Storage | table | OK | 11 | `events_raw4.70 million76.04 MiB13.492` |
| 03 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:27:2764721891 hour, 3 min` |
| 04 By platform | stacked_bar | OK | 280 | `2026-08-01 22:57:00JIO_ANDROID_TV38.24` |
| 04 Platform totals | table | OK | 12 | `ANDROID_PHONE1549.765.0937729` |
| 04 By content type | stacked_bar | OK | 58 | `2026-08-01 22:57:00vod631.87` |
| 04 Content type totals | table | OK | 3 | `vod2375.6699.7857871` |
| 04 By app version | stacked_bar | OK | 226 | `2026-08-01 22:57:006.34.8421.33` |
| 04 App version totals | table | OK | 10 | `6.34.81428.2759.9934462` |
| 04 By category | stacked_bar | OK | 297 | `2026-08-01 22:57:00bgfff18.1` |
| 04 Category totals | table | OK | 30 | `dhddd464.7319.529730` |
| 04 By title (top 10) | stacked_bar | OK | 288 | `2026-08-01 22:57:00zurur feg3.02` |
| 04 Title totals | table | OK | 30 | `tifif fehvoddhddd463.3319.469694` |
| 05 Peak (ungrouped) | number | OK | 1 | `20517` |
| 05 Average (ungrouped) | number | OK | 1 | `5290.749409` |
| 05 Viewer-hours (ungrouped) | number | OK | 1 | `2380.84` |
| 05 Rows read | number | OK | 1 | `27` |
| 05 Peak by dimension value | table | OK | 50 | `totalall205172026-08-01 23:17:005290.7494092380.84` |
| 05 Peak per minute | line | OK | 41188 | `2026-08-01 22:57:00total: all757` |
| 05 Peak per hour | line | OK | 5345 | `2026-08-01 22:00:00all dimensions: ANDROID_PHONE  india  v` |
| 05 Per day | table | OK | 4046 | `2026-08-01totalall205172026-08-01 23:17:0099.20165290.7492` |
| 05 Query evidence | table | OK | 20 | `selected range61239cc5-a102-4616-aa52-ed795c9a715621718756` |
| 05 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:27:30641 hour, 3 minutes ` |
| 06 Worst retention — location | number | OK | 1 | `0.735177` |
| 06 Worst retention — platform | number | OK | 1 | `0.682117` |
| 06 Worst retention — content type | number | OK | 1 | `0.73072` |
| 06 Worst retention — category | number | OK | 1 | `0.023856` |
| 06 Detector lag (s) | number | OK | 1 | `214` |
| 06 Slices breaching | number | OK | 1 | `2` |
| 06 Slices watched | number | OK | 1 | `1` |
| 06 Settled through | table | OK | 1 | `2026-08-01 23:24:00.000214174586` |
| 06 Retention by location (alert below 0.70) | line | OK | 28 | `2026-08-01 22:56:00india0.960577` |
| 06 Observed vs baseline by location | line | OK | 56 | `2026-08-01 22:56:00india observed538.119267` |
| 06 Breaching slices, any dimension | table | OK | 2 | `categorydbchh72026-08-01 23:10:002026-08-01 23:16:000.0239` |
| 06 Retention by platform | line | OK | 112 | `2026-08-01 22:56:00IPHONE0.785553` |
| 06 Retention by content type | line | OK | 28 | `2026-08-01 22:56:00vod0.95894` |
| 06 Retention by category | line | OK | 20 | `2026-08-01 23:05:00dbchh1` |

63 passed, 0 failed.

## live-6h — `2026-08-01 17:26:26` .. `2026-08-01 23:26:26`

| Tile | Type | Result | Rows | First row |
|---|---|---|---|---|
| 01 Concurrent now | number | OK | 1 | `16012` |
| 01 Peak (ungrouped) | number | OK | 1 | `20517` |
| 01 Viewer-hours | number | OK | 1 | `4572.71` |
| 01 Layer lag (s) | number | OK | 1 | `317` |
| 01 Concurrent viewers | line | OK | 215 | `2026-08-01 19:48:00157.62` |
| 01 Peak vs average (ungrouped) | line | OK | 215 | `2026-08-01 19:48:00328157.62` |
| 01 Top titles | line | OK | 1298 | `2026-08-01 19:52:00tifif feh5.66` |
| 01 Title leaderboard | table | OK | 25 | `zawew kebvoddbchh30472194275.71` |
| 02 Average concurrency | number | OK | 1 | `1384.68551` |
| 02 Viewer-hours | number | OK | 1 | `4984.87` |
| 02 Intervals started | number | OK | 1 | `85576` |
| 02 By platform | line | OK | 1820 | `2026-08-01 19:48:00SONY_ANDROID_TV8.7` |
| 02 By content type | line | OK | 312 | `2026-08-01 19:48:00vod151.25` |
| 02 Viewer-hours by category | pie | OK | 12 | `cdbgg1347.37` |
| 02 Titles | table | OK | 25 | `nivev jadvodcdbgg1307.99105597.4` |
| 02 Peak (ungrouped) | number | OK | 1 | `20517` |
| 02 Layer lag (s) | number | OK | 1 | `219` |
| 02 Peak minute | table | OK | 1 | `2026-08-01 23:17:002051718637.74` |
| 02 Peak by grouping | table | OK | 60 | `countryindia205172026-08-01 23:17:004984.87216` |
| 03 Ingest lag p50/p95/p99 (s) | line | OK | 219 | `2026-08-01 19:48:002.6723.09117.861` |
| 03 Rows/s by producer | line | OK | 316 | `2026-08-01 19:48:00generator16.1` |
| 03 Read volume by query | table | OK | 30 | `selected range470813130237996833-- =======================` |
| 03 Recent queries | table | OK | 200 | `selected range2026-08-01 23:26:2553212027726.17411385642.1` |
| 03 Rollup duration (ms) | line | OK | 531 | `2026-08-01 19:45:00live177` |
| 03 Sessions dirtied/min | line | OK | 219 | `2026-08-01 19:48:00358` |
| 03 Layer freshness | table | OK | 3 | `intervals2026-08-01 23:30:59.957-198131225478sonyliv-activ` |
| 03 Dedup collapse | table | OK | 1 | `47027784679810229680.48840` |
| 03 Storage | table | OK | 11 | `events_raw4.70 million76.07 MiB13.482` |
| 03 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:27:3064727141 hour, 4 min` |
| 04 By platform | stacked_bar | OK | 1820 | `2026-08-01 19:48:00SONY_ANDROID_TV8.7` |
| 04 Platform totals | table | OK | 13 | `ANDROID_PHONE3709.1674.4157404` |
| 04 By content type | stacked_bar | OK | 312 | `2026-08-01 19:48:00vod151.25` |
| 04 Content type totals | table | OK | 3 | `vod4969.0399.6885280` |
| 04 By app version | stacked_bar | OK | 1462 | `2026-08-01 19:48:006.34.894.24` |
| 04 App version totals | table | OK | 11 | `6.34.83507.970.3752501` |
| 04 By category | stacked_bar | OK | 1891 | `2026-08-01 19:48:00bgbbb1.05` |
| 04 Category totals | table | OK | 30 | `cdbgg1347.3727.0311235` |
| 04 By title (top 10) | stacked_bar | OK | 1800 | `2026-08-01 19:48:00other157.62` |
| 04 Title totals | table | OK | 30 | `nivev jadvodcdbgg1307.9926.2410559` |
| 05 Peak (ungrouped) | number | OK | 1 | `20517` |
| 05 Average (ungrouped) | number | OK | 1 | `1384.68551` |
| 05 Viewer-hours (ungrouped) | number | OK | 1 | `4984.87` |
| 05 Rows read | number | OK | 1 | `216` |
| 05 Peak by dimension value | table | OK | 50 | `totalall205172026-08-01 23:17:001384.685514984.87` |
| 05 Peak per minute | line | OK | 171940 | `2026-08-01 19:48:00total: all328` |
| 05 Peak per hour | line | OK | 12081 | `2026-08-01 19:00:00all dimensions: ANDROID_PHONE  india  v` |
| 05 Per day | table | OK | 8149 | `2026-08-01totalall205172026-08-01 23:17:00207.70281384.686` |
| 05 Query evidence | table | OK | 20 | `selected range9bc5671e-e2f4-47fb-872e-44c6fe5cc68221718756` |
| 05 Query log coverage | table | OK | 1 | `2026-08-01 22:23:462026-08-01 23:27:30641 hour, 4 minutes ` |
| 06 Worst retention — location | number | OK | 1 | `0.211258` |
| 06 Worst retention — platform | number | OK | 1 | `0` |
| 06 Worst retention — content type | number | OK | 1 | `0.208036` |
| 06 Worst retention — category | number | OK | 1 | `0` |
| 06 Detector lag (s) | number | OK | 1 | `229` |
| 06 Slices breaching | number | OK | 1 | `13` |
| 06 Slices watched | number | OK | 1 | `1` |
| 06 Settled through | table | OK | 1 | `2026-08-01 23:24:00.000230174586` |
| 06 Retention by location (alert below 0.70) | line | OK | 358 | `2026-08-01 17:26:00india1` |
| 06 Observed vs baseline by location | line | OK | 716 | `2026-08-01 17:26:00india observed0` |
| 06 Breaching slices, any dimension | table | OK | 13 | `platformJIO_ANDROID_TV62026-08-01 21:25:002026-08-01 21:30` |
| 06 Retention by platform | line | OK | 707 | `2026-08-01 19:56:00ANDROID_PHONE1` |
| 06 Retention by content type | line | OK | 208 | `2026-08-01 19:56:00vod1` |
| 06 Retention by category | line | OK | 471 | `2026-08-01 20:00:00chbgg1` |

63 passed, 0 failed.

---

**Total: 378 passed, 0 failed.**
