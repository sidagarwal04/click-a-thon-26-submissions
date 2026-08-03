-- Investigation: ctr, 2026-06-22 to 2026-06-23 (baseline: 2026-06-15 to 2026-06-16)

-- Step 1: Baseline window aggregate (2026-06-15 to 2026-06-16)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-16';

-- Step 2: Current window aggregate (2026-06-22 to 2026-06-23)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-22' AND '2026-06-23';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 10: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 11: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;

-- Step 12: Depth 1 (within country=NG) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
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
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
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
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
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
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
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
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
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
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
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
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
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
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG'
        GROUP BY segment;

-- Step 20: Depth 2 (within country=NG, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 21: Depth 2 (within country=NG, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 22: Depth 2 (within country=NG, ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 23: Depth 2 (within country=NG, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 24: Depth 2 (within country=NG, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 25: Depth 2 (within country=NG, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 26: Depth 2 (within country=NG, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 27: Depth 3 (within country=NG, ad_format=rewarded, vertical=travel) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 28: Depth 3 (within country=NG, ad_format=rewarded, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 29: Depth 3 (within country=NG, ad_format=rewarded, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 30: Depth 3 (within country=NG, ad_format=rewarded, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 31: Depth 3 (within country=NG, ad_format=rewarded, vertical=travel) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 32: Depth 3 (within country=NG, ad_format=rewarded, vertical=travel) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel'
        GROUP BY segment;

-- Step 33: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 34: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 35: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 36: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 37: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 38: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5, category=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5' AND category = 'entertainment'
        GROUP BY segment;

-- Step 39: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5, category=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5' AND category = 'entertainment'
        GROUP BY segment;

-- Step 40: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5, category=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5' AND category = 'entertainment'
        GROUP BY segment;

-- Step 41: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5, category=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5' AND category = 'entertainment'
        GROUP BY segment;

-- Step 42: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5, device_model=iPhone 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 43: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 44: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 45: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, os_version=iOS 17.5, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND os_version = 'iOS 17.5' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 46: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, category=social) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social'
        GROUP BY segment;

-- Step 47: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, category=social) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social'
        GROUP BY segment;

-- Step 48: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, category=social) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social'
        GROUP BY segment;

-- Step 49: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, category=social) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social'
        GROUP BY segment;

-- Step 50: Depth 4 (within country=NG, ad_format=rewarded, vertical=travel, category=social) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social'
        GROUP BY segment;

-- Step 51: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, category=social, device_model=iPhone 13) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND device_model = 'iPhone 13'
        GROUP BY segment;

-- Step 52: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, category=social, device_model=iPhone 13) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND device_model = 'iPhone 13'
        GROUP BY segment;

-- Step 53: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, category=social, device_model=iPhone 13) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND device_model = 'iPhone 13'
        GROUP BY segment;

-- Step 54: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, category=social, device_model=iPhone 13) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND device_model = 'iPhone 13'
        GROUP BY segment;

-- Step 55: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 56: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 57: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 58: Depth 5 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 59: Depth 6 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 60: Depth 6 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3, campaign_type=CPI) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 61: Depth 6 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3, campaign_type=CPI) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 62: Depth 7 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3, campaign_type=CPI, device_model=Pixel 7) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 63: Depth 7 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3, campaign_type=CPI, device_model=Pixel 7) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 64: Depth 7 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3, campaign_type=CPI, os_version=Android 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 65: Depth 7 (within country=NG, ad_format=rewarded, vertical=travel, category=social, publisher_tier=tier_3, campaign_type=CPI, os_version=Android 14) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND vertical = 'travel' AND category = 'social' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 66: Depth 3 (within country=NG, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 67: Depth 3 (within country=NG, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 68: Depth 3 (within country=NG, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 69: Depth 3 (within country=NG, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 70: Depth 3 (within country=NG, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 71: Depth 3 (within country=NG, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 72: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 73: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 74: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 75: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 76: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 77: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 78: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 79: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 80: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 81: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5, campaign_type=CPC) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 82: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5, campaign_type=CPC) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 83: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 84: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, os_version=iOS 17.5, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND os_version = 'iOS 17.5' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 85: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 86: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 87: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 88: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 89: Depth 4 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 90: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, os_version=Android 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 91: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, os_version=Android 14) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 92: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, os_version=Android 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 93: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, os_version=Android 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 94: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment'
        GROUP BY segment;

-- Step 95: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment'
        GROUP BY segment;

-- Step 96: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment'
        GROUP BY segment;

-- Step 97: Depth 5 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment'
        GROUP BY segment;

-- Step 98: Depth 6 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, campaign_type=CPI) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 99: Depth 6 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 100: Depth 6 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, campaign_type=CPI) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 101: Depth 7 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, campaign_type=CPI, os_version=Android 12) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND campaign_type = 'CPI' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 102: Depth 7 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, campaign_type=CPI, os_version=Android 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND campaign_type = 'CPI' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 103: Depth 6 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, os_version=Android 12) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 104: Depth 6 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 105: Depth 6 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, os_version=Android 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 106: Depth 7 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, os_version=Android 12, campaign_type=CPI) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND os_version = 'Android 12' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 107: Depth 7 (within country=NG, ad_format=rewarded, publisher_tier=tier_1, device_model=Galaxy A54, category=entertainment, os_version=Android 12, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1' AND device_model = 'Galaxy A54' AND category = 'entertainment' AND os_version = 'Android 12' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 108: Depth 2 (within country=NG, os_version=iOS 17.5) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 109: Depth 2 (within country=NG, os_version=iOS 17.5) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 110: Depth 2 (within country=NG, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 111: Depth 2 (within country=NG, os_version=iOS 17.5) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 112: Depth 2 (within country=NG, os_version=iOS 17.5) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 113: Depth 2 (within country=NG, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 114: Depth 2 (within country=NG, os_version=iOS 17.5) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 115: Depth 3 (within country=NG, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 116: Depth 3 (within country=NG, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 117: Depth 3 (within country=NG, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 118: Depth 3 (within country=NG, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 119: Depth 3 (within country=NG, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 120: Depth 3 (within country=NG, os_version=iOS 17.5, vertical=travel) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel'
        GROUP BY segment;

-- Step 121: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 122: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 123: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 124: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 125: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 126: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded' AND category = 'utility'
        GROUP BY segment;

-- Step 127: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded' AND category = 'utility'
        GROUP BY segment;

-- Step 128: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded' AND category = 'utility'
        GROUP BY segment;

-- Step 129: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded, category=utility) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded' AND category = 'utility'
        GROUP BY segment;

