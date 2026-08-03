# Every query this investigation ran

**36 queries · 537,518,081 rows read · 19,465 ms of ClickHouse time.**

Each is the exact SQL sent to ClickHouse, with the rows it read and the
time it took, in execution order. Parameters appear as `{name:Type}` —
they are bound by the client, never string-formatted, so these are
runnable as-is once the window is substituted.

Every number in every diagnosis comes from one of these. Nothing in the
prose was computed anywhere else.

| # | Stage | Rows read | Time |
|---:|---|---:|---:|
| 1 | `detect:revenue` | 1,920 | 41.8 ms |
| 2 | `detect:requests` | 1,920 | 33.5 ms |
| 3 | `detect:fill_rate` | 1,920 | 33.5 ms |
| 4 | `detect:ecpm` | 1,920 | 34.5 ms |
| 5 | `detect:ctr` | 1,920 | 38.2 ms |
| 6 | `detect_segments:revenue` | 122,880 | 84.0 ms |
| 7 | `detect_segments:requests` | 122,880 | 62.5 ms |
| 8 | `detect_segments:fill_rate` | 122,880 | 76.8 ms |
| 9 | `detect_segments:ecpm` | 122,880 | 65.9 ms |
| 10 | `detect_segments:ctr` | 122,880 | 64.2 ms |
| 11 | `baseline:data_range` | 1 | 31.2 ms |
| 12 | `decompose:window_vs_baseline` | 4,800 | 54.9 ms |
| 13 | `localize:ecpm` | 307,200 | 55.2 ms |
| 14 | `characterize:ecpm:ad_format=video` | 15,872 | 40.8 ms |
| 15 | `characterize:baseline:ad_format=video` | 15,872 | 35.3 ms |
| 16 | `scan_intersect:regionxdevice_model` | 25,550,016 | 935.6 ms |
| 17 | `scan_intersect:regionxos_version` | 25,550,016 | 899.2 ms |
| 18 | `scan_intersect:regionxcategory` | 25,550,016 | 1018.5 ms |
| 19 | `scan_intersect:regionxpublisher_tier` | 25,550,016 | 1000.2 ms |
| 20 | `scan_intersect:regionxad_format` | 25,550,016 | 752.7 ms |
| 21 | `scan_intersect:regionxcountry` | 25,550,016 | 879.5 ms |
| 22 | `scan_intersect:device_modelxos_version` | 25,550,016 | 905.0 ms |
| 23 | `scan_intersect:device_modelxcategory` | 25,550,016 | 1002.4 ms |
| 24 | `scan_intersect:device_modelxpublisher_tier` | 25,550,016 | 980.8 ms |
| 25 | `scan_intersect:device_modelxad_format` | 25,550,016 | 752.5 ms |
| 26 | `scan_intersect:device_modelxcountry` | 25,550,016 | 867.4 ms |
| 27 | `scan_intersect:os_versionxcategory` | 25,550,016 | 1000.8 ms |
| 28 | `scan_intersect:os_versionxpublisher_tier` | 25,550,016 | 997.4 ms |
| 29 | `scan_intersect:os_versionxad_format` | 25,550,016 | 707.8 ms |
| 30 | `scan_intersect:os_versionxcountry` | 25,550,016 | 850.2 ms |
| 31 | `scan_intersect:categoryxpublisher_tier` | 25,550,016 | 954.1 ms |
| 32 | `scan_intersect:categoryxad_format` | 25,550,016 | 746.0 ms |
| 33 | `scan_intersect:categoryxcountry` | 25,550,016 | 1036.4 ms |
| 34 | `scan_intersect:publisher_tierxad_format` | 25,550,016 | 760.7 ms |
| 35 | `scan_intersect:publisher_tierxcountry` | 25,550,016 | 971.9 ms |
| 36 | `scan_intersect:ad_formatxcountry` | 25,550,016 | 694.0 ms |

---

## `baseline:data_range` — 1 call(s)

1 rows · 31.2 ms

```sql
SELECT min(hour) AS first_hour FROM inmobi.events_hourly
```

## `characterize:baseline:ad_format=video` — 1 call(s)

15,872 rows · 35.3 ms

```sql
SELECT requests AS requests, if(requests > 0, fills / requests, 0) AS fill_rate, if(fills > 0, impressions / fills, 0) AS render_rate, (if(impressions > 0, revenue / impressions, 0)) * 1000 AS ecpm FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} - toIntervalWeek(1) AND hour <= {end:DateTime} - toIntervalWeek(1) AND dim_name = {dim_name:String} AND dim_value = {dim_value:String}
```

