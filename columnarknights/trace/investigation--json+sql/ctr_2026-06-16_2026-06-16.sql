-- Investigation: ctr, 2026-06-16 to 2026-06-16 (baseline: 2026-06-09 to 2026-06-09)

-- Step 1: Baseline window aggregate (2026-06-09 to 2026-06-09)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-09';

-- Step 2: Current window aggregate (2026-06-16 to 2026-06-16)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-16' AND '2026-06-16';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 10: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 11: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;

-- Step 12: Depth 1 (within country=ID) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID'
        GROUP BY segment;

-- Step 13: Depth 1 (within country=ID) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID'
        GROUP BY segment;

-- Step 14: Depth 1 (within country=ID) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID'
        GROUP BY segment;

-- Step 15: Depth 1 (within country=ID) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'ID'
        GROUP BY segment;

-- Step 16: Depth 1 (within country=ID) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID'
        GROUP BY segment;

-- Step 17: Depth 1 (within country=ID) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID'
        GROUP BY segment;

-- Step 18: Depth 1 (within country=ID) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'ID'
        GROUP BY segment;

-- Step 19: Depth 1 (within country=ID) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID'
        GROUP BY segment;

-- Step 20: Depth 2 (within country=ID, vertical=gaming) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 21: Depth 2 (within country=ID, vertical=gaming) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 22: Depth 2 (within country=ID, vertical=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 23: Depth 2 (within country=ID, vertical=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 24: Depth 2 (within country=ID, vertical=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 25: Depth 2 (within country=ID, vertical=gaming) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'ID' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 26: Depth 2 (within country=ID, vertical=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 27: Depth 3 (within country=ID, vertical=gaming, ad_format=video) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 28: Depth 3 (within country=ID, vertical=gaming, ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 29: Depth 3 (within country=ID, vertical=gaming, ad_format=video) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 30: Depth 3 (within country=ID, vertical=gaming, ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 31: Depth 3 (within country=ID, vertical=gaming, ad_format=video) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 32: Depth 3 (within country=ID, vertical=gaming, ad_format=video) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 33: Depth 4 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 34: Depth 4 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 35: Depth 4 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 36: Depth 4 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 37: Depth 4 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 38: Depth 5 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7' AND category = 'utility'
        GROUP BY segment;

-- Step 39: Depth 5 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7' AND category = 'utility'
        GROUP BY segment;

-- Step 40: Depth 5 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7' AND category = 'utility'
        GROUP BY segment;

-- Step 41: Depth 5 (within country=ID, vertical=gaming, ad_format=video, device_model=Pixel 7, category=utility) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND device_model = 'Pixel 7' AND category = 'utility'
        GROUP BY segment;

-- Step 42: Depth 4 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 43: Depth 4 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 44: Depth 4 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 45: Depth 4 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 46: Depth 4 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 47: Depth 5 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12' AND category = 'utility'
        GROUP BY segment;

-- Step 48: Depth 5 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12' AND category = 'utility'
        GROUP BY segment;

-- Step 49: Depth 5 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12' AND category = 'utility'
        GROUP BY segment;

-- Step 50: Depth 5 (within country=ID, vertical=gaming, ad_format=video, os_version=Android 12, category=utility) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'ID' AND vertical = 'gaming' AND ad_format = 'video' AND os_version = 'Android 12' AND category = 'utility'
        GROUP BY segment;

-- Step 51: Depth 3 (within country=ID, vertical=gaming, device_model=iPhone 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 52: Depth 3 (within country=ID, vertical=gaming, device_model=iPhone 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 53: Depth 3 (within country=ID, vertical=gaming, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 54: Depth 3 (within country=ID, vertical=gaming, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 55: Depth 3 (within country=ID, vertical=gaming, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 56: Depth 3 (within country=ID, vertical=gaming, device_model=iPhone 14) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 57: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 58: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 59: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 60: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 61: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 62: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded, category=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 63: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded, category=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 64: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded, category=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 65: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded, category=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND category = 'gaming'
        GROUP BY segment;

-- Step 66: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded, campaign_type=CPC) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 67: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 68: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 69: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, ad_format=rewarded, campaign_type=CPC) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND ad_format = 'rewarded' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 70: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 71: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 72: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 73: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 74: Depth 4 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 75: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 76: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 77: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 78: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 79: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC, category=gaming) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND category = 'gaming'
        GROUP BY segment;

-- Step 80: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC, category=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND category = 'gaming'
        GROUP BY segment;

-- Step 81: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC, category=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND category = 'gaming'
        GROUP BY segment;

-- Step 82: Depth 5 (within country=ID, vertical=gaming, device_model=iPhone 14, campaign_type=CPC, category=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND vertical = 'gaming' AND device_model = 'iPhone 14' AND campaign_type = 'CPC' AND category = 'gaming'
        GROUP BY segment;

-- Step 83: Depth 2 (within country=ID, device_model=Pixel 7) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 84: Depth 2 (within country=ID, device_model=Pixel 7) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 85: Depth 2 (within country=ID, device_model=Pixel 7) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 86: Depth 2 (within country=ID, device_model=Pixel 7) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'ID' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 87: Depth 2 (within country=ID, device_model=Pixel 7) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 88: Depth 2 (within country=ID, device_model=Pixel 7) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 89: Depth 2 (within country=ID, device_model=Pixel 7) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 90: Depth 3 (within country=ID, device_model=Pixel 7, ad_format=video) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video'
        GROUP BY segment;

-- Step 91: Depth 3 (within country=ID, device_model=Pixel 7, ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video'
        GROUP BY segment;

-- Step 92: Depth 3 (within country=ID, device_model=Pixel 7, ad_format=video) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video'
        GROUP BY segment;

-- Step 93: Depth 3 (within country=ID, device_model=Pixel 7, ad_format=video) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video'
        GROUP BY segment;

-- Step 94: Depth 3 (within country=ID, device_model=Pixel 7, ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video'
        GROUP BY segment;

-- Step 95: Depth 3 (within country=ID, device_model=Pixel 7, ad_format=video) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video'
        GROUP BY segment;

-- Step 96: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 97: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 98: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 99: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 100: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 101: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming' AND category = 'utility'
        GROUP BY segment;

-- Step 102: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming' AND category = 'utility'
        GROUP BY segment;

-- Step 103: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming' AND category = 'utility'
        GROUP BY segment;

-- Step 104: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, vertical=gaming, category=utility) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND vertical = 'gaming' AND category = 'utility'
        GROUP BY segment;

-- Step 105: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming'
        GROUP BY segment;

-- Step 106: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming'
        GROUP BY segment;

-- Step 107: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming'
        GROUP BY segment;

-- Step 108: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming'
        GROUP BY segment;

-- Step 109: Depth 4 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming'
        GROUP BY segment;

-- Step 110: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming, vertical=cpg) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 111: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming, vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 112: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming, vertical=cpg) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 113: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming, vertical=cpg) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming' AND vertical = 'cpg'
        GROUP BY segment;

-- Step 114: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming, publisher_tier=tier_3) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 115: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming, publisher_tier=tier_3) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 116: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming, publisher_tier=tier_3) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 117: Depth 5 (within country=ID, device_model=Pixel 7, ad_format=video, category=gaming, publisher_tier=tier_3) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND ad_format = 'video' AND category = 'gaming' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 118: Depth 3 (within country=ID, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 119: Depth 3 (within country=ID, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 120: Depth 3 (within country=ID, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 121: Depth 3 (within country=ID, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 122: Depth 3 (within country=ID, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 123: Depth 3 (within country=ID, device_model=Pixel 7, vertical=gaming) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming'
        GROUP BY segment;

-- Step 124: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 125: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 126: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 127: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 128: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video'
        GROUP BY segment;

-- Step 129: Depth 5 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video' AND category = 'utility'
        GROUP BY segment;

-- Step 130: Depth 5 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video' AND category = 'utility'
        GROUP BY segment;

-- Step 131: Depth 5 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video' AND category = 'utility'
        GROUP BY segment;

-- Step 132: Depth 5 (within country=ID, device_model=Pixel 7, vertical=gaming, ad_format=video, category=utility) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND ad_format = 'video' AND category = 'utility'
        GROUP BY segment;

-- Step 133: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social'
        GROUP BY segment;

-- Step 134: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social'
        GROUP BY segment;

-- Step 135: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social'
        GROUP BY segment;

-- Step 136: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social'
        GROUP BY segment;

-- Step 137: Depth 4 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social'
        GROUP BY segment;

-- Step 138: Depth 5 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social, publisher_tier=tier_2) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 139: Depth 5 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social, publisher_tier=tier_2) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 140: Depth 5 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social, publisher_tier=tier_2) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 141: Depth 5 (within country=ID, device_model=Pixel 7, vertical=gaming, category=social, publisher_tier=tier_2) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'ID' AND device_model = 'Pixel 7' AND vertical = 'gaming' AND category = 'social' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 142: Depth 1 (within vertical=cpg) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg'
        GROUP BY segment;

-- Step 143: Depth 1 (within vertical=cpg) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'cpg'
        GROUP BY segment;

-- Step 144: Depth 1 (within vertical=cpg) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg'
        GROUP BY segment;

-- Step 145: Depth 1 (within vertical=cpg) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg'
        GROUP BY segment;

-- Step 146: Depth 1 (within vertical=cpg) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg'
        GROUP BY segment;

-- Step 147: Depth 1 (within vertical=cpg) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'cpg'
        GROUP BY segment;

-- Step 148: Depth 1 (within vertical=cpg) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg'
        GROUP BY segment;

-- Step 149: Depth 1 (within vertical=cpg) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg'
        GROUP BY segment;

-- Step 150: Depth 2 (within vertical=cpg, country=UK) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK'
        GROUP BY segment;

-- Step 151: Depth 2 (within vertical=cpg, country=UK) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'cpg' AND country = 'UK'
        GROUP BY segment;

-- Step 152: Depth 2 (within vertical=cpg, country=UK) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK'
        GROUP BY segment;

-- Step 153: Depth 2 (within vertical=cpg, country=UK) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK'
        GROUP BY segment;

-- Step 154: Depth 2 (within vertical=cpg, country=UK) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK'
        GROUP BY segment;

-- Step 155: Depth 2 (within vertical=cpg, country=UK) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND country = 'UK'
        GROUP BY segment;

-- Step 156: Depth 2 (within vertical=cpg, country=UK) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND country = 'UK'
        GROUP BY segment;

-- Step 157: Depth 3 (within vertical=cpg, country=UK, os_version=iOS 17.2) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 158: Depth 3 (within vertical=cpg, country=UK, os_version=iOS 17.2) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 159: Depth 3 (within vertical=cpg, country=UK, os_version=iOS 17.2) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 160: Depth 3 (within vertical=cpg, country=UK, os_version=iOS 17.2) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 161: Depth 3 (within vertical=cpg, country=UK, os_version=iOS 17.2) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 162: Depth 3 (within vertical=cpg, country=UK, os_version=iOS 17.2) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 163: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility'
        GROUP BY segment;

-- Step 164: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility'
        GROUP BY segment;

-- Step 165: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility'
        GROUP BY segment;

-- Step 166: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility'
        GROUP BY segment;

-- Step 167: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility'
        GROUP BY segment;

-- Step 168: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, device_model=iPhone 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 169: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 170: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 171: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 172: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 173: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 174: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 175: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 176: Depth 6 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 177: Depth 6 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 178: Depth 6 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner, campaign_type=CPM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 179: Depth 6 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 180: Depth 6 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 181: Depth 6 (within vertical=cpg, country=UK, os_version=iOS 17.2, category=utility, ad_format=banner, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND category = 'utility' AND ad_format = 'banner' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 182: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 183: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 184: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 185: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 186: Depth 4 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 187: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14, category=utility) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14' AND category = 'utility'
        GROUP BY segment;

-- Step 188: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14, category=utility) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14' AND category = 'utility'
        GROUP BY segment;

-- Step 189: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14, category=utility) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14' AND category = 'utility'
        GROUP BY segment;

-- Step 190: Depth 5 (within vertical=cpg, country=UK, os_version=iOS 17.2, device_model=iPhone 14, category=utility) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND os_version = 'iOS 17.2' AND device_model = 'iPhone 14' AND category = 'utility'
        GROUP BY segment;

-- Step 191: Depth 3 (within vertical=cpg, country=UK, device_model=Pixel 8) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 192: Depth 3 (within vertical=cpg, country=UK, device_model=Pixel 8) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 193: Depth 3 (within vertical=cpg, country=UK, device_model=Pixel 8) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 194: Depth 3 (within vertical=cpg, country=UK, device_model=Pixel 8) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 195: Depth 3 (within vertical=cpg, country=UK, device_model=Pixel 8) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 196: Depth 3 (within vertical=cpg, country=UK, device_model=Pixel 8) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 197: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 198: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 199: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 200: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 201: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 202: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded, os_version=Android 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 203: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded, os_version=Android 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 204: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded, os_version=Android 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 205: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded, os_version=Android 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 206: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded, campaign_type=CPM) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 207: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 208: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 209: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, ad_format=rewarded, campaign_type=CPM) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND ad_format = 'rewarded' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 210: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment'
        GROUP BY segment;

-- Step 211: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment'
        GROUP BY segment;

-- Step 212: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment'
        GROUP BY segment;

-- Step 213: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment'
        GROUP BY segment;

-- Step 214: Depth 4 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment'
        GROUP BY segment;

-- Step 215: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, os_version=Android 14) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 216: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, os_version=Android 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 217: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, os_version=Android 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 218: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, os_version=Android 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 219: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native'
        GROUP BY segment;

-- Step 220: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native'
        GROUP BY segment;

-- Step 221: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native'
        GROUP BY segment;

-- Step 222: Depth 5 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native'
        GROUP BY segment;

-- Step 223: Depth 6 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native, publisher_tier=tier_3) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 224: Depth 6 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native, publisher_tier=tier_3) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 225: Depth 6 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native, publisher_tier=tier_3) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 226: Depth 6 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 227: Depth 6 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 228: Depth 6 (within vertical=cpg, country=UK, device_model=Pixel 8, category=entertainment, ad_format=native, campaign_type=CPC) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND country = 'UK' AND device_model = 'Pixel 8' AND category = 'entertainment' AND ad_format = 'native' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 229: Depth 2 (within vertical=cpg, category=social) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social'
        GROUP BY segment;