-- Step 130: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded, device_model=iPhone 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 131: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 132: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 133: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, ad_format=rewarded, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND ad_format = 'rewarded' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 134: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility'
        GROUP BY segment;

-- Step 135: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility'
        GROUP BY segment;

-- Step 136: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility'
        GROUP BY segment;

-- Step 137: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility'
        GROUP BY segment;

-- Step 138: Depth 4 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility'
        GROUP BY segment;

-- Step 139: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 140: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 141: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 142: Depth 5 (within country=NG, os_version=iOS 17.5, vertical=travel, category=utility, ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND vertical = 'travel' AND category = 'utility' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 143: Depth 3 (within country=NG, os_version=iOS 17.5, category=social) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social'
        GROUP BY segment;

-- Step 144: Depth 3 (within country=NG, os_version=iOS 17.5, category=social) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social'
        GROUP BY segment;

-- Step 145: Depth 3 (within country=NG, os_version=iOS 17.5, category=social) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social'
        GROUP BY segment;

-- Step 146: Depth 3 (within country=NG, os_version=iOS 17.5, category=social) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social'
        GROUP BY segment;

-- Step 147: Depth 3 (within country=NG, os_version=iOS 17.5, category=social) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social'
        GROUP BY segment;

-- Step 148: Depth 3 (within country=NG, os_version=iOS 17.5, category=social) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social'
        GROUP BY segment;

-- Step 149: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial'
        GROUP BY segment;

-- Step 150: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial'
        GROUP BY segment;

-- Step 151: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial'
        GROUP BY segment;

-- Step 152: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial'
        GROUP BY segment;

-- Step 153: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial'
        GROUP BY segment;

-- Step 154: Depth 5 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial, vertical=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 155: Depth 5 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial, vertical=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 156: Depth 5 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial, vertical=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 157: Depth 5 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial, vertical=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 158: Depth 6 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial, vertical=entertainment, publisher_tier=tier_3) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial' AND vertical = 'entertainment' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 159: Depth 6 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial, vertical=entertainment, publisher_tier=tier_3) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial' AND vertical = 'entertainment' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 160: Depth 6 (within country=NG, os_version=iOS 17.5, category=social, ad_format=interstitial, vertical=entertainment, publisher_tier=tier_3) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND ad_format = 'interstitial' AND vertical = 'entertainment' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 161: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel'
        GROUP BY segment;

