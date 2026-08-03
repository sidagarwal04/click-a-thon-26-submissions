---
name: atlys-segment-comparison
description: Use when comparing an Atlys metric across segments (device, os, geo/country, destination, user type, acquisition) to find where performance is unusually good or bad. Provides normalization for messy data and volume guardrails.
---

# Skill: Segment Comparison

Goal: compare a metric across segments to find where something is unusually good or
bad, with enough rigor that a PM can trust it. Compute in ClickHouse; return top-N.

## Standard segment dimensions
- Device: `lower(device_type)` and `os` (handle NULL os with android device_type).
- Geo: `geoip_country_code` (ISO-2), optionally `geoip_subdivision_1_code`.
- Destination: `destination`.
- User: `is_new_user` (auth), `is_guest`, `is_enterprise`, `co_travelers`.
- Acquisition: `gclid != ''` => paid search.

## Normalization (apply and state it)
Flat tables:
```sql
lower(coalesce(nullIf(device_type,''),'unknown')) AS device_norm,
coalesce(nullIf(os,''), if(lower(device_type)='android','android','unknown')) AS os_norm,
upper(coalesce(nullIf(geoip_country_code,''),'??'))  AS geo
```
JSON `payload` tables (same logic wrapping `payload.*`; see `atlys-json-payload-access`):
```sql
lower(coalesce(nullIf(toString(payload.device_type),''),'unknown')) AS device_norm,
coalesce(nullIf(toString(payload.os),''), if(lower(toString(payload.device_type))='android','android','unknown')) AS os_norm,
upper(coalesce(nullIf(toString(payload.geoip_country_code),''),'??')) AS geo
```

## Pattern — metric by segment with volume guardrail
Always return the denominator so small segments can be discounted.
```sql
SELECT
    upper(coalesce(nullIf(geoip_country_code,''),'??')) AS geo,
    lower(coalesce(nullIf(device_type,''),'unknown'))   AS device_norm,
    uniqExact(user_id) AS users,
    countIf(<success_condition>) AS successes,
    round(successes / nullIf(users,0), 4) AS rate
FROM atlys.<table>
WHERE timestamp >= {start:DateTime} AND timestamp < {end:DateTime}
GROUP BY geo, device_norm
HAVING users >= 200          -- ignore tiny segments
ORDER BY rate ASC            -- worst-performing first
LIMIT 25;
```
On a JSON `payload` table, swap the columns for `payload.*` (e.g.
`uniqExact(payload.user_id)`, `upper(coalesce(nullIf(toString(payload.geoip_country_code),''),'??'))`),
add `WHERE payload.event = '<stage>'` when the success condition is event-type-specific, and
window on `payload.timestamp`.

## Comparing two segments (e.g. iOS vs Android)
Compute the rate for each, the absolute and relative gap, and the sample sizes.
Report relative gap as the headline ("iOS converts 15% worse than Android") but only
if both segments clear the volume guardrail. If a segment is small, mark confidence
Low.

## Significance (lightweight)
You are not running a full stats test in SQL, but:
- Require a minimum volume (e.g. `users >= 200`) before calling a gap real.
- Prefer relative differences that are both sizable (>~10%) and on large bases.
- If a difference is small or on a thin base, say "not conclusive" and lower confidence.

## Always
- Cut by device AND geo AND destination before concluding a driver.
- Exclude or flag `is_back_filled = 1` and non-empty `duplicate_id` for behaviour reads.
- Return only aggregated rows (top-N), never raw events.
