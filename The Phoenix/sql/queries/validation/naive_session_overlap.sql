-- The wrong answer, on purpose. Counts a session as watching for its entire span,
-- start to end, exactly as the problem statement describes the naive approach.
-- Kept so the overcount is a measured number in the pitch, not an assertion.
WITH sess AS
(
    SELECT
        video_session_id,
        min(toDateTime(event_timestamp)) AS s,
        max(toDateTime(event_timestamp)) AS e
    FROM events_src
    GROUP BY video_session_id
)
SELECT
    minute,
    uniqExact(video_session_id) AS concurrent_sessions
FROM
(
    SELECT
        video_session_id,
        arrayJoin(timeSlots(s, toUInt32(greatest(dateDiff('second', s, e) - 1, 0)), 60)) AS minute
    FROM sess
)
GROUP BY minute
ORDER BY minute;
