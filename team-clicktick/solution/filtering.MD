**Why our data model lets you “filter‑fast” on every common business key**

| Dimension | What we store in the table | How its storage and ordering keep scan time low |
|-----------|-----------------------------|-----------------------------------------------|
| **platform** | `platform` column (e.g., *JIO_ANDROID_TV, ANDROID_PHONE*) stored as a simple String in both `concurrency_deltas` and `session_active_intervals_clean`. | Partitions are usually defined by **date + partition key “platform”** (ClickHouse can skip whole partitions when you filter on a single platform).  The table is sorted by `(platform, minute_bucket)` or `(video_session_id, interval_start)`, so all rows for a given platform live next to one another and are read in one contiguous block. |
| **country** | `country` column (e.g., *IN, US*) stored alongside platform. | The sort key `(platform, country, minute_bucket)` gives an extra level of grouping; filtering on country still benefits from the primary‑key index because all rows for a country within a specific platform cluster together. |
| **content** (`content_id`) | Stored in every analytics table (delta and interval tables).  This is a numeric key so hash‑collisions are minimal. | Indexing `content_id` in combination with the primary key lets the engine keep only a small slice of blocks.  If you want to aggregate just a handful of titles, the query touches only those rows. |
| **video_type** (`audio_language`, `player_version`, etc.) | Stored as string columns and included in the sort keys. | The same principle applies: grouping by `(platform, country, content_id, video_type, minute_bucket)` lets ClickHouse prune to a narrow set of partitions when you filter on any subset. |
| **time grain** (minute, hour, day) | Time‑based columns are stored as `DateTime` for minutes, and the tables are partitioned by date (`toYYYYMMDD(minute_bucket)` or equivalent). | A minute‑level granularity means each row represents *exactly one* minute of delta.  Queries that ask “how many users in July 2026?” only scan the partitions belonging to those months, which is orders of magnitude less than the whole dataset. |

---

## How filtering actually works

1. **Partition pruning** – ClickHouse checks your `WHERE` clause against the partition key (`toYYYYMMDD(minute_bucket)`, platform, country).  If the clause matches only a subset, it reads only those blocks.

2. **Primary‑key / sorting key navigation** – The sort key is an in‑memory B‑tree that points directly to the row ranges for the filtered combination of dimensions.  No scanning of the whole table is required; all matching rows come in one sorted stream.

3. **Memory‑efficient aggregation** – Once ClickHouse has the relevant tuples, it performs the aggregate (`COUNT`, `SUM`, `AVG`, `MAX`) entirely in RAM without looking elsewhere.  
   Because our tables store only the fields needed for the specific metric (delta, interval start/end), the data volume is tiny compared to the raw event log.