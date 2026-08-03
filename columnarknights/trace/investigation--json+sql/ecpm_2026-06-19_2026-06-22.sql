-- Investigation: ecpm, 2026-06-19 to 2026-06-22 (baseline: 2026-06-12 to 2026-06-15)

-- Step 1: Baseline window aggregate (2026-06-12 to 2026-06-15)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-15';

-- Step 2: Current window aggregate (2026-06-19 to 2026-06-22)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-19' AND '2026-06-22';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 10: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 11: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;

-- Step 12: Depth 1 (within category=finance) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND category = 'finance'
        GROUP BY segment;

-- Step 13: Depth 1 (within category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND category = 'finance'
        GROUP BY segment;

-- Step 14: Depth 1 (within category=finance) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND category = 'finance'
        GROUP BY segment;

-- Step 15: Depth 1 (within category=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND category = 'finance'
        GROUP BY segment;

-- Step 16: Depth 1 (within category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND category = 'finance'
        GROUP BY segment;

-- Step 17: Depth 1 (within category=finance) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND category = 'finance'
        GROUP BY segment;

-- Step 18: Depth 1 (within category=finance) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND category = 'finance'
        GROUP BY segment;

-- Step 19: Depth 1 (within category=finance) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND category = 'finance'
        GROUP BY segment;

-- Step 20: Depth 2 (within category=finance, ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 21: Depth 2 (within category=finance, ad_format=video) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 22: Depth 2 (within category=finance, ad_format=video) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 23: Depth 2 (within category=finance, ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 24: Depth 2 (within category=finance, ad_format=video) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 25: Depth 2 (within category=finance, ad_format=video) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 26: Depth 2 (within category=finance, ad_format=video) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND category = 'finance' AND ad_format = 'video'
        GROUP BY segment;

-- Step 27: Depth 1 (within ad_format=video) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'video'
        GROUP BY segment;

-- Step 28: Depth 1 (within ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'video'
        GROUP BY segment;

-- Step 29: Depth 1 (within ad_format=video) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'video'
        GROUP BY segment;

-- Step 30: Depth 1 (within ad_format=video) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'video'
        GROUP BY segment;

-- Step 31: Depth 1 (within ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'video'
        GROUP BY segment;

-- Step 32: Depth 1 (within ad_format=video) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'video'
        GROUP BY segment;

-- Step 33: Depth 1 (within ad_format=video) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'video'
        GROUP BY segment;

-- Step 34: Depth 1 (within ad_format=video) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'video'
        GROUP BY segment;

-- Step 35: Depth 2 (within ad_format=video, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 36: Depth 2 (within ad_format=video, category=finance) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 37: Depth 2 (within ad_format=video, category=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 38: Depth 2 (within ad_format=video, category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 39: Depth 2 (within ad_format=video, category=finance) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 40: Depth 2 (within ad_format=video, category=finance) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 41: Depth 2 (within ad_format=video, category=finance) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'video' AND category = 'finance'
        GROUP BY segment;

-- Step 42: Depth 2 (within ad_format=video, country=CA) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'video' AND country = 'CA'
        GROUP BY segment;

-- Step 43: Depth 2 (within ad_format=video, country=CA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'video' AND country = 'CA'
        GROUP BY segment;

-- Step 44: Depth 2 (within ad_format=video, country=CA) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'video' AND country = 'CA'
        GROUP BY segment;

-- Step 45: Depth 2 (within ad_format=video, country=CA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'video' AND country = 'CA'
        GROUP BY segment;

-- Step 46: Depth 2 (within ad_format=video, country=CA) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'video' AND country = 'CA'
        GROUP BY segment;

-- Step 47: Depth 2 (within ad_format=video, country=CA) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'video' AND country = 'CA'
        GROUP BY segment;

-- Step 48: Depth 2 (within ad_format=video, country=CA) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'video' AND country = 'CA'
        GROUP BY segment;

-- Step 49: Depth 3 (within ad_format=video, country=CA, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'video' AND country = 'CA' AND category = 'finance'
        GROUP BY segment;

-- Step 50: Depth 3 (within ad_format=video, country=CA, category=finance) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'video' AND country = 'CA' AND category = 'finance'
        GROUP BY segment;

-- Step 51: Depth 3 (within ad_format=video, country=CA, category=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'video' AND country = 'CA' AND category = 'finance'
        GROUP BY segment;

-- Step 52: Depth 3 (within ad_format=video, country=CA, category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'video' AND country = 'CA' AND category = 'finance'
        GROUP BY segment;

-- Step 53: Depth 3 (within ad_format=video, country=CA, category=finance) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'video' AND country = 'CA' AND category = 'finance'
        GROUP BY segment;

-- Step 54: Depth 3 (within ad_format=video, country=CA, category=finance) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-12' AND '2026-06-15') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-12' AND '2026-06-15') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-19' AND '2026-06-22') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-19' AND '2026-06-22') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-12' AND '2026-06-22'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'video' AND country = 'CA' AND category = 'finance'
        GROUP BY segment;
