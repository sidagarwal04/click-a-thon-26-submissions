CREATE VIEW silver.dq_funnel_violations
(
    `event_date` Date,
    `impression_without_fill` UInt64,
    `click_without_impression` UInt64,
    `revenue_without_impression` UInt64,
    `advertiser_on_unfilled` UInt64,
    `total_rows` UInt64
)
AS SELECT
    toDate(event_time) AS event_date,
    countIf((is_impression = 1) AND (is_filled = 0)) AS impression_without_fill,
    countIf((is_click = 1) AND (is_impression = 0)) AS click_without_impression,
    countIf((revenue > 0) AND (is_impression = 0)) AS revenue_without_impression,
    countIf((is_filled = 0) AND (coalesce(nullIf(advertiser_id, ''), '') != '')) AS advertiser_on_unfilled,
    count() AS total_rows
FROM default.clickathon_ad_events
GROUP BY event_date
ORDER BY event_date ASC