## `characterize:ecpm:ad_format=video` — 1 call(s)

15,872 rows · 40.8 ms

```sql
SELECT hour, (if(impressions > 0, revenue / impressions, 0)) * 1000 AS metric_value, requests AS requests, if(requests > 0, fills / requests, 0) AS fill_rate, if(fills > 0, impressions / fills, 0) AS render_rate, (if(impressions > 0, revenue / impressions, 0)) * 1000 AS ecpm FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} - toIntervalHour({ctx:UInt16}) AND hour <= {end:DateTime} + toIntervalHour({ctx:UInt16}) AND dim_name = {dim_name:String} AND dim_value = {dim_value:String} ORDER BY hour
```

## `decompose:window_vs_baseline` — 1 call(s)

4,800 rows · 54.9 ms

```sql
SELECT 0 AS weeks_back, sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS impressions, sum(clicks) AS clicks, sum(revenue) AS revenue FROM inmobi.events_hourly WHERE hour >= {start:DateTime} AND hour <= {end:DateTime} UNION ALL SELECT 1 AS weeks_back, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM inmobi.events_hourly WHERE hour >= {start:DateTime} - toIntervalWeek(1) AND hour <= {end:DateTime} - toIntervalWeek(1) UNION ALL SELECT 2 AS weeks_back, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM inmobi.events_hourly WHERE hour >= {start:DateTime} - toIntervalWeek(2) AND hour <= {end:DateTime} - toIntervalWeek(2) UNION ALL SELECT 3 AS weeks_back, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM inmobi.events_hourly WHERE hour >= {start:DateTime} - toIntervalWeek(3) AND hour <= {end:DateTime} - toIntervalWeek(3) UNION ALL SELECT 4 AS weeks_back, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM inmobi.events_hourly WHERE hour >= {start:DateTime} - toIntervalWeek(4) AND hour <= {end:DateTime} - toIntervalWeek(4) ORDER BY weeks_back
```

## `detect:ctr` — 1 call(s)

1,920 rows · 38.2 ms

```sql
WITH target AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, if(impressions > 0, clicks / impressions, 0) AS metric_value, impressions AS denom FROM inmobi.events_hourly WHERE hour >= {start:DateTime} AND hour < {end:DateTime} ), hist AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, if(impressions > 0, clicks / impressions, 0) AS metric_value FROM inmobi.events_hourly WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.metric_value, t.denom ORDER BY t.hour
```

## `detect:ecpm` — 1 call(s)

1,920 rows · 34.5 ms

```sql
WITH target AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, if(impressions > 0, revenue / impressions * 1000, 0) AS metric_value, 0 AS denom FROM inmobi.events_hourly WHERE hour >= {start:DateTime} AND hour < {end:DateTime} ), hist AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, if(impressions > 0, revenue / impressions * 1000, 0) AS metric_value FROM inmobi.events_hourly WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.metric_value, t.denom ORDER BY t.hour
```

## `detect:fill_rate` — 1 call(s)

1,920 rows · 33.5 ms

```sql
WITH target AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, if(requests > 0, fills / requests, 0) AS metric_value, requests AS denom FROM inmobi.events_hourly WHERE hour >= {start:DateTime} AND hour < {end:DateTime} ), hist AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, if(requests > 0, fills / requests, 0) AS metric_value FROM inmobi.events_hourly WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.metric_value, t.denom ORDER BY t.hour
```

## `detect:requests` — 1 call(s)

1,920 rows · 33.5 ms

```sql
WITH target AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, requests AS metric_value, 0 AS denom FROM inmobi.events_hourly WHERE hour >= {start:DateTime} AND hour < {end:DateTime} ), hist AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests AS metric_value FROM inmobi.events_hourly WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.metric_value, t.denom ORDER BY t.hour
```

## `detect:revenue` — 1 call(s)

1,920 rows · 41.8 ms

```sql
WITH target AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, revenue AS metric_value, 0 AS denom FROM inmobi.events_hourly WHERE hour >= {start:DateTime} AND hour < {end:DateTime} ), hist AS ( SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, revenue AS metric_value FROM inmobi.events_hourly WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.metric_value, t.denom ORDER BY t.hour
```

## `detect_segments:ctr` — 1 call(s)

122,880 rows · 64.2 ms