-- Step 162: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel'
        GROUP BY segment;

-- Step 163: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel'
        GROUP BY segment;

-- Step 164: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel'
        GROUP BY segment;

-- Step 165: Depth 4 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel'
        GROUP BY segment;

-- Step 166: Depth 5 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel, publisher_tier=tier_1) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 167: Depth 5 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 168: Depth 5 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 169: Depth 5 (within country=NG, os_version=iOS 17.5, category=social, vertical=travel, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'NG' AND os_version = 'iOS 17.5' AND category = 'social' AND vertical = 'travel' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 170: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 171: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 172: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 173: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 174: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 175: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 176: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 177: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 178: Depth 2 (within ad_format=rewarded, country=AR) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 179: Depth 2 (within ad_format=rewarded, country=AR) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 180: Depth 2 (within ad_format=rewarded, country=AR) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 181: Depth 2 (within ad_format=rewarded, country=AR) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 182: Depth 2 (within ad_format=rewarded, country=AR) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 183: Depth 2 (within ad_format=rewarded, country=AR) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 184: Depth 2 (within ad_format=rewarded, country=AR) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'AR'
        GROUP BY segment;

-- Step 185: Depth 3 (within ad_format=rewarded, country=AR, category=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment'
        GROUP BY segment;

-- Step 186: Depth 3 (within ad_format=rewarded, country=AR, category=entertainment) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment'
        GROUP BY segment;

-- Step 187: Depth 3 (within ad_format=rewarded, country=AR, category=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment'
        GROUP BY segment;

-- Step 188: Depth 3 (within ad_format=rewarded, country=AR, category=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment'
        GROUP BY segment;

-- Step 189: Depth 3 (within ad_format=rewarded, country=AR, category=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment'
        GROUP BY segment;

-- Step 190: Depth 3 (within ad_format=rewarded, country=AR, category=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment'
        GROUP BY segment;

-- Step 191: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 192: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 193: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 194: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 195: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 196: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 197: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5, campaign_type=CPC) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 198: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 199: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 200: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5, vertical=auto) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5' AND vertical = 'auto'
        GROUP BY segment;

-- Step 201: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5, vertical=auto) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5' AND vertical = 'auto'
        GROUP BY segment;

-- Step 202: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5, vertical=auto) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5' AND vertical = 'auto'
        GROUP BY segment;

-- Step 203: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, os_version=iOS 17.5, vertical=auto) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND os_version = 'iOS 17.5' AND vertical = 'auto'
        GROUP BY segment;

-- Step 204: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 205: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 206: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 207: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 208: Depth 4 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 209: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, vertical=auto) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND vertical = 'auto'
        GROUP BY segment;

-- Step 210: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, vertical=auto) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND vertical = 'auto'
        GROUP BY segment;