-- Step 230: Depth 2 (within vertical=cpg, category=social) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social'
        GROUP BY segment;

-- Step 231: Depth 2 (within vertical=cpg, category=social) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social'
        GROUP BY segment;

-- Step 232: Depth 2 (within vertical=cpg, category=social) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social'
        GROUP BY segment;

-- Step 233: Depth 2 (within vertical=cpg, category=social) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'cpg' AND category = 'social'
        GROUP BY segment;

-- Step 234: Depth 2 (within vertical=cpg, category=social) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social'
        GROUP BY segment;

-- Step 235: Depth 2 (within vertical=cpg, category=social) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social'
        GROUP BY segment;

-- Step 236: Depth 3 (within vertical=cpg, category=social, country=MX) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX'
        GROUP BY segment;

-- Step 237: Depth 3 (within vertical=cpg, category=social, country=MX) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX'
        GROUP BY segment;

-- Step 238: Depth 3 (within vertical=cpg, category=social, country=MX) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX'
        GROUP BY segment;

-- Step 239: Depth 3 (within vertical=cpg, category=social, country=MX) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX'
        GROUP BY segment;

-- Step 240: Depth 3 (within vertical=cpg, category=social, country=MX) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX'
        GROUP BY segment;

-- Step 241: Depth 3 (within vertical=cpg, category=social, country=MX) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX'
        GROUP BY segment;

