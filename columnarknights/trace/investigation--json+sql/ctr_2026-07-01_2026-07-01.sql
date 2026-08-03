-- Investigation: ctr, 2026-07-01 to 2026-07-01 (baseline: 2026-06-24 to 2026-06-24)

-- Step 1: Baseline window aggregate (2026-06-24 to 2026-06-24)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-06-24';

-- Step 2: Current window aggregate (2026-07-01 to 2026-07-01)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-07-01' AND '2026-07-01';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 10: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 11: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;

-- Step 12: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 13: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 14: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 15: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 16: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 17: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 18: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 19: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 20: Depth 2 (within ad_format=rewarded, vertical=gaming) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 21: Depth 2 (within ad_format=rewarded, vertical=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 22: Depth 2 (within ad_format=rewarded, vertical=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 23: Depth 2 (within ad_format=rewarded, vertical=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 24: Depth 2 (within ad_format=rewarded, vertical=gaming) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 25: Depth 2 (within ad_format=rewarded, vertical=gaming) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 26: Depth 2 (within ad_format=rewarded, vertical=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 27: Depth 3 (within ad_format=rewarded, vertical=gaming, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 28: Depth 3 (within ad_format=rewarded, vertical=gaming, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 29: Depth 3 (within ad_format=rewarded, vertical=gaming, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 30: Depth 3 (within ad_format=rewarded, vertical=gaming, category=news) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 31: Depth 3 (within ad_format=rewarded, vertical=gaming, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 32: Depth 3 (within ad_format=rewarded, vertical=gaming, category=news) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 33: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 34: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 35: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 36: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 37: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 38: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 39: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 40: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7, publisher_tier=tier_1) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 41: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 42: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7, region=NAM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7' AND region = 'NAM'
        GROUP BY segment;

-- Step 43: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7, region=NAM) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7' AND region = 'NAM'
        GROUP BY segment;

-- Step 44: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7, region=NAM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7' AND region = 'NAM'
        GROUP BY segment;

-- Step 45: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, device_model=Pixel 7, region=NAM) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND device_model = 'Pixel 7' AND region = 'NAM'
        GROUP BY segment;

-- Step 46: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, country=IN) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN'
        GROUP BY segment;

-- Step 47: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, country=IN) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN'
        GROUP BY segment;

-- Step 48: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, country=IN) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN'
        GROUP BY segment;

-- Step 49: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, country=IN) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN'
        GROUP BY segment;

-- Step 50: Depth 4 (within ad_format=rewarded, vertical=gaming, category=news, country=IN) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN'
        GROUP BY segment;

-- Step 51: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 52: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 53: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 54: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 55: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14, publisher_tier=tier_3) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 56: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14, publisher_tier=tier_3) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 57: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14, publisher_tier=tier_3) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 58: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14, campaign_type=CPI) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 59: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 60: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, device_model=iPhone 14, campaign_type=CPI) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND device_model = 'iPhone 14' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 61: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 62: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 63: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 64: Depth 5 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 65: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1, publisher_tier=tier_3) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 66: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1, publisher_tier=tier_3) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 67: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1, publisher_tier=tier_3) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 68: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1, campaign_type=CPI) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 69: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 70: Depth 6 (within ad_format=rewarded, vertical=gaming, category=news, country=IN, os_version=iOS 18.1, campaign_type=CPI) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND category = 'news' AND country = 'IN' AND os_version = 'iOS 18.1' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 71: Depth 3 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 72: Depth 3 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 73: Depth 3 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 74: Depth 3 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 75: Depth 3 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 76: Depth 3 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 77: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA'
        GROUP BY segment;

-- Step 78: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA'
        GROUP BY segment;

-- Step 79: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA'
        GROUP BY segment;

-- Step 80: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA'
        GROUP BY segment;

-- Step 81: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA'
        GROUP BY segment;

-- Step 82: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 83: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 84: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 85: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 86: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 87: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 88: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12, publisher_tier=tier_1) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 89: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 90: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 91: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, os_version=Android 12, campaign_type=CPM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND os_version = 'Android 12' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 92: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, campaign_type=CPM) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 93: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 94: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, campaign_type=CPM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 95: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, campaign_type=CPM) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 96: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, campaign_type=CPM, os_version=Android 12) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND campaign_type = 'CPM' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 97: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, campaign_type=CPM, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND campaign_type = 'CPM' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 98: Depth 6 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, region=MEA, campaign_type=CPM, os_version=Android 12) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND region = 'MEA' AND campaign_type = 'CPM' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 99: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility'
        GROUP BY segment;

