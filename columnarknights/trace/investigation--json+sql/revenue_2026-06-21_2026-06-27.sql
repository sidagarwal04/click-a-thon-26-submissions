-- Investigation: revenue, 2026-06-21 to 2026-06-27 (baseline: 2026-06-14 to 2026-06-20)

-- Step 1: Baseline window aggregate (2026-06-14 to 2026-06-20)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-14' AND '2026-06-20';

-- Step 2: Current window aggregate (2026-06-21 to 2026-06-27)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-21' AND '2026-06-27';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-14' AND '2026-06-20') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-21' AND '2026-06-27') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-14' AND '2026-06-27'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-14' AND '2026-06-20') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-21' AND '2026-06-27') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-14' AND '2026-06-27'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-14' AND '2026-06-20') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-21' AND '2026-06-27') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-14' AND '2026-06-27'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-14' AND '2026-06-20') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-21' AND '2026-06-27') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-14' AND '2026-06-27'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-14' AND '2026-06-20') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-21' AND '2026-06-27') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-14' AND '2026-06-27'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-14' AND '2026-06-20') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-21' AND '2026-06-27') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-14' AND '2026-06-27'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-14' AND '2026-06-20') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-14' AND '2026-06-20') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-21' AND '2026-06-27') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-21' AND '2026-06-27') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-14' AND '2026-06-27'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;