-- Step 211: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, vertical=auto) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND vertical = 'auto'
        GROUP BY segment;

-- Step 212: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, vertical=auto) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND vertical = 'auto'
        GROUP BY segment;

-- Step 213: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 214: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 215: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 216: Depth 5 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 217: Depth 6 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, campaign_type=CPC, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 218: Depth 6 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, campaign_type=CPC, os_version=iOS 17.5) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 219: Depth 6 (within ad_format=rewarded, country=AR, category=entertainment, device_model=iPhone 14, campaign_type=CPC, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND category = 'entertainment' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 220: Depth 3 (within ad_format=rewarded, country=AR, campaign_type=CPC) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 221: Depth 3 (within ad_format=rewarded, country=AR, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 222: Depth 3 (within ad_format=rewarded, country=AR, campaign_type=CPC) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 223: Depth 3 (within ad_format=rewarded, country=AR, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 224: Depth 3 (within ad_format=rewarded, country=AR, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 225: Depth 3 (within ad_format=rewarded, country=AR, campaign_type=CPC) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 226: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 227: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 228: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 229: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 230: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 231: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, publisher_tier=tier_2) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 232: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, publisher_tier=tier_2) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 233: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, publisher_tier=tier_2) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 234: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, publisher_tier=tier_2) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 235: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, vertical=entertainment) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 236: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, vertical=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 237: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, vertical=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 238: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, vertical=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND vertical = 'entertainment'
        GROUP BY segment;

-- Step 239: Depth 6 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, vertical=entertainment, publisher_tier=tier_2) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND vertical = 'entertainment' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 240: Depth 6 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, vertical=entertainment, publisher_tier=tier_2) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND vertical = 'entertainment' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 241: Depth 6 (within ad_format=rewarded, country=AR, campaign_type=CPC, os_version=Android 15, vertical=entertainment, publisher_tier=tier_2) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND os_version = 'Android 15' AND vertical = 'entertainment' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 242: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment'
        GROUP BY segment;

-- Step 243: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment'
        GROUP BY segment;

-- Step 244: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment'
        GROUP BY segment;

-- Step 245: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment'
        GROUP BY segment;

-- Step 246: Depth 4 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment'
        GROUP BY segment;

-- Step 247: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 248: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 249: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 250: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, os_version=iOS 17.5) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 251: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 252: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 253: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 254: Depth 5 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, device_model=iPhone 14) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 255: Depth 6 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, device_model=iPhone 14, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND device_model = 'iPhone 14' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 256: Depth 6 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, device_model=iPhone 14, os_version=iOS 17.5) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND device_model = 'iPhone 14' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 257: Depth 6 (within ad_format=rewarded, country=AR, campaign_type=CPC, category=entertainment, device_model=iPhone 14, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'AR' AND campaign_type = 'CPC' AND category = 'entertainment' AND device_model = 'iPhone 14' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 258: Depth 2 (within ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 259: Depth 2 (within ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 260: Depth 2 (within ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 261: Depth 2 (within ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 262: Depth 2 (within ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 263: Depth 2 (within ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 264: Depth 2 (within ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 265: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, country=PH) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH'
        GROUP BY segment;

-- Step 266: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, country=PH) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH'
        GROUP BY segment;

-- Step 267: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, country=PH) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH'
        GROUP BY segment;

-- Step 268: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, country=PH) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH'
        GROUP BY segment;

-- Step 269: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, country=PH) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH'
        GROUP BY segment;

-- Step 270: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, country=PH) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH'
        GROUP BY segment;

-- Step 271: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news'
        GROUP BY segment;

-- Step 272: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news'
        GROUP BY segment;

-- Step 273: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news'
        GROUP BY segment;

-- Step 274: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news'
        GROUP BY segment;

-- Step 275: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news'
        GROUP BY segment;

-- Step 276: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news, vertical=auto) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news' AND vertical = 'auto'
        GROUP BY segment;

-- Step 277: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news, vertical=auto) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news' AND vertical = 'auto'
        GROUP BY segment;

