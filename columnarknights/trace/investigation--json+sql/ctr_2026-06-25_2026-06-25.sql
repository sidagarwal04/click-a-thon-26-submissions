-- Investigation: ctr, 2026-06-25 to 2026-06-25 (baseline: 2026-06-18 to 2026-06-18)

-- Step 1: Baseline window aggregate (2026-06-18 to 2026-06-18)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-18';

-- Step 2: Current window aggregate (2026-06-25 to 2026-06-25)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-25' AND '2026-06-25';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 10: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 11: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;

-- Step 12: Depth 1 (within country=IN) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN'
        GROUP BY segment;

-- Step 13: Depth 1 (within country=IN) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN'
        GROUP BY segment;

-- Step 14: Depth 1 (within country=IN) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN'
        GROUP BY segment;

-- Step 15: Depth 1 (within country=IN) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN'
        GROUP BY segment;

-- Step 16: Depth 1 (within country=IN) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN'
        GROUP BY segment;

-- Step 17: Depth 1 (within country=IN) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN'
        GROUP BY segment;

-- Step 18: Depth 1 (within country=IN) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN'
        GROUP BY segment;

-- Step 19: Depth 1 (within country=IN) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN'
        GROUP BY segment;

-- Step 20: Depth 2 (within country=IN, device_model=Pixel 8) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 21: Depth 2 (within country=IN, device_model=Pixel 8) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 22: Depth 2 (within country=IN, device_model=Pixel 8) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 23: Depth 2 (within country=IN, device_model=Pixel 8) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 24: Depth 2 (within country=IN, device_model=Pixel 8) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 25: Depth 2 (within country=IN, device_model=Pixel 8) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 26: Depth 2 (within country=IN, device_model=Pixel 8) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 27: Depth 3 (within country=IN, device_model=Pixel 8, campaign_type=CPI) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 28: Depth 3 (within country=IN, device_model=Pixel 8, campaign_type=CPI) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 29: Depth 3 (within country=IN, device_model=Pixel 8, campaign_type=CPI) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 30: Depth 3 (within country=IN, device_model=Pixel 8, campaign_type=CPI) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 31: Depth 3 (within country=IN, device_model=Pixel 8, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 32: Depth 3 (within country=IN, device_model=Pixel 8, campaign_type=CPI) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 33: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 34: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 35: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 36: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 37: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 38: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video, os_version=Android 15) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 39: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video, os_version=Android 15) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 40: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video, os_version=Android 15) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 41: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video, os_version=Android 15) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 42: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 43: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video, category=finance) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 44: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video, category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 45: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, ad_format=video, category=finance) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 46: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 47: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 48: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 49: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 50: Depth 4 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 51: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming, publisher_tier=tier_1) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 52: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 53: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 54: Depth 5 (within country=IN, device_model=Pixel 8, campaign_type=CPI, vertical=gaming, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND campaign_type = 'CPI' AND vertical = 'gaming' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 55: Depth 3 (within country=IN, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 56: Depth 3 (within country=IN, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 57: Depth 3 (within country=IN, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 58: Depth 3 (within country=IN, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 59: Depth 3 (within country=IN, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 60: Depth 3 (within country=IN, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 61: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 62: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 63: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 64: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 65: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 66: Depth 5 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 67: Depth 5 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 68: Depth 5 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 69: Depth 5 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video'
        GROUP BY segment;

-- Step 70: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 71: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video, category=finance) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 72: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video, category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 73: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video, publisher_tier=tier_2) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 74: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video, publisher_tier=tier_2) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 75: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, ad_format=video, publisher_tier=tier_2) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND ad_format = 'video' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 76: Depth 5 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance'
        GROUP BY segment;

-- Step 77: Depth 5 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance'
        GROUP BY segment;

-- Step 78: Depth 5 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance'
        GROUP BY segment;

-- Step 79: Depth 5 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance'
        GROUP BY segment;

-- Step 80: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance, ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 81: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance, ad_format=video) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 82: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance, ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 83: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance, publisher_tier=tier_2) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 84: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance, publisher_tier=tier_2) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 85: Depth 6 (within country=IN, device_model=Pixel 8, os_version=Android 14, campaign_type=CPI, category=finance, publisher_tier=tier_2) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND campaign_type = 'CPI' AND category = 'finance' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 86: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, vertical=cpg) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 87: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, vertical=cpg) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 88: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, vertical=cpg) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 89: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 90: Depth 4 (within country=IN, device_model=Pixel 8, os_version=Android 14, vertical=cpg) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND device_model = 'Pixel 8' AND os_version = 'Android 14' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 91: Depth 2 (within country=IN, publisher_tier=tier_1) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 92: Depth 2 (within country=IN, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 93: Depth 2 (within country=IN, publisher_tier=tier_1) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 94: Depth 2 (within country=IN, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 95: Depth 2 (within country=IN, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 96: Depth 2 (within country=IN, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 97: Depth 2 (within country=IN, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 98: Depth 3 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 99: Depth 3 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 100: Depth 3 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 101: Depth 3 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 102: Depth 3 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 103: Depth 3 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 104: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 105: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 106: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 107: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 108: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 109: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, category=entertainment) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND category = 'entertainment'
        GROUP BY segment;

-- Step 110: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, category=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND category = 'entertainment'
        GROUP BY segment;

-- Step 111: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, category=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND category = 'entertainment'
        GROUP BY segment;

-- Step 112: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, category=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND category = 'entertainment'
        GROUP BY segment;

-- Step 113: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 114: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 115: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 116: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 117: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto, category=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'gaming'
        GROUP BY segment;

-- Step 118: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto, category=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'gaming'
        GROUP BY segment;

-- Step 119: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto, category=gaming) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'gaming'
        GROUP BY segment;

-- Step 120: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto, device_model=iPhone 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 121: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 122: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, ad_format=rewarded, vertical=auto, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND ad_format = 'rewarded' AND vertical = 'auto' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 123: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 124: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 125: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 126: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 127: Depth 4 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 128: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 129: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 130: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 131: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 132: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming'
        GROUP BY segment;

-- Step 133: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming'
        GROUP BY segment;

-- Step 134: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming'
        GROUP BY segment;

-- Step 135: Depth 5 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming'
        GROUP BY segment;

-- Step 136: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 137: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 138: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 139: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming, campaign_type=CPI) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 140: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 141: Depth 6 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming, campaign_type=CPI) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 142: Depth 7 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming, campaign_type=CPI, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming' AND campaign_type = 'CPI' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 143: Depth 7 (within country=IN, publisher_tier=tier_1, os_version=iOS 16.4, vertical=cpg, category=gaming, campaign_type=CPI, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND os_version = 'iOS 16.4' AND vertical = 'cpg' AND category = 'gaming' AND campaign_type = 'CPI' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 144: Depth 3 (within country=IN, publisher_tier=tier_1, category=news) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 145: Depth 3 (within country=IN, publisher_tier=tier_1, category=news) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 146: Depth 3 (within country=IN, publisher_tier=tier_1, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 147: Depth 3 (within country=IN, publisher_tier=tier_1, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 148: Depth 3 (within country=IN, publisher_tier=tier_1, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 149: Depth 3 (within country=IN, publisher_tier=tier_1, category=news) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 150: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 151: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 152: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 153: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 154: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 155: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, os_version=Android 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 156: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, os_version=Android 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 157: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, os_version=Android 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 158: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, os_version=Android 14) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 159: Depth 6 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, os_version=Android 14, campaign_type=CPM) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND os_version = 'Android 14' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 160: Depth 6 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, os_version=Android 14, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND os_version = 'Android 14' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 161: Depth 6 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, os_version=Android 14, campaign_type=CPM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND os_version = 'Android 14' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 162: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, device_model=Galaxy S23) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 163: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, device_model=Galaxy S23) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 164: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, device_model=Galaxy S23) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 165: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, device_model=Galaxy S23) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 166: Depth 6 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, device_model=Galaxy S23, campaign_type=CPM) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND device_model = 'Galaxy S23' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 167: Depth 6 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, device_model=Galaxy S23, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND device_model = 'Galaxy S23' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 168: Depth 6 (within country=IN, publisher_tier=tier_1, category=news, vertical=gaming, device_model=Galaxy S23, campaign_type=CPM) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND vertical = 'gaming' AND device_model = 'Galaxy S23' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 169: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 170: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 171: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 172: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 173: Depth 4 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 174: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI, vertical=entertainment) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 175: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI, vertical=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 176: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI, vertical=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 177: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI, vertical=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 178: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI, device_model=Galaxy S23) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 179: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI, device_model=Galaxy S23) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 180: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI, device_model=Galaxy S23) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 181: Depth 5 (within country=IN, publisher_tier=tier_1, category=news, campaign_type=CPI, device_model=Galaxy S23) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'IN' AND publisher_tier = 'tier_1' AND category = 'news' AND campaign_type = 'CPI' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 182: Depth 1 (within device_model=Pixel 8) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 183: Depth 1 (within device_model=Pixel 8) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 184: Depth 1 (within device_model=Pixel 8) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 185: Depth 1 (within device_model=Pixel 8) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 186: Depth 1 (within device_model=Pixel 8) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 187: Depth 1 (within device_model=Pixel 8) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 188: Depth 1 (within device_model=Pixel 8) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 189: Depth 1 (within device_model=Pixel 8) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 190: Depth 2 (within device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 191: Depth 2 (within device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 192: Depth 2 (within device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 193: Depth 2 (within device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 194: Depth 2 (within device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 195: Depth 2 (within device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 196: Depth 2 (within device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 197: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, country=ES) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 198: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, country=ES) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 199: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, country=ES) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 200: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, country=ES) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 201: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, country=ES) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 202: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, country=ES) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 203: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, os_version=Android 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 204: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, os_version=Android 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 205: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, os_version=Android 14) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 206: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, os_version=Android 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 207: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, os_version=Android 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 208: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 209: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 210: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 211: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 212: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 213: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce, os_version=Android 12) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 214: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 215: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 216: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, country=ES, vertical=ecommerce, os_version=Android 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'ecommerce' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 217: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, category=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 218: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, category=gaming) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 219: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, category=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 220: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, category=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 221: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, category=gaming) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 222: Depth 3 (within device_model=Pixel 8, ad_format=rewarded, category=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 223: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA'
        GROUP BY segment;

-- Step 224: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA'
        GROUP BY segment;

-- Step 225: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA'
        GROUP BY segment;

-- Step 226: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA'
        GROUP BY segment;

-- Step 227: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA'
        GROUP BY segment;

-- Step 228: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 229: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 230: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 231: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 232: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12, country=AE) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12' AND country = 'AE'
        GROUP BY segment;