-- Step 100: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility'
        GROUP BY segment;

-- Step 101: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility'
        GROUP BY segment;

-- Step 102: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility'
        GROUP BY segment;

-- Step 103: Depth 4 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility'
        GROUP BY segment;

-- Step 104: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility, campaign_type=CPI) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 105: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 106: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility, campaign_type=CPI) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 107: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility, campaign_type=CPI) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 108: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility, country=ID) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility' AND country = 'ID'
        GROUP BY segment;

-- Step 109: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility, country=ID) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility' AND country = 'ID'
        GROUP BY segment;

-- Step 110: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility, country=ID) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility' AND country = 'ID'
        GROUP BY segment;

-- Step 111: Depth 5 (within ad_format=rewarded, vertical=gaming, device_model=Redmi Note 12, category=utility, country=ID) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'gaming' AND device_model = 'Redmi Note 12' AND category = 'utility' AND country = 'ID'
        GROUP BY segment;

-- Step 112: Depth 2 (within ad_format=rewarded, device_model=Pixel 7) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 113: Depth 2 (within ad_format=rewarded, device_model=Pixel 7) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 114: Depth 2 (within ad_format=rewarded, device_model=Pixel 7) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 115: Depth 2 (within ad_format=rewarded, device_model=Pixel 7) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 116: Depth 2 (within ad_format=rewarded, device_model=Pixel 7) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 117: Depth 2 (within ad_format=rewarded, device_model=Pixel 7) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 118: Depth 2 (within ad_format=rewarded, device_model=Pixel 7) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 119: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, country=DE) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE'
        GROUP BY segment;

-- Step 120: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, country=DE) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE'
        GROUP BY segment;

-- Step 121: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, country=DE) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE'
        GROUP BY segment;

-- Step 122: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, country=DE) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE'
        GROUP BY segment;

-- Step 123: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, country=DE) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE'
        GROUP BY segment;

-- Step 124: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, country=DE) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE'
        GROUP BY segment;

-- Step 125: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news'
        GROUP BY segment;

-- Step 126: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news'
        GROUP BY segment;

-- Step 127: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news'
        GROUP BY segment;

-- Step 128: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news'
        GROUP BY segment;

-- Step 129: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news'
        GROUP BY segment;

-- Step 130: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 131: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news, os_version=Android 12) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 132: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 133: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news, os_version=Android 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 134: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news, vertical=cpg) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 135: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 136: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news, vertical=cpg) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 137: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, category=news, vertical=cpg) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND category = 'news' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 138: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance'
        GROUP BY segment;

-- Step 139: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance'
        GROUP BY segment;

-- Step 140: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance'
        GROUP BY segment;

-- Step 141: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance'
        GROUP BY segment;

-- Step 142: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance'
        GROUP BY segment;

-- Step 143: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance' AND category = 'finance'
        GROUP BY segment;

-- Step 144: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance, category=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance' AND category = 'finance'
        GROUP BY segment;

-- Step 145: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance, category=finance) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance' AND category = 'finance'
        GROUP BY segment;

-- Step 146: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance, category=finance) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance' AND category = 'finance'
        GROUP BY segment;

-- Step 147: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance, os_version=Android 13) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 148: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance, os_version=Android 13) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 149: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance, os_version=Android 13) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 150: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, country=DE, vertical=finance, os_version=Android 13) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND country = 'DE' AND vertical = 'finance' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 151: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 152: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 153: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 154: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 155: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 156: Depth 3 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 157: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 158: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 159: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 160: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 161: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news'
        GROUP BY segment;

-- Step 162: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 163: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 164: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news, publisher_tier=tier_1) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 165: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 166: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news, region=NAM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news' AND region = 'NAM'
        GROUP BY segment;

-- Step 167: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news, region=NAM) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news' AND region = 'NAM'
        GROUP BY segment;