-- Step 278: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news, vertical=auto) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news' AND vertical = 'auto'
        GROUP BY segment;

-- Step 279: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, category=news, vertical=auto) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND category = 'news' AND vertical = 'auto'
        GROUP BY segment;

-- Step 280: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 281: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 282: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 283: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 284: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 285: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI, vertical=auto) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI' AND vertical = 'auto'
        GROUP BY segment;

-- Step 286: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI, vertical=auto) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI' AND vertical = 'auto'
        GROUP BY segment;

-- Step 287: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI, vertical=auto) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI' AND vertical = 'auto'
        GROUP BY segment;

-- Step 288: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI, vertical=auto) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI' AND vertical = 'auto'
        GROUP BY segment;

-- Step 289: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI, vertical=auto, category=ecommerce) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI' AND vertical = 'auto' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 290: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI, vertical=auto, category=ecommerce) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI' AND vertical = 'auto' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 291: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, country=PH, campaign_type=CPI, vertical=auto, category=ecommerce) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND country = 'PH' AND campaign_type = 'CPI' AND vertical = 'auto' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 292: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 293: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 294: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 295: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 296: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 297: Depth 3 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 298: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 299: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 300: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 301: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 302: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 303: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, country=IN) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND country = 'IN'
        GROUP BY segment;

-- Step 304: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, country=IN) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND country = 'IN'
        GROUP BY segment;

-- Step 305: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, country=IN) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND country = 'IN'
        GROUP BY segment;

-- Step 306: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, country=IN) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND country = 'IN'
        GROUP BY segment;

-- Step 307: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, country=IN, campaign_type=CPM) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND country = 'IN' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 308: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, country=IN, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND country = 'IN' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 309: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, country=IN, campaign_type=CPM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND country = 'IN' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 310: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND category = 'news'
        GROUP BY segment;

-- Step 311: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND category = 'news'
        GROUP BY segment;

-- Step 312: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, category=news) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND category = 'news'
        GROUP BY segment;

-- Step 313: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND category = 'news'
        GROUP BY segment;

-- Step 314: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, category=news, device_model=iPhone 13) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND category = 'news' AND device_model = 'iPhone 13'
        GROUP BY segment;

-- Step 315: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, category=news, device_model=iPhone 13) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND category = 'news' AND device_model = 'iPhone 13'
        GROUP BY segment;

-- Step 316: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, vertical=cpg, category=news, device_model=iPhone 13) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND vertical = 'cpg' AND category = 'news' AND device_model = 'iPhone 13'
        GROUP BY segment;

-- Step 317: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN'
        GROUP BY segment;

-- Step 318: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN'
        GROUP BY segment;

-- Step 319: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN'
        GROUP BY segment;

-- Step 320: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN'
        GROUP BY segment;

-- Step 321: Depth 4 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN'
        GROUP BY segment;

-- Step 322: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, vertical=cpg) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 323: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 324: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, vertical=cpg) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 325: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, vertical=cpg) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 326: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, vertical=cpg, campaign_type=CPM) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND vertical = 'cpg' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 327: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, vertical=cpg, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND vertical = 'cpg' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 328: Depth 6 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, vertical=cpg, campaign_type=CPM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND vertical = 'cpg' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 329: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, category=news) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND category = 'news'
        GROUP BY segment;

-- Step 330: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND category = 'news'
        GROUP BY segment;

-- Step 331: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND category = 'news'
        GROUP BY segment;

-- Step 332: Depth 5 (within ad_format=rewarded, os_version=iOS 17.5, publisher_tier=tier_1, country=IN, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-15' AND '2026-06-16') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-15' AND '2026-06-16') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-22' AND '2026-06-23') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-22' AND '2026-06-23') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-15' AND '2026-06-23'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND os_version = 'iOS 17.5' AND publisher_tier = 'tier_1' AND country = 'IN' AND category = 'news'
        GROUP BY segment;
