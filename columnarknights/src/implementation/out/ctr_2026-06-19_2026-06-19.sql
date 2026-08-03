-- Investigation: ctr, 2026-06-19 to 2026-06-19 (baseline: 2026-06-12 to 2026-06-12)

-- Step 1: Baseline window aggregate (2026-06-12 to 2026-06-12)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-12';

-- Step 2: Current window aggregate (2026-06-19 to 2026-06-19)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-19' AND '2026-06-19';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 10: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 11: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;

-- Step 12: Depth 1 (within country=NG) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 13: Depth 1 (within country=NG) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 14: Depth 1 (within country=NG) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 15: Depth 1 (within country=NG) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 16: Depth 1 (within country=NG) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 17: Depth 1 (within country=NG) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 18: Depth 1 (within country=NG) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 19: Depth 1 (within country=NG) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 20: Depth 2 (within country=NG, category=news) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND category = 'news'
        GROUP BY segment;

-- Step 21: Depth 2 (within country=NG, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news'
        GROUP BY segment;

-- Step 22: Depth 2 (within country=NG, category=news) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND category = 'news'
        GROUP BY segment;

-- Step 23: Depth 2 (within country=NG, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news'
        GROUP BY segment;

-- Step 24: Depth 2 (within country=NG, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news'
        GROUP BY segment;

-- Step 25: Depth 2 (within country=NG, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND category = 'news'
        GROUP BY segment;

-- Step 26: Depth 2 (within country=NG, category=news) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news'
        GROUP BY segment;

-- Step 27: Depth 3 (within country=NG, category=news, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 28: Depth 3 (within country=NG, category=news, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 29: Depth 3 (within country=NG, category=news, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 30: Depth 3 (within country=NG, category=news, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 31: Depth 3 (within country=NG, category=news, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 32: Depth 3 (within country=NG, category=news, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 33: Depth 4 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 34: Depth 4 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 35: Depth 4 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 36: Depth 4 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 37: Depth 4 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 38: Depth 5 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 39: Depth 5 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4, device_model=iPhone 14) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 40: Depth 5 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 41: Depth 5 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 42: Depth 5 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 43: Depth 5 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4, campaign_type=CPM) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 44: Depth 5 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 45: Depth 5 (within country=NG, category=news, ad_format=rewarded, os_version=iOS 16.4, campaign_type=CPM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 46: Depth 4 (within country=NG, category=news, ad_format=rewarded, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 47: Depth 4 (within country=NG, category=news, ad_format=rewarded, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 48: Depth 4 (within country=NG, category=news, ad_format=rewarded, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 49: Depth 4 (within country=NG, category=news, ad_format=rewarded, vertical=travel) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 50: Depth 4 (within country=NG, category=news, ad_format=rewarded, vertical=travel) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 51: Depth 5 (within country=NG, category=news, ad_format=rewarded, vertical=travel, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 52: Depth 5 (within country=NG, category=news, ad_format=rewarded, vertical=travel, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 53: Depth 5 (within country=NG, category=news, ad_format=rewarded, vertical=travel, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 54: Depth 5 (within country=NG, category=news, ad_format=rewarded, vertical=travel, campaign_type=CPC) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 55: Depth 5 (within country=NG, category=news, ad_format=rewarded, vertical=travel, device_model=iPhone 15) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 56: Depth 5 (within country=NG, category=news, ad_format=rewarded, vertical=travel, device_model=iPhone 15) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 57: Depth 5 (within country=NG, category=news, ad_format=rewarded, vertical=travel, device_model=iPhone 15) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 58: Depth 5 (within country=NG, category=news, ad_format=rewarded, vertical=travel, device_model=iPhone 15) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 59: Depth 3 (within country=NG, category=news, device_model=iPhone 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 60: Depth 3 (within country=NG, category=news, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 61: Depth 3 (within country=NG, category=news, device_model=iPhone 14) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 62: Depth 3 (within country=NG, category=news, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 63: Depth 3 (within country=NG, category=news, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 64: Depth 3 (within country=NG, category=news, device_model=iPhone 14) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 65: Depth 4 (within country=NG, category=news, device_model=iPhone 14, vertical=travel) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel'
        GROUP BY segment;

-- Step 66: Depth 4 (within country=NG, category=news, device_model=iPhone 14, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel'
        GROUP BY segment;

-- Step 67: Depth 4 (within country=NG, category=news, device_model=iPhone 14, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel'
        GROUP BY segment;

-- Step 68: Depth 4 (within country=NG, category=news, device_model=iPhone 14, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel'
        GROUP BY segment;

-- Step 69: Depth 4 (within country=NG, category=news, device_model=iPhone 14, vertical=travel) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel'
        GROUP BY segment;

-- Step 70: Depth 5 (within country=NG, category=news, device_model=iPhone 14, vertical=travel, campaign_type=CPM) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 71: Depth 5 (within country=NG, category=news, device_model=iPhone 14, vertical=travel, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 72: Depth 5 (within country=NG, category=news, device_model=iPhone 14, vertical=travel, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 73: Depth 5 (within country=NG, category=news, device_model=iPhone 14, vertical=travel, campaign_type=CPM) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND vertical = 'travel' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 74: Depth 4 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 75: Depth 4 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 76: Depth 4 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 77: Depth 4 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 78: Depth 4 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 79: Depth 5 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 80: Depth 5 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 81: Depth 5 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 82: Depth 5 (within country=NG, category=news, device_model=iPhone 14, ad_format=rewarded, os_version=iOS 16.4) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND category = 'news' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND os_version = 'iOS 16.4'
        GROUP BY segment;

-- Step 83: Depth 2 (within country=NG, os_version=iOS 18.1) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 84: Depth 2 (within country=NG, os_version=iOS 18.1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 85: Depth 2 (within country=NG, os_version=iOS 18.1) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 86: Depth 2 (within country=NG, os_version=iOS 18.1) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 87: Depth 2 (within country=NG, os_version=iOS 18.1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 88: Depth 2 (within country=NG, os_version=iOS 18.1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 89: Depth 2 (within country=NG, os_version=iOS 18.1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 90: Depth 3 (within country=NG, os_version=iOS 18.1, category=social) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social'
        GROUP BY segment;

-- Step 91: Depth 3 (within country=NG, os_version=iOS 18.1, category=social) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social'
        GROUP BY segment;

-- Step 92: Depth 3 (within country=NG, os_version=iOS 18.1, category=social) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social'
        GROUP BY segment;

-- Step 93: Depth 3 (within country=NG, os_version=iOS 18.1, category=social) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social'
        GROUP BY segment;

-- Step 94: Depth 3 (within country=NG, os_version=iOS 18.1, category=social) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social'
        GROUP BY segment;

-- Step 95: Depth 3 (within country=NG, os_version=iOS 18.1, category=social) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social'
        GROUP BY segment;

-- Step 96: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 97: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 98: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 99: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 100: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 101: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 102: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 103: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 104: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 105: Depth 4 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 106: Depth 5 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce, publisher_tier=tier_1) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 107: Depth 5 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 108: Depth 5 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 109: Depth 5 (within country=NG, os_version=iOS 18.1, category=social, vertical=ecommerce, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND category = 'social' AND vertical = 'ecommerce' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 110: Depth 3 (within country=NG, os_version=iOS 18.1, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 111: Depth 3 (within country=NG, os_version=iOS 18.1, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 112: Depth 3 (within country=NG, os_version=iOS 18.1, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 113: Depth 3 (within country=NG, os_version=iOS 18.1, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 114: Depth 3 (within country=NG, os_version=iOS 18.1, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 115: Depth 3 (within country=NG, os_version=iOS 18.1, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 116: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, vertical=ecommerce) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 117: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, vertical=ecommerce) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 118: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, vertical=ecommerce) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 119: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, vertical=ecommerce) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 120: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, vertical=ecommerce) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND vertical = 'ecommerce'
        GROUP BY segment;

-- Step 121: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, category=social) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND category = 'social'
        GROUP BY segment;

-- Step 122: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, category=social) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND category = 'social'
        GROUP BY segment;

-- Step 123: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, category=social) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND category = 'social'
        GROUP BY segment;

-- Step 124: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, category=social) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND category = 'social'
        GROUP BY segment;

-- Step 125: Depth 4 (within country=NG, os_version=iOS 18.1, ad_format=rewarded, category=social) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 18.1' AND ad_format = 'rewarded' AND category = 'social'
        GROUP BY segment;

-- Step 126: Depth 1 (within vertical=entertainment) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 127: Depth 1 (within vertical=entertainment) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 128: Depth 1 (within vertical=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 129: Depth 1 (within vertical=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 130: Depth 1 (within vertical=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 131: Depth 1 (within vertical=entertainment) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 132: Depth 1 (within vertical=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 133: Depth 1 (within vertical=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 134: Depth 2 (within vertical=entertainment, category=finance) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND category = 'finance'
        GROUP BY segment;

-- Step 135: Depth 2 (within vertical=entertainment, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance'
        GROUP BY segment;

-- Step 136: Depth 2 (within vertical=entertainment, category=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance'
        GROUP BY segment;

-- Step 137: Depth 2 (within vertical=entertainment, category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance'
        GROUP BY segment;

-- Step 138: Depth 2 (within vertical=entertainment, category=finance) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND category = 'finance'
        GROUP BY segment;

-- Step 139: Depth 2 (within vertical=entertainment, category=finance) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance'
        GROUP BY segment;

-- Step 140: Depth 2 (within vertical=entertainment, category=finance) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'entertainment' AND category = 'finance'
        GROUP BY segment;

-- Step 141: Depth 3 (within vertical=entertainment, category=finance, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 142: Depth 3 (within vertical=entertainment, category=finance, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 143: Depth 3 (within vertical=entertainment, category=finance, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 144: Depth 3 (within vertical=entertainment, category=finance, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 145: Depth 3 (within vertical=entertainment, category=finance, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 146: Depth 3 (within vertical=entertainment, category=finance, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 147: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, os_version=iOS 18.1) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 148: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, os_version=iOS 18.1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 149: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, os_version=iOS 18.1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 150: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, os_version=iOS 18.1) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 151: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, os_version=iOS 18.1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 152: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 153: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 154: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 155: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 156: Depth 4 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 157: Depth 5 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK, device_model=Pixel 7) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 158: Depth 5 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK, device_model=Pixel 7) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 159: Depth 5 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK, device_model=Pixel 7) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 160: Depth 5 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK, device_model=Pixel 7) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 161: Depth 5 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 162: Depth 5 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 163: Depth 5 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 164: Depth 5 (within vertical=entertainment, category=finance, ad_format=rewarded, country=UK, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'entertainment' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'UK' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 165: Depth 3 (within vertical=entertainment, category=finance, os_version=iOS 17.5) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 166: Depth 3 (within vertical=entertainment, category=finance, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 167: Depth 3 (within vertical=entertainment, category=finance, os_version=iOS 17.5) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 168: Depth 3 (within vertical=entertainment, category=finance, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 169: Depth 3 (within vertical=entertainment, category=finance, os_version=iOS 17.5) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 170: Depth 3 (within vertical=entertainment, category=finance, os_version=iOS 17.5) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 171: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 172: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 173: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 174: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 175: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 176: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, country=AR) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 177: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, country=AR) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 178: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, country=AR) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 179: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, country=AR) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 180: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, region=LATAM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND region = 'LATAM'
        GROUP BY segment;

-- Step 181: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, region=LATAM) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND region = 'LATAM'
        GROUP BY segment;

-- Step 182: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, region=LATAM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND region = 'LATAM'
        GROUP BY segment;

-- Step 183: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, region=LATAM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND region = 'LATAM'
        GROUP BY segment;

-- Step 184: Depth 6 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, region=LATAM, country=AR) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND region = 'LATAM' AND country = 'AR'
        GROUP BY segment;

-- Step 185: Depth 6 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, region=LATAM, country=AR) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND region = 'LATAM' AND country = 'AR'
        GROUP BY segment;

-- Step 186: Depth 6 (within vertical=entertainment, category=finance, os_version=iOS 17.5, ad_format=rewarded, region=LATAM, country=AR) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND ad_format = 'rewarded' AND region = 'LATAM' AND country = 'AR'
        GROUP BY segment;

-- Step 187: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA'
        GROUP BY segment;

-- Step 188: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA'
        GROUP BY segment;

-- Step 189: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA'
        GROUP BY segment;

-- Step 190: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA'
        GROUP BY segment;

-- Step 191: Depth 4 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA'
        GROUP BY segment;

-- Step 192: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA, country=AE) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 193: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA, country=AE) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 194: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA, country=AE) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 195: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA, country=AE) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 196: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA, publisher_tier=tier_2) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 197: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA, publisher_tier=tier_2) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 198: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA, publisher_tier=tier_2) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 199: Depth 5 (within vertical=entertainment, category=finance, os_version=iOS 17.5, region=MEA, publisher_tier=tier_2) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND category = 'finance' AND os_version = 'iOS 17.5' AND region = 'MEA' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 200: Depth 2 (within vertical=entertainment, os_version=iOS 17.5) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 201: Depth 2 (within vertical=entertainment, os_version=iOS 17.5) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 202: Depth 2 (within vertical=entertainment, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 203: Depth 2 (within vertical=entertainment, os_version=iOS 17.5) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 204: Depth 2 (within vertical=entertainment, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 205: Depth 2 (within vertical=entertainment, os_version=iOS 17.5) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 206: Depth 2 (within vertical=entertainment, os_version=iOS 17.5) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 207: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, category=finance) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance'
        GROUP BY segment;

-- Step 208: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance'
        GROUP BY segment;

-- Step 209: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, category=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance'
        GROUP BY segment;

-- Step 210: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance'
        GROUP BY segment;

-- Step 211: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, category=finance) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance'
        GROUP BY segment;

-- Step 212: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, category=finance) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance'
        GROUP BY segment;

-- Step 213: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 214: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 215: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 216: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 217: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 218: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, country=AR) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 219: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, country=AR) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 220: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, country=AR) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 221: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, country=AR) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 222: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, region=LATAM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND region = 'LATAM'
        GROUP BY segment;

-- Step 223: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, region=LATAM) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND region = 'LATAM'
        GROUP BY segment;

-- Step 224: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, region=LATAM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND region = 'LATAM'
        GROUP BY segment;

-- Step 225: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, region=LATAM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND region = 'LATAM'
        GROUP BY segment;

-- Step 226: Depth 6 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, region=LATAM, country=AR) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND region = 'LATAM' AND country = 'AR'
        GROUP BY segment;

-- Step 227: Depth 6 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, region=LATAM, country=AR) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND region = 'LATAM' AND country = 'AR'
        GROUP BY segment;

-- Step 228: Depth 6 (within vertical=entertainment, os_version=iOS 17.5, category=finance, ad_format=rewarded, region=LATAM, country=AR) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND ad_format = 'rewarded' AND region = 'LATAM' AND country = 'AR'
        GROUP BY segment;

-- Step 229: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA'
        GROUP BY segment;

-- Step 230: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA'
        GROUP BY segment;

-- Step 231: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA'
        GROUP BY segment;

-- Step 232: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA'
        GROUP BY segment;

-- Step 233: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA'
        GROUP BY segment;

-- Step 234: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA, country=AE) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 235: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA, country=AE) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 236: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA, country=AE) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 237: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA, country=AE) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA' AND country = 'AE'
        GROUP BY segment;

-- Step 238: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA, publisher_tier=tier_2) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 239: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA, publisher_tier=tier_2) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 240: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA, publisher_tier=tier_2) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 241: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, category=finance, region=MEA, publisher_tier=tier_2) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND category = 'finance' AND region = 'MEA' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 242: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 243: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 244: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 245: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 246: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 247: Depth 3 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 248: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming'
        GROUP BY segment;

-- Step 249: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming'
        GROUP BY segment;

-- Step 250: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming'
        GROUP BY segment;

-- Step 251: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming'
        GROUP BY segment;

-- Step 252: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming'
        GROUP BY segment;

-- Step 253: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming, country=MX) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming' AND country = 'MX'
        GROUP BY segment;

-- Step 254: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming, country=MX) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming' AND country = 'MX'
        GROUP BY segment;

-- Step 255: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming, country=MX) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming' AND country = 'MX'
        GROUP BY segment;

-- Step 256: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming, country=MX) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming' AND country = 'MX'
        GROUP BY segment;

-- Step 257: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming, device_model=iPhone 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 258: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 259: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 260: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, category=gaming, device_model=iPhone 14) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND category = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 261: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH'
        GROUP BY segment;

-- Step 262: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH'
        GROUP BY segment;

-- Step 263: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH'
        GROUP BY segment;

-- Step 264: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH'
        GROUP BY segment;

-- Step 265: Depth 4 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH'
        GROUP BY segment;

-- Step 266: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH, ad_format=native) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH' AND ad_format = 'native'
        GROUP BY segment;

-- Step 267: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH, ad_format=native) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH' AND ad_format = 'native'
        GROUP BY segment;

-- Step 268: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH, ad_format=native) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH' AND ad_format = 'native'
        GROUP BY segment;

-- Step 269: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH, ad_format=native) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH' AND ad_format = 'native'
        GROUP BY segment;

-- Step 270: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH, device_model=iPhone 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 271: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH, device_model=iPhone 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 272: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 273: Depth 5 (within vertical=entertainment, os_version=iOS 17.5, campaign_type=CPI, country=PH, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-12') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-12') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-19') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-19') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-19'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPI' AND country = 'PH' AND device_model = 'iPhone 14'
        GROUP BY segment;