-- Step 168: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news, region=NAM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news' AND region = 'NAM'
        GROUP BY segment;

-- Step 169: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, category=news, region=NAM) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'news' AND region = 'NAM'
        GROUP BY segment;

-- Step 170: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 171: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 172: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 173: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 174: Depth 4 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 175: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 176: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 177: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 178: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, category=news) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 179: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 180: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 181: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 182: Depth 5 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 183: Depth 6 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 184: Depth 6 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 185: Depth 6 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1, category=news) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1' AND category = 'news'
        GROUP BY segment;

-- Step 186: Depth 6 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1, campaign_type=CPC) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 187: Depth 6 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 188: Depth 6 (within ad_format=rewarded, device_model=Pixel 7, vertical=gaming, country=CA, publisher_tier=tier_1, campaign_type=CPC) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 189: Depth 1 (within os_version=Android 13) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 190: Depth 1 (within os_version=Android 13) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 191: Depth 1 (within os_version=Android 13) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 192: Depth 1 (within os_version=Android 13) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 193: Depth 1 (within os_version=Android 13) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 194: Depth 1 (within os_version=Android 13) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 195: Depth 1 (within os_version=Android 13) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 196: Depth 1 (within os_version=Android 13) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 197: Depth 2 (within os_version=Android 13, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 198: Depth 2 (within os_version=Android 13, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 199: Depth 2 (within os_version=Android 13, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 200: Depth 2 (within os_version=Android 13, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 201: Depth 2 (within os_version=Android 13, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 202: Depth 2 (within os_version=Android 13, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 203: Depth 2 (within os_version=Android 13, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 204: Depth 3 (within os_version=Android 13, ad_format=rewarded, country=UK) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 205: Depth 3 (within os_version=Android 13, ad_format=rewarded, country=UK) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 206: Depth 3 (within os_version=Android 13, ad_format=rewarded, country=UK) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 207: Depth 3 (within os_version=Android 13, ad_format=rewarded, country=UK) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 208: Depth 3 (within os_version=Android 13, ad_format=rewarded, country=UK) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 209: Depth 3 (within os_version=Android 13, ad_format=rewarded, country=UK) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK'
        GROUP BY segment;

-- Step 210: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, device_model=Redmi Note 12) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 211: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, device_model=Redmi Note 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 212: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, device_model=Redmi Note 12) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 213: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, device_model=Redmi Note 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 214: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, device_model=Redmi Note 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 215: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, vertical=cpg) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 216: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, vertical=cpg) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 217: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 218: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, vertical=cpg) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 219: Depth 4 (within os_version=Android 13, ad_format=rewarded, country=UK, vertical=cpg) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND country = 'UK' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 220: Depth 3 (within os_version=Android 13, ad_format=rewarded, vertical=gaming) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 221: Depth 3 (within os_version=Android 13, ad_format=rewarded, vertical=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 222: Depth 3 (within os_version=Android 13, ad_format=rewarded, vertical=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 223: Depth 3 (within os_version=Android 13, ad_format=rewarded, vertical=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 224: Depth 3 (within os_version=Android 13, ad_format=rewarded, vertical=gaming) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 225: Depth 3 (within os_version=Android 13, ad_format=rewarded, vertical=gaming) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 226: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 227: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 228: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 229: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 230: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA'
        GROUP BY segment;

-- Step 231: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 232: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 233: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 234: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 235: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 236: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 237: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 238: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 239: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 240: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 241: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 242: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 243: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 244: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, country=CA, category=news, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND country = 'CA' AND category = 'news' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 245: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM'
        GROUP BY segment;

-- Step 246: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM'
        GROUP BY segment;

-- Step 247: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM'
        GROUP BY segment;

-- Step 248: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM'
        GROUP BY segment;

-- Step 249: Depth 4 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM'
        GROUP BY segment;

-- Step 250: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news'
        GROUP BY segment;

-- Step 251: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news'
        GROUP BY segment;

-- Step 252: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news'
        GROUP BY segment;

-- Step 253: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news'
        GROUP BY segment;

-- Step 254: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 255: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news, campaign_type=CPC) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 256: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 257: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news, device_model=Pixel 7) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 258: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news, device_model=Pixel 7) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 259: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, category=news, device_model=Pixel 7) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND category = 'news' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 260: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA'
        GROUP BY segment;

-- Step 261: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA'
        GROUP BY segment;

-- Step 262: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA'
        GROUP BY segment;

-- Step 263: Depth 5 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA'
        GROUP BY segment;

-- Step 264: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 265: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 266: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 267: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 268: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 269: Depth 6 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND category = 'news'
        GROUP BY segment;

-- Step 270: Depth 7 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, category=news, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 271: Depth 7 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, category=news, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND category = 'news' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 272: Depth 7 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, category=news, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND category = 'news' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 273: Depth 7 (within os_version=Android 13, ad_format=rewarded, vertical=gaming, region=NAM, country=CA, category=news, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND ad_format = 'rewarded' AND vertical = 'gaming' AND region = 'NAM' AND country = 'CA' AND category = 'news' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 274: Depth 2 (within os_version=Android 13, region=LATAM) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM'
        GROUP BY segment;

-- Step 275: Depth 2 (within os_version=Android 13, region=LATAM) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM'
        GROUP BY segment;

-- Step 276: Depth 2 (within os_version=Android 13, region=LATAM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM'
        GROUP BY segment;

-- Step 277: Depth 2 (within os_version=Android 13, region=LATAM) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13' AND region = 'LATAM'
        GROUP BY segment;

-- Step 278: Depth 2 (within os_version=Android 13, region=LATAM) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM'
        GROUP BY segment;

-- Step 279: Depth 2 (within os_version=Android 13, region=LATAM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM'
        GROUP BY segment;

-- Step 280: Depth 2 (within os_version=Android 13, region=LATAM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM'
        GROUP BY segment;

-- Step 281: Depth 3 (within os_version=Android 13, region=LATAM, vertical=cpg) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 282: Depth 3 (within os_version=Android 13, region=LATAM, vertical=cpg) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 283: Depth 3 (within os_version=Android 13, region=LATAM, vertical=cpg) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 284: Depth 3 (within os_version=Android 13, region=LATAM, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 285: Depth 3 (within os_version=Android 13, region=LATAM, vertical=cpg) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 286: Depth 3 (within os_version=Android 13, region=LATAM, vertical=cpg) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 287: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance'
        GROUP BY segment;

-- Step 288: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance'
        GROUP BY segment;

-- Step 289: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance'
        GROUP BY segment;

-- Step 290: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance'
        GROUP BY segment;

-- Step 291: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance'
        GROUP BY segment;

-- Step 292: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, ad_format=banner) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 293: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, ad_format=banner) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 294: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, ad_format=banner) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 295: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, ad_format=banner) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 296: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, ad_format=banner, device_model=Galaxy S23) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND ad_format = 'banner' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 297: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, ad_format=banner, device_model=Galaxy S23) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND ad_format = 'banner' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 298: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, ad_format=banner, device_model=Galaxy S23) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND ad_format = 'banner' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 299: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 300: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 301: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 302: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 303: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, ad_format=banner) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 304: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, ad_format=banner) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 305: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, ad_format=banner) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 306: Depth 7 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, ad_format=banner, device_model=Galaxy S23) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND ad_format = 'banner' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 307: Depth 7 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, ad_format=banner, device_model=Galaxy S23) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND ad_format = 'banner' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 308: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, device_model=Galaxy S23) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 309: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, device_model=Galaxy S23) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 310: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, device_model=Galaxy S23) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 311: Depth 7 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, device_model=Galaxy S23, ad_format=banner) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND device_model = 'Galaxy S23' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 312: Depth 7 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, device_model=Galaxy S23, ad_format=banner) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND device_model = 'Galaxy S23' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 313: Depth 7 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, device_model=Galaxy S23, campaign_type=CPI) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND device_model = 'Galaxy S23' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 314: Depth 7 (within os_version=Android 13, region=LATAM, vertical=cpg, category=finance, publisher_tier=tier_3, device_model=Galaxy S23, campaign_type=CPI) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND category = 'finance' AND publisher_tier = 'tier_3' AND device_model = 'Galaxy S23' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 315: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 316: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 317: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 318: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 319: Depth 4 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23'
        GROUP BY segment;

