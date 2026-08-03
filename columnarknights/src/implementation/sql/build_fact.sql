-- Joins the raw fact table to all three dimension tables exactly once, so every
-- later drill-down query reads a single flat table. advertiser_id is empty on
-- unfilled requests, so the advertisers join legitimately misses for those rows;
-- ifNull() turns that into '' rather than NULL.
INSERT INTO fact_events
SELECT
    e.event_time,
    e.app_id,
    ifNull(a.category, '')          AS category,
    ifNull(a.publisher_tier, '')    AS publisher_tier,
    e.geo_device_id,
    ifNull(g.region, '')            AS region,
    ifNull(g.country, '')           AS country,
    ifNull(g.device_model, '')      AS device_model,
    ifNull(g.os_version, '')        AS os_version,
    e.advertiser_id,
    ifNull(adv.vertical, '')        AS vertical,
    ifNull(adv.campaign_type, '')   AS campaign_type,
    e.ad_format,
    e.is_filled,
    e.is_impression,
    e.is_click,
    e.revenue
FROM ad_events_raw AS e
LEFT JOIN apps AS a ON e.app_id = a.app_id
LEFT JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
LEFT JOIN advertisers AS adv ON e.advertiser_id = adv.advertiser_id;