```sql
WITH target AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, if(impressions > 0, clicks / impressions, 0) AS metric_value, impressions AS denom FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} AND hour < {end:DateTime} AND requests >= {min_volume:UInt32} ), hist AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, if(impressions > 0, clicks / impressions, 0) AS metric_value FROM inmobi.events_hourly_by_dim WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.dim_name AS dim_name, t.dim_value AS dim_value, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dim_name = h.dim_name AND t.dim_value = h.dim_value AND t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.dim_name, t.dim_value, t.metric_value, t.denom ORDER BY t.hour
```

## `detect_segments:ecpm` — 1 call(s)

122,880 rows · 65.9 ms

```sql
WITH target AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, if(impressions > 0, revenue / impressions * 1000, 0) AS metric_value, 0 AS denom FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} AND hour < {end:DateTime} AND requests >= {min_volume:UInt32} ), hist AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, if(impressions > 0, revenue / impressions * 1000, 0) AS metric_value FROM inmobi.events_hourly_by_dim WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.dim_name AS dim_name, t.dim_value AS dim_value, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dim_name = h.dim_name AND t.dim_value = h.dim_value AND t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.dim_name, t.dim_value, t.metric_value, t.denom ORDER BY t.hour
```

## `detect_segments:fill_rate` — 1 call(s)

122,880 rows · 76.8 ms

```sql
WITH target AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, if(requests > 0, fills / requests, 0) AS metric_value, requests AS denom FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} AND hour < {end:DateTime} AND requests >= {min_volume:UInt32} ), hist AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, if(requests > 0, fills / requests, 0) AS metric_value FROM inmobi.events_hourly_by_dim WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.dim_name AS dim_name, t.dim_value AS dim_value, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dim_name = h.dim_name AND t.dim_value = h.dim_value AND t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.dim_name, t.dim_value, t.metric_value, t.denom ORDER BY t.hour
```

## `detect_segments:requests` — 1 call(s)

122,880 rows · 62.5 ms

```sql
WITH target AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, requests AS metric_value, 0 AS denom FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} AND hour < {end:DateTime} AND requests >= {min_volume:UInt32} ), hist AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests AS metric_value FROM inmobi.events_hourly_by_dim WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.dim_name AS dim_name, t.dim_value AS dim_value, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dim_name = h.dim_name AND t.dim_value = h.dim_value AND t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.dim_name, t.dim_value, t.metric_value, t.denom ORDER BY t.hour
```

## `detect_segments:revenue` — 1 call(s)

122,880 rows · 84.0 ms

```sql
WITH target AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, requests, fills, impressions, clicks, revenue, revenue AS metric_value, 0 AS denom FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} AND hour < {end:DateTime} AND requests >= {min_volume:UInt32} ), hist AS ( SELECT hour, dim_name, dim_value, toDayOfWeek(hour) AS dow, toHour(hour) AS hod, revenue AS metric_value FROM inmobi.events_hourly_by_dim WHERE hour < {end:DateTime} ) SELECT t.hour AS hour, t.dim_name AS dim_name, t.dim_value AS dim_value, t.metric_value AS actual, t.denom AS denom, quantileExact(0.5)(h.metric_value) AS baseline, stddevPop(h.metric_value) AS spread, count() AS baseline_samples FROM target AS t INNER JOIN hist AS h ON t.dim_name = h.dim_name AND t.dim_value = h.dim_value AND t.dow = h.dow AND t.hod = h.hod WHERE h.hour < t.hour AND h.hour >= t.hour - toIntervalWeek({weeks:UInt8}) GROUP BY t.hour, t.dim_name, t.dim_value, t.metric_value, t.denom ORDER BY t.hour
```

## `localize:ecpm` — 1 call(s)

307,200 rows · 55.2 ms

```sql
SELECT 0 AS weeks_back, dim_name, dim_value, sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS impressions, sum(clicks) AS clicks, sum(revenue) AS revenue FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} AND hour <= {end:DateTime} GROUP BY dim_name, dim_value UNION ALL SELECT 1 AS weeks_back, dim_name, dim_value, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} - toIntervalWeek(1) AND hour <= {end:DateTime} - toIntervalWeek(1) GROUP BY dim_name, dim_value UNION ALL SELECT 2 AS weeks_back, dim_name, dim_value, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} - toIntervalWeek(2) AND hour <= {end:DateTime} - toIntervalWeek(2) GROUP BY dim_name, dim_value UNION ALL SELECT 3 AS weeks_back, dim_name, dim_value, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} - toIntervalWeek(3) AND hour <= {end:DateTime} - toIntervalWeek(3) GROUP BY dim_name, dim_value UNION ALL SELECT 4 AS weeks_back, dim_name, dim_value, sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM inmobi.events_hourly_by_dim WHERE hour >= {start:DateTime} - toIntervalWeek(4) AND hour <= {end:DateTime} - toIntervalWeek(4) GROUP BY dim_name, dim_value
```

