# Legacy projection remediation

The Context Agent flags every id-leading `ORDER BY` as a `stale_entry`.
This tool prices the defect and applies the production-safe fix: a projection,
not a table rewrite.

## Id-leading tables detected

| table | sorting_key | rows | bytes |
| --- | --- | ---: | ---: |
| `destination_card_clicked` | `id, timestamp, user_id` | 1,000,000 | 322,398,541 |
| `search_typed` | `id, timestamp, user_id` | 599,630 | 100,099,489 |
| `landing_page_scrolled` | `id, timestamp, user_id` | 499,786 | 80,306,202 |
| `auth_completed` | `id, timestamp, user_id` | 183,790 | 34,259,396 |
| `application_started` | `id, timestamp, user_id` | 154,413 | 29,842,186 |
| `document_uploaded` | `id, timestamp, user_id` | 20,446 | 3,963,196 |
| `pay_now_clicked` | `id, timestamp, user_id` | 14,739 | 2,965,129 |
| `purchase_completed` | `id, timestamp, user_id` | 7,054 | 1,411,508 |

## Remediated: `destination_card_clicked`

```sql
ALTER TABLE destination_card_clicked ADD PROJECTION p_funnel (
  SELECT *
  ORDER BY (toDate(timestamp), device_type, user_id)
)
ALTER TABLE destination_card_clicked MATERIALIZE PROJECTION p_funnel;
```

### Probe query

```sql
SELECT
    toDate(timestamp) AS day,
    device_type,
    uniqIf(user_id, user_id IS NOT NULL AND toString(user_id) != '') AS users
FROM destination_card_clicked
WHERE timestamp >= (SELECT max(timestamp) - INTERVAL 30 DAY FROM destination_card_clicked)
  AND device_type = (
        SELECT device_type FROM destination_card_clicked
        WHERE device_type IS NOT NULL AND toString(device_type) != ''
        GROUP BY device_type ORDER BY count() DESC LIMIT 1
      )
GROUP BY day, device_type
ORDER BY day, device_type
LIMIT 200
```

### Measured cost

| | read_rows | read_bytes | duration_ms |
| --- | ---: | ---: | ---: |
| before (primary key) | 2,197,352 | 29,122,224 | 41 |
| after (projection) | 1,197,364 | 25,122,512 | 21 |

**Ratio:** 1.16× fewer bytes read after materialising `p_funnel`.

### EXPLAIN before

```
Output: toDate(timestamp), device_type, uniqIf(user_id, 1 AND notEmpty(toString(user_id)))

Limit (preliminary LIMIT)
│  Limit 200
│  Offset 0
└──Sorting (Sorting for ORDER BY)
   │  Sort description: toDate(timestamp) ASC, device_type ASC
   │  Limit 200
   └──Aggregating
      │  Keys: toDate(timestamp), device_type
      │  Aggregates: uniqIf(user_id, 1 AND notEmpty(toString(user_id)))
      │  Skip merging: 0
      └──ReadFromMergeTree (atlys.destination_card_clicked)
            Read type: Default
            Parts: 2 | Granules: 25
            Output: timestamp, device_type, user_id
            Prewhere filter
            Prewhere filter column:  timestamp >= 1780271980 AND device_type = 'ios'
            Indexes:
              Min-Max
                Keys:
                  timestamp
                Condition: (timestamp in [1780271980, +Inf))
                Parts: 2/12
                Granules: 25/128
              Partition
                Keys:
                  toYYYYMM(timestamp)
                Condition: (toYYYYMM(timestamp) in [202605, +Inf))
                Parts: 2/2
                Granules: 25/25
              PrimaryKey
                Keys:
                  timestamp
                Condition: (timestamp in [1780271980, +Inf))
                Parts: 2/2
                Granules: 25/25
                Search Algorithm: generic exclusion search
              Ranges: 2
```

### EXPLAIN after

```
Output: toDate(timestamp), device_type, uniqIf(user_id, 1 AND notEmpty(toString(user_id)))

Limit (preliminary LIMIT)
│  Limit 200
│  Offset 0
└──Sorting (Sorting for ORDER BY)
   │  Sort description: toDate(timestamp) ASC, device_type ASC
   │  Limit 200
   └──Aggregating
      │  Keys: toDate(timestamp), device_type
      │  Aggregates: uniqIf(user_id, 1 AND notEmpty(toString(user_id)))
      │  Skip merging: 0
      └──ReadFromMergeTree (p_funnel)
            Read type: Default
            Parts: 2 | Granules: 25
            Output: timestamp, device_type, user_id
            Prewhere filter
            Prewhere filter column:  device_type = 'ios' AND timestamp >= 1780271980
            Indexes:
              PrimaryKey
                Keys:
                  toDate(timestamp)
                  device_type
                Condition: and((toDate(timestamp) in [20604, +Inf)), (device_type in ['ios', 'ios']))
                Parts: 2/2
                Granules: 25/25
                Search Algorithm: generic exclusion search
              Ranges: 2
```
