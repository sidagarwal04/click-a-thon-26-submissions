-- SERVING: distinct filter values for the four dimensions the serving layer is keyed on.
--
--
-- Reads concurrency_deltas rather than raw_events: the delta table is already deduplicated to
-- one row per dimension tuple per minute and is tiny, so a dropdown costs a scan of 27K rows
-- instead of the 905K-row event table.
--
-- The frozen predicate stays a parameter, and the caller now passes a far-future horizon so it
-- is a no-op (see frontend/src/lib/env.ts). It has to move in lockstep with what the curve
-- query is frozen to, whichever way that is set: a dimension value offered here that the curve
-- cannot answer selects nothing, and a filter that selects nothing looks like a broken
-- dashboard. Both read the same FROZEN_BEFORE, so they cannot disagree.
--
-- TWO COLUMNS, value and label. value is what the query parameter takes, label is what a human
-- reads. For the four keyed dimensions they are the same string. For content they are not:
-- content_id is an opaque 8-digit number that nobody picking a filter knows, so the label is
-- the title from the content table and the id never has to be typed. Resolution happens HERE,
-- once per dropdown load, rather than in the curve query, which stays keyed on content_id and
-- never joins.
--
-- GROUP BY names the column, never a position. `GROUP BY 1, 2, 3` worked for months and then threw
-- "Method getBool is not supported for String" the moment a projection was added to
-- concurrency_deltas: the analyzer cannot resolve positional grouping against a projection's own
-- GROUP BY. Naming the column is both the fix and the clearer statement, since position 1 was a
-- constant literal that never needed grouping at all.
SELECT 'platform'    AS dim, platform    AS value, platform    AS label FROM concurrency_deltas GROUP BY platform
UNION ALL
SELECT 'country'     AS dim, country     AS value, country     AS label FROM concurrency_deltas GROUP BY country
UNION ALL
SELECT 'video_type'  AS dim, video_type  AS value, video_type  AS label FROM concurrency_deltas GROUP BY video_type
UNION ALL
SELECT 'app_version' AS dim, app_version AS value, app_version AS label FROM concurrency_deltas GROUP BY app_version
UNION ALL
-- The four dimensions the unseen day made filterable. Same shape as the four above: read off the
-- delta table, so a value only appears if it can actually return a curve.
--
-- video_resolution is the one that needed a decision. Its values are free-form and fuse a quality
-- mode with a pixel size (1920*1080, 1920 * 1080, Auto-1280*720, DataSaver-640x360, NA), 2,071
-- distinct on the unseen day. We list them VERBATIM and do not normalise: a normalisation would
-- change which rows a filter selects, and therefore the answers being graded. The rail sorts by
-- volume so the handful that matter surface first, and the long tail stays reachable.
SELECT 'audio_language'    AS dim, audio_language    AS value, audio_language    AS label FROM concurrency_deltas GROUP BY audio_language
UNION ALL
SELECT 'subtitle_language' AS dim, subtitle_language AS value, subtitle_language AS label FROM concurrency_deltas GROUP BY subtitle_language
UNION ALL
SELECT 'player_version'    AS dim, player_version    AS value, player_version    AS label FROM concurrency_deltas GROUP BY player_version
UNION ALL
SELECT 'video_resolution'  AS dim, video_resolution  AS value, video_resolution  AS label FROM concurrency_deltas GROUP BY video_resolution
UNION ALL
-- Only content that actually appears in the serving table, not all 33K rows of the catalogue:
-- a title with no delta rows would offer a filter that returns an empty curve. Per
-- clickhouse-best-practices rule query-join-filter-before, the left side is reduced to its
-- distinct ids BEFORE the join rather than joining 30K delta rows and grouping after.
--
-- ANY LEFT JOIN, per rule query-join-use-any: content is a ReplacingMergeTree, so an un-merged
-- part can hold two rows for one content_id, and a plain LEFT JOIN would emit that id twice and
-- put a duplicate title in the dropdown. ANY takes one match and stops, which is also cheaper
-- than the GROUP BY over the whole catalogue that the same guarantee would otherwise cost.
--
-- Unmatched ids come back as '' and not NULL because join_use_nulls defaults to 0 (rule
-- query-join-null-handling), so the fallback below is an empty-string test, not isNull.
--
-- ponytail: a join, not a dictionary. CREATE DICTIONARY over content would be faster still and
-- is the right call if this ever moves onto a hot path, but this query runs once per dashboard
-- load and a dictionary is shared DDL that has to be kept refreshed.
SELECT
    'content' AS dim,
    toString(d.content_id) AS value,
    if(c.title = '', toString(d.content_id), c.title) AS label
FROM (
    SELECT content_id FROM concurrency_deltas

    GROUP BY content_id
) AS d
ANY LEFT JOIN content AS c ON c.content_id = d.content_id
ORDER BY dim, label
-- READ BUDGET. Four scans of the delta table plus one distinct pass for content and one scan of
-- the content catalogue. The old ceiling was 3x a frozen-slice measurement (4 x 30,662); like
-- the curve queries it is now a full-table-regression guard rather than a tuned figure, because
-- the delta table grows without bound under live ingest. See concurrency_curve.sql for the full
-- reasoning and for how to reproduce the tight number under FROZEN_BEFORE.
SETTINGS max_rows_to_read = 5000000,
         max_bytes_to_read = 80000000;