-- Step 242: Depth 4 (within vertical=cpg, category=social, country=MX, ad_format=video) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video'
        GROUP BY segment;

-- Step 243: Depth 4 (within vertical=cpg, category=social, country=MX, ad_format=video) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video'
        GROUP BY segment;

-- Step 244: Depth 4 (within vertical=cpg, category=social, country=MX, ad_format=video) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video'
        GROUP BY segment;

-- Step 245: Depth 4 (within vertical=cpg, category=social, country=MX, ad_format=video) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video'
        GROUP BY segment;

-- Step 246: Depth 4 (within vertical=cpg, category=social, country=MX, ad_format=video) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video'
        GROUP BY segment;

-- Step 247: Depth 5 (within vertical=cpg, category=social, country=MX, ad_format=video, campaign_type=CPM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 248: Depth 5 (within vertical=cpg, category=social, country=MX, ad_format=video, campaign_type=CPM) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 249: Depth 5 (within vertical=cpg, category=social, country=MX, ad_format=video, campaign_type=CPM) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 250: Depth 5 (within vertical=cpg, category=social, country=MX, ad_format=video, campaign_type=CPM) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND campaign_type = 'CPM'
        GROUP BY segment;

-- Step 251: Depth 6 (within vertical=cpg, category=social, country=MX, ad_format=video, campaign_type=CPM, publisher_tier=tier_2) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND campaign_type = 'CPM' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 252: Depth 6 (within vertical=cpg, category=social, country=MX, ad_format=video, campaign_type=CPM, publisher_tier=tier_2) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND campaign_type = 'CPM' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 253: Depth 6 (within vertical=cpg, category=social, country=MX, ad_format=video, campaign_type=CPM, publisher_tier=tier_2) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND campaign_type = 'CPM' AND publisher_tier = 'tier_2'
        GROUP BY segment;

-- Step 254: Depth 5 (within vertical=cpg, category=social, country=MX, ad_format=video, device_model=iPhone 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 255: Depth 5 (within vertical=cpg, category=social, country=MX, ad_format=video, device_model=iPhone 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 256: Depth 5 (within vertical=cpg, category=social, country=MX, ad_format=video, device_model=iPhone 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 257: Depth 5 (within vertical=cpg, category=social, country=MX, ad_format=video, device_model=iPhone 14) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND ad_format = 'video' AND device_model = 'iPhone 14'
        GROUP BY segment;

-- Step 258: Depth 4 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 259: Depth 4 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 260: Depth 4 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 261: Depth 4 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 262: Depth 4 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15'
        GROUP BY segment;

-- Step 263: Depth 5 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 264: Depth 5 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 265: Depth 5 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 266: Depth 5 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 267: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 268: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 269: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 270: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 271: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 272: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 273: Depth 5 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 274: Depth 5 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 275: Depth 5 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 276: Depth 5 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 277: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, ad_format=rewarded) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 278: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 279: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 280: Depth 7 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 281: Depth 7 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, ad_format=rewarded, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND ad_format = 'rewarded' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 282: Depth 7 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 283: Depth 7 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, ad_format=rewarded, os_version=iOS 17.5) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND ad_format = 'rewarded' AND os_version = 'iOS 17.5'
        GROUP BY segment;

-- Step 284: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, publisher_tier=tier_1) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 285: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 286: Depth 6 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, publisher_tier=tier_1) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 287: Depth 7 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, publisher_tier=tier_1, ad_format=rewarded) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND publisher_tier = 'tier_1' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 288: Depth 7 (within vertical=cpg, category=social, country=MX, device_model=iPhone 15, campaign_type=CPI, publisher_tier=tier_1, ad_format=rewarded) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND vertical = 'cpg' AND category = 'social' AND country = 'MX' AND device_model = 'iPhone 15' AND campaign_type = 'CPI' AND publisher_tier = 'tier_1' AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 289: Depth 3 (within vertical=cpg, category=social, os_version=Android 15) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 290: Depth 3 (within vertical=cpg, category=social, os_version=Android 15) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 291: Depth 3 (within vertical=cpg, category=social, os_version=Android 15) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 292: Depth 3 (within vertical=cpg, category=social, os_version=Android 15) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 293: Depth 3 (within vertical=cpg, category=social, os_version=Android 15) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 294: Depth 3 (within vertical=cpg, category=social, os_version=Android 15) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 295: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, country=US) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US'
        GROUP BY segment;

