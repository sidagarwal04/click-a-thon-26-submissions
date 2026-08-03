-- SERVING: peak and average concurrency filtered by TITLE or CATEGORY.
--
--   title    : String ('' = all; exact match against content.title)
--   category : String ('' = all; exact match against content.category)
--   from_ts, to_ts : String  (range, [from, to))
--   grain_s  : UInt32
--
-- Why this is its own query instead of two more columns in concurrency_deltas: title and
-- category are attributes of content_id, which the serving table already carries, so
-- storing them again would denormalize 33,464 strings into every delta row and force a
-- rebuild to fix a typo in a title. Resolving the filter to a content_id set FIRST keeps
-- the serving read on the serving table.
--
-- Why a JOIN-shaped IN and not a dictionary: dictGet was tried and rejected on this Cloud
-- service; it returned '' for keys that provably exist because dictionaries load per
-- replica (see sql/schema/02_content.sql). The content table is 33,464 rows; resolving the
-- id set costs nothing and is deterministic.
--
-- A category matching N titles sums their deltas, which is exactly the additive-delta
-- model doing its job: the category's concurrency is the sum of its contents'.
WITH ids AS
(
    SELECT content_id
    FROM content
    WHERE ({title:String}    = '' OR title    = {title:String})
      AND ({category:String} = '' OR category = {category:String})
),
filtered AS
(
    SELECT minute, sum(delta) AS d
    FROM concurrency_deltas
    WHERE content_id IN (SELECT content_id FROM ids)
      AND minute < parseDateTimeBestEffort({to_ts:String})
    GROUP BY minute
),
curve AS
(
    SELECT
        minute,
        toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrency
    FROM filtered
),
seeded_window AS
(
    -- Same one-pass seeding as peak_average.sql, same aliasing trap: the group key is `m`,
    -- never `minute`.
    SELECT
        if(minute < parseDateTimeBestEffort({from_ts:String}), parseDateTimeBestEffort({from_ts:String}), minute) AS m,
        argMax(concurrency, minute) AS concurrency
    FROM curve
    GROUP BY m
),
dense AS
(
    SELECT m AS minute, concurrency
    FROM seeded_window
    ORDER BY minute ASC
    WITH FILL
        FROM parseDateTimeBestEffort({from_ts:String})
        TO   parseDateTimeBestEffort({to_ts:String})
        STEP toIntervalMinute(1)
    INTERPOLATE (concurrency AS concurrency)
)
SELECT
    toStartOfInterval(minute, toIntervalSecond({grain_s:UInt32})) AS bucket,
    max(concurrency)            AS peak_concurrency,
    argMax(minute, concurrency) AS peak_minute,
    round(avg(concurrency), 2)  AS avg_all_minutes,
    ifNotFinite(round(avgIf(concurrency, concurrency > 0), 2), 0) AS avg_active_minutes,
    countIf(concurrency > 0)    AS minutes_with_audience
FROM dense
GROUP BY bucket
ORDER BY bucket
-- READ BUDGET: the id-set filter cannot prune the primary key (content_id is fourth in the
-- ORDER BY), so the worst shape reads the full delta series plus the content table. Same
-- 3x contract as peak_average.sql; recalibrate with scripts/bench.sh.
SETTINGS max_rows_to_read = 202000,
         max_bytes_to_read = 3300000;