-- Step 233: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12, country=AE) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12' AND country = 'AE'
        GROUP BY segment;

-- Step 234: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12, country=AE) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12' AND country = 'AE'
        GROUP BY segment;

-- Step 235: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 236: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 237: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 238: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, vertical=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 239: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, vertical=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 240: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, vertical=entertainment) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 241: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, region=MEA, vertical=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND region = 'MEA' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 242: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel'
        GROUP BY segment;

-- Step 243: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel'
        GROUP BY segment;

-- Step 244: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel'
        GROUP BY segment;

-- Step 245: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel'
        GROUP BY segment;

-- Step 246: Depth 4 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel'
        GROUP BY segment;

-- Step 247: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, country=ID) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND country = 'ID'
        GROUP BY segment;

-- Step 248: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, country=ID) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND country = 'ID'
        GROUP BY segment;

-- Step 249: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, country=ID) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND country = 'ID'
        GROUP BY segment;

-- Step 250: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, country=ID) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND country = 'ID'
        GROUP BY segment;

-- Step 251: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 252: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 253: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, os_version=Android 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 254: Depth 5 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, os_version=Android 12) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 255: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, os_version=Android 12, region=APAC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND os_version = 'Android 12' AND region = 'APAC'
        GROUP BY segment;