-- Step 320: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 321: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 322: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 323: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 324: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, ad_format=rewarded, category=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 325: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, ad_format=rewarded, category=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 326: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, ad_format=rewarded, category=gaming) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 327: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, category=social) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND category = 'social'
        GROUP BY segment;

-- Step 328: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, category=social) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND category = 'social'
        GROUP BY segment;

-- Step 329: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, category=social) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND category = 'social'
        GROUP BY segment;

-- Step 330: Depth 5 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, category=social) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND category = 'social'
        GROUP BY segment;

-- Step 331: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, category=social, publisher_tier=tier_2) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND category = 'social' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 332: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, category=social, publisher_tier=tier_2) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND category = 'social' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 333: Depth 6 (within os_version=Android 13, region=LATAM, vertical=cpg, device_model=Galaxy S23, category=social, publisher_tier=tier_2) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND vertical = 'cpg' AND device_model = 'Galaxy S23' AND category = 'social' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 334: Depth 3 (within os_version=Android 13, region=LATAM, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 335: Depth 3 (within os_version=Android 13, region=LATAM, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 336: Depth 3 (within os_version=Android 13, region=LATAM, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 337: Depth 3 (within os_version=Android 13, region=LATAM, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 338: Depth 3 (within os_version=Android 13, region=LATAM, ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 339: Depth 3 (within os_version=Android 13, region=LATAM, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 340: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 341: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 342: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 343: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 344: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 345: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 346: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 347: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 348: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 349: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54, category=ecommerce) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 350: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54, category=ecommerce) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 351: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54, category=ecommerce) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 352: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54, campaign_type=CPC) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 353: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 354: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, device_model=Galaxy A54, campaign_type=CPC) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND device_model = 'Galaxy A54' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 355: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 356: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 357: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 358: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 359: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC, category=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC' AND category = 'entertainment'
        GROUP BY segment;

-- Step 360: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC, category=entertainment) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC' AND category = 'entertainment'
        GROUP BY segment;