-- Step 296: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, country=US) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US'
        GROUP BY segment;

-- Step 297: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, country=US) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US'
        GROUP BY segment;

-- Step 298: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, country=US) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US'
        GROUP BY segment;

-- Step 299: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, country=US) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US'
        GROUP BY segment;

-- Step 300: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, country=US, device_model=Pixel 7) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 301: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, country=US, device_model=Pixel 7) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 302: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, country=US, device_model=Pixel 7) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 303: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, country=US, device_model=Pixel 7) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 304: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 305: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 306: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 307: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3'
        GROUP BY segment;

-- Step 308: Depth 6 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3, campaign_type=CPI) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 309: Depth 6 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3, campaign_type=CPI) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 310: Depth 6 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3, campaign_type=CPI) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3' AND campaign_type = 'CPI'
        GROUP BY segment;

-- Step 311: Depth 6 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3, device_model=Redmi Note 12) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 312: Depth 6 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3, device_model=Redmi Note 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 313: Depth 6 (within vertical=cpg, category=social, os_version=Android 15, country=US, publisher_tier=tier_3, device_model=Redmi Note 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND country = 'US' AND publisher_tier = 'tier_3' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 314: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 315: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 316: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 317: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 318: Depth 4 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7'
        GROUP BY segment;

-- Step 319: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7, country=US) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7' AND country = 'US'
        GROUP BY segment;

-- Step 320: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7, country=US) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7' AND country = 'US'
        GROUP BY segment;

-- Step 321: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7, country=US) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7' AND country = 'US'
        GROUP BY segment;

-- Step 322: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7, country=US) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7' AND country = 'US'
        GROUP BY segment;

-- Step 323: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7, region=NAM) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7' AND region = 'NAM'
        GROUP BY segment;

-- Step 324: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7, region=NAM) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7' AND region = 'NAM'
        GROUP BY segment;

-- Step 325: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7, region=NAM) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7' AND region = 'NAM'
        GROUP BY segment;

-- Step 326: Depth 5 (within vertical=cpg, category=social, os_version=Android 15, device_model=Pixel 7, region=NAM) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-09' AND '2026-06-09') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-09' AND '2026-06-09') AS revenue_b,
            countIf(event_date BETWEEN '2026-06-16' AND '2026-06-16') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-06-16' AND '2026-06-16') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-09' AND '2026-06-16'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND vertical = 'cpg' AND category = 'social' AND os_version = 'Android 15' AND device_model = 'Pixel 7' AND region = 'NAM'
        GROUP BY segment;