## `scan_intersect:ad_formatxcountry` — 1 call(s)

25,550,016 rows · 694.0 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, CAST(ad_format AS String) AS va, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, CAST(ad_format AS String) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:categoryxad_format` — 1 call(s)

25,550,016 rows · 746.0 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_apps','category', app_id) AS va, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','category', app_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:categoryxcountry` — 1 call(s)

25,550,016 rows · 1036.4 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_apps','category', app_id) AS va, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','category', app_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:categoryxpublisher_tier` — 1 call(s)

25,550,016 rows · 954.1 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_apps','category', app_id) AS va, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','category', app_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:device_modelxad_format` — 1 call(s)

25,550,016 rows · 752.5 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:device_modelxcategory` — 1 call(s)

25,550,016 rows · 1002.4 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, dictGetString('inmobi.dict_apps','category', app_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','category', app_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:device_modelxcountry` — 1 call(s)

25,550,016 rows · 867.4 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:device_modelxos_version` — 1 call(s)

25,550,016 rows · 905.0 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:device_modelxpublisher_tier` — 1 call(s)

25,550,016 rows · 980.8 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:os_versionxad_format` — 1 call(s)

25,550,016 rows · 707.8 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS va, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:os_versionxcategory` — 1 call(s)

25,550,016 rows · 1000.8 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS va, dictGetString('inmobi.dict_apps','category', app_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','category', app_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:os_versionxcountry` — 1 call(s)

25,550,016 rows · 850.2 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS va, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:os_versionxpublisher_tier` — 1 call(s)

25,550,016 rows · 997.4 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS va, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:publisher_tierxad_format` — 1 call(s)

25,550,016 rows · 760.7 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS va, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:publisher_tierxcountry` — 1 call(s)

25,550,016 rows · 971.9 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS va, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:regionxad_format` — 1 call(s)

25,550,016 rows · 752.7 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, CAST(ad_format AS String) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:regionxcategory` — 1 call(s)

25,550,016 rows · 1018.5 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, dictGetString('inmobi.dict_apps','category', app_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','category', app_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:regionxcountry` — 1 call(s)

25,550,016 rows · 879.5 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','country', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:regionxdevice_model` — 1 call(s)

25,550,016 rows · 935.6 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','device_model', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:regionxos_version` — 1 call(s)

25,550,016 rows · 899.2 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','os_version', geo_device_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```

## `scan_intersect:regionxpublisher_tier` — 1 call(s)

25,550,016 rows · 1000.2 ms

```sql
WITH cells AS ( SELECT toDate(event_time) AS day, toDayOfWeek(event_time) AS dow, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS vb, (sum(is_filled)) / (count()) AS metric_value, count() AS requests FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, dow, va, vb HAVING requests >= {minreq:UInt32} ), pa AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_geo_device','region', geo_device_id) AS va, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, va ), pb AS ( SELECT toDate(event_time) AS day, dictGetString('inmobi.dict_apps','publisher_tier', app_id) AS vb, (sum(is_filled)) / (count()) AS v FROM inmobi.ad_events WHERE event_time >= {start:DateTime} - toIntervalWeek({weeks:UInt8}) AND event_time <= {end:DateTime} GROUP BY day, vb ) SELECT t.day AS day, t.va AS va, t.vb AS vb, t.metric_value AS actual, t.requests AS requests, quantileExact(0.5)(h.metric_value) AS baseline, any(pa_now.v) AS pa_now, quantileExact(0.5)(pa_hist.v) AS pa_base, any(pb_now.v) AS pb_now, quantileExact(0.5)(pb_hist.v) AS pb_base FROM cells AS t INNER JOIN cells AS h ON t.va=h.va AND t.vb=h.vb AND t.dow=h.dow AND h.day < t.day INNER JOIN pa AS pa_now ON pa_now.day = t.day AND pa_now.va = t.va INNER JOIN pa AS pa_hist ON pa_hist.va = t.va AND toDayOfWeek(pa_hist.day)=t.dow AND pa_hist.day < t.day INNER JOIN pb AS pb_now ON pb_now.day = t.day AND pb_now.vb = t.vb INNER JOIN pb AS pb_hist ON pb_hist.vb = t.vb AND toDayOfWeek(pb_hist.day)=t.dow AND pb_hist.day < t.day WHERE t.day >= toDate({start:DateTime}) GROUP BY day, va, vb, actual, requests
```