-- Step 256: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, os_version=Android 12, region=APAC) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND os_version = 'Android 12' AND region = 'APAC'
        GROUP BY segment;

-- Step 257: Depth 6 (within device_model=Pixel 8, ad_format=rewarded, category=gaming, vertical=travel, os_version=Android 12, region=APAC) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND category = 'gaming' AND vertical = 'travel' AND os_version = 'Android 12' AND region = 'APAC'
        GROUP BY segment;

-- Step 258: Depth 2 (within device_model=Pixel 8, category=gaming) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND device_model = 'Pixel 8' AND category = 'gaming'
        GROUP BY segment;

-- Step 259: Depth 2 (within device_model=Pixel 8, category=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming'
        GROUP BY segment;

-- Step 260: Depth 2 (within device_model=Pixel 8, category=gaming) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming'
        GROUP BY segment;

-- Step 261: Depth 2 (within device_model=Pixel 8, category=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming'
        GROUP BY segment;

-- Step 262: Depth 2 (within device_model=Pixel 8, category=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming'
        GROUP BY segment;

-- Step 263: Depth 2 (within device_model=Pixel 8, category=gaming) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming'
        GROUP BY segment;

-- Step 264: Depth 2 (within device_model=Pixel 8, category=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming'
        GROUP BY segment;

-- Step 265: Depth 3 (within device_model=Pixel 8, category=gaming, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 266: Depth 3 (within device_model=Pixel 8, category=gaming, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 267: Depth 3 (within device_model=Pixel 8, category=gaming, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 268: Depth 3 (within device_model=Pixel 8, category=gaming, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 269: Depth 3 (within device_model=Pixel 8, category=gaming, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 270: Depth 3 (within device_model=Pixel 8, category=gaming, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 271: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 272: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 273: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 274: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 275: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 276: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 277: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 278: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 279: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 280: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12, country=AE) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12' AND country = 'AE'
        GROUP BY segment;

-- Step 281: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12, country=AE) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12' AND country = 'AE'
        GROUP BY segment;

-- Step 282: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12, country=AE) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12' AND country = 'AE'
        GROUP BY segment;

-- Step 283: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 284: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 285: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 286: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, vertical=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 287: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, vertical=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 288: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, vertical=entertainment) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 289: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, region=MEA, vertical=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND region = 'MEA' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 290: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 291: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 292: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 293: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 294: Depth 4 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 295: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, country=ID) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND country = 'ID'
        GROUP BY segment;

-- Step 296: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, country=ID) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND country = 'ID'
        GROUP BY segment;

-- Step 297: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, country=ID) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND country = 'ID'
        GROUP BY segment;

-- Step 298: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, country=ID) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND country = 'ID'
        GROUP BY segment;

-- Step 299: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 300: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 301: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, os_version=Android 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 302: Depth 5 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, os_version=Android 12) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 303: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, os_version=Android 12, region=APAC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'Android 12' AND region = 'APAC'
        GROUP BY segment;

-- Step 304: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, os_version=Android 12, region=APAC) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'Android 12' AND region = 'APAC'
        GROUP BY segment;

