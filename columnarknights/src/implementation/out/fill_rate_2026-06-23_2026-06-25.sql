-- Investigation: fill_rate, 2026-06-23 to 2026-06-25 (baseline: 2026-06-16 to 2026-06-18)

-- Step 1: Baseline window aggregate (2026-06-16 to 2026-06-18)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-18';

-- Step 2: Current window aggregate (2026-06-23 to 2026-06-25)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-23' AND '2026-06-25';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;

-- Step 10: Depth 1 (within os_version=Android 15) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 11: Depth 1 (within os_version=Android 15) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 12: Depth 1 (within os_version=Android 15) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 13: Depth 1 (within os_version=Android 15) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 14: Depth 1 (within os_version=Android 15) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 15: Depth 1 (within os_version=Android 15) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 16: Depth 1 (within device_model=Galaxy S23) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 17: Depth 1 (within device_model=Galaxy S23) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 18: Depth 1 (within device_model=Galaxy S23) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 19: Depth 1 (within device_model=Galaxy S23) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 20: Depth 1 (within device_model=Galaxy S23) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 21: Depth 1 (within device_model=Galaxy S23) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 22: Depth 2 (within device_model=Galaxy S23, os_version=Android 15) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND device_model = 'Galaxy S23' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 23: Depth 2 (within device_model=Galaxy S23, os_version=Android 15) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Galaxy S23' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 24: Depth 2 (within device_model=Galaxy S23, os_version=Android 15) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Galaxy S23' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 25: Depth 2 (within device_model=Galaxy S23, os_version=Android 15) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Galaxy S23' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 26: Depth 2 (within device_model=Galaxy S23, os_version=Android 15) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND device_model = 'Galaxy S23' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 27: Depth 2 (within device_model=Galaxy S23, country=UK) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND device_model = 'Galaxy S23' AND country = 'UK'
        GROUP BY segment;

-- Step 28: Depth 2 (within device_model=Galaxy S23, country=UK) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND device_model = 'Galaxy S23' AND country = 'UK'
        GROUP BY segment;

-- Step 29: Depth 2 (within device_model=Galaxy S23, country=UK) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND device_model = 'Galaxy S23' AND country = 'UK'
        GROUP BY segment;

-- Step 30: Depth 2 (within device_model=Galaxy S23, country=UK) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND device_model = 'Galaxy S23' AND country = 'UK'
        GROUP BY segment;

-- Step 31: Depth 2 (within device_model=Galaxy S23, country=UK) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-18') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-18') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-23' AND '2026-06-25') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-23' AND '2026-06-25') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-25'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND device_model = 'Galaxy S23' AND country = 'UK'
        GROUP BY segment;