-- Step 361: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC, category=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC' AND category = 'entertainment'
        GROUP BY segment;

-- Step 362: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC, publisher_tier=tier_2) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 363: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC, publisher_tier=tier_2) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 364: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, vertical=travel, campaign_type=CPC, publisher_tier=tier_2) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND vertical = 'travel' AND campaign_type = 'CPC' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 365: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX'
        GROUP BY segment;

-- Step 366: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX'
        GROUP BY segment;

-- Step 367: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX'
        GROUP BY segment;

-- Step 368: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX'
        GROUP BY segment;

-- Step 369: Depth 4 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX'
        GROUP BY segment;

-- Step 370: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, vertical=cpg) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 371: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, vertical=cpg) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 372: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 373: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, vertical=cpg) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 374: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social'
        GROUP BY segment;

-- Step 375: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social'
        GROUP BY segment;

-- Step 376: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social'
        GROUP BY segment;

-- Step 377: Depth 5 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social'
        GROUP BY segment;

-- Step 378: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, vertical=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND vertical = 'finance'
        GROUP BY segment;

-- Step 379: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, vertical=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND vertical = 'finance'
        GROUP BY segment;

-- Step 380: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, vertical=finance) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND vertical = 'finance'
        GROUP BY segment;

-- Step 381: Depth 7 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, vertical=finance, device_model=Pixel 8) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND vertical = 'finance' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 382: Depth 7 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, vertical=finance, device_model=Pixel 8) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND vertical = 'finance' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 383: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, device_model=Pixel 8) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 384: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, device_model=Pixel 8) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 385: Depth 6 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, device_model=Pixel 8) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 386: Depth 7 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, device_model=Pixel 8, vertical=finance) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND device_model = 'Pixel 8' AND vertical = 'finance'
        GROUP BY segment;

-- Step 387: Depth 7 (within os_version=Android 13, region=LATAM, ad_format=rewarded, country=MX, category=social, device_model=Pixel 8, vertical=finance) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-24' AND '2026-06-24') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-24' AND '2026-06-24') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-01' AND '2026-07-01') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-01' AND '2026-07-01') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-24' AND '2026-07-01'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND os_version = 'Android 13' AND region = 'LATAM' AND ad_format = 'rewarded' AND country = 'MX' AND category = 'social' AND device_model = 'Pixel 8' AND vertical = 'finance'
        GROUP BY segment;