-- Step 305: Depth 6 (within device_model=Pixel 8, category=gaming, ad_format=rewarded, vertical=travel, os_version=Android 12, region=APAC) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'Android 12' AND region = 'APAC'
        GROUP BY segment;

-- Step 306: Depth 3 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 307: Depth 3 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 308: Depth 3 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 309: Depth 3 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 310: Depth 3 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 311: Depth 3 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 312: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 313: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 314: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 315: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 316: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 317: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, country=ES) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 318: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, country=ES) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 319: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, country=ES) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 320: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, country=ES) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 321: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, country=ES, vertical=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 322: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, country=ES, vertical=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 323: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, country=ES, vertical=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 324: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 325: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 326: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 327: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA'
        GROUP BY segment;

-- Step 328: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA, country=AE) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 329: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA, country=AE) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 330: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA, country=AE) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 331: Depth 7 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA, country=AE, campaign_type=CPM) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA' AND country = 'AE' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 332: Depth 7 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA, country=AE, campaign_type=CPM) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA' AND country = 'AE' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 333: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA, os_version=Android 15) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 334: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA, os_version=Android 15) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 335: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, ad_format=rewarded, region=MEA, os_version=Android 15) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND ad_format = 'rewarded' AND region = 'MEA' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 336: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU'
        GROUP BY segment;

-- Step 337: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU'
        GROUP BY segment;

-- Step 338: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU'
        GROUP BY segment;

-- Step 339: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU'
        GROUP BY segment;

-- Step 340: Depth 4 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU'
        GROUP BY segment;

-- Step 341: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 342: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 343: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 344: Depth 5 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 345: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, country=ES) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 346: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, country=ES) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 347: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, country=ES) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND country = 'ES'
        GROUP BY segment;

-- Step 348: Depth 7 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, country=ES, vertical=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 349: Depth 7 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, country=ES, vertical=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND country = 'ES' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 350: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, vertical=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 351: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, vertical=entertainment) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 352: Depth 6 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, vertical=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 353: Depth 7 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, vertical=entertainment, country=ES) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND vertical = 'entertainment' AND country = 'ES'
        GROUP BY segment;

-- Step 354: Depth 7 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, vertical=entertainment, country=ES) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND vertical = 'entertainment' AND country = 'ES'
        GROUP BY segment;

-- Step 355: Depth 7 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, vertical=entertainment, os_version=Android 13) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND vertical = 'entertainment' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 356: Depth 7 (within device_model=Pixel 8, category=gaming, publisher_tier=tier_2, region=EU, ad_format=rewarded, vertical=entertainment, os_version=Android 13) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-18' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-18' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-25' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-25' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-18' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Pixel 8' AND category = 'gaming' AND publisher_tier = 'tier_2' AND region = 'EU' AND ad_format = 'rewarded' AND vertical = 'entertainment' AND os_version = 'Android 13'
        GROUP BY segment;
