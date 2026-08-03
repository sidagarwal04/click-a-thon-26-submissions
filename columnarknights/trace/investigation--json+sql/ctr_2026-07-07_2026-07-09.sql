-- Investigation: ctr, 2026-07-07 to 2026-07-09 (baseline: 2026-06-30 to 2026-07-02)

-- Step 1: Baseline window aggregate (2026-06-30 to 2026-07-02)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-02';

-- Step 2: Current window aggregate (2026-07-07 to 2026-07-09)
SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN '2026-07-07' AND '2026-07-09';

-- Step 3: Depth 0 — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        GROUP BY segment;

-- Step 4: Depth 0 — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        GROUP BY segment;

-- Step 5: Depth 0 — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        GROUP BY segment;

-- Step 6: Depth 0 — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        GROUP BY segment;

-- Step 7: Depth 0 — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        GROUP BY segment;

-- Step 8: Depth 0 — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        GROUP BY segment;

-- Step 9: Depth 0 — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        GROUP BY segment;

-- Step 10: Depth 0 — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        GROUP BY segment;

-- Step 11: Depth 0 — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        GROUP BY segment;

-- Step 12: Depth 1 (within ad_format=rewarded) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
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
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
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
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
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
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
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
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
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
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
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
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
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
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded'
        GROUP BY segment;

-- Step 20: Depth 2 (within ad_format=rewarded, country=FR) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'FR'
        GROUP BY segment;

-- Step 21: Depth 2 (within ad_format=rewarded, country=FR) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'FR'
        GROUP BY segment;

-- Step 22: Depth 2 (within ad_format=rewarded, country=FR) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'FR'
        GROUP BY segment;

-- Step 23: Depth 2 (within ad_format=rewarded, country=FR) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'FR'
        GROUP BY segment;

-- Step 24: Depth 2 (within ad_format=rewarded, country=FR) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'FR'
        GROUP BY segment;

-- Step 25: Depth 2 (within ad_format=rewarded, country=FR) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'FR'
        GROUP BY segment;

-- Step 26: Depth 2 (within ad_format=rewarded, country=FR) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'FR'
        GROUP BY segment;

-- Step 27: Depth 3 (within ad_format=rewarded, country=FR, device_model=Pixel 8) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 28: Depth 3 (within ad_format=rewarded, country=FR, device_model=Pixel 8) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 29: Depth 3 (within ad_format=rewarded, country=FR, device_model=Pixel 8) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 30: Depth 3 (within ad_format=rewarded, country=FR, device_model=Pixel 8) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 31: Depth 3 (within ad_format=rewarded, country=FR, device_model=Pixel 8) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 32: Depth 3 (within ad_format=rewarded, country=FR, device_model=Pixel 8) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 33: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 34: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 35: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 36: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 37: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, os_version=Android 14) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND os_version = 'Android 14'
        GROUP BY segment;

-- Step 38: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, vertical=auto) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND vertical = 'auto'
        GROUP BY segment;

-- Step 39: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, vertical=auto) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND vertical = 'auto'
        GROUP BY segment;

-- Step 40: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, vertical=auto) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND vertical = 'auto'
        GROUP BY segment;

-- Step 41: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, vertical=auto) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND vertical = 'auto'
        GROUP BY segment;

-- Step 42: Depth 4 (within ad_format=rewarded, country=FR, device_model=Pixel 8, vertical=auto) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND device_model = 'Pixel 8' AND vertical = 'auto'
        GROUP BY segment;

-- Step 43: Depth 3 (within ad_format=rewarded, country=FR, os_version=iOS 18.1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 44: Depth 3 (within ad_format=rewarded, country=FR, os_version=iOS 18.1) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 45: Depth 3 (within ad_format=rewarded, country=FR, os_version=iOS 18.1) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 46: Depth 3 (within ad_format=rewarded, country=FR, os_version=iOS 18.1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 47: Depth 3 (within ad_format=rewarded, country=FR, os_version=iOS 18.1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 48: Depth 3 (within ad_format=rewarded, country=FR, os_version=iOS 18.1) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1'
        GROUP BY segment;

-- Step 49: Depth 4 (within ad_format=rewarded, country=FR, os_version=iOS 18.1, campaign_type=CPC) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 50: Depth 4 (within ad_format=rewarded, country=FR, os_version=iOS 18.1, campaign_type=CPC) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 51: Depth 4 (within ad_format=rewarded, country=FR, os_version=iOS 18.1, campaign_type=CPC) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 52: Depth 4 (within ad_format=rewarded, country=FR, os_version=iOS 18.1, campaign_type=CPC) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 53: Depth 4 (within ad_format=rewarded, country=FR, os_version=iOS 18.1, campaign_type=CPC) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND country = 'FR' AND os_version = 'iOS 18.1' AND campaign_type = 'CPC'
        GROUP BY segment;

-- Step 54: Depth 2 (within ad_format=rewarded, vertical=auto) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 55: Depth 2 (within ad_format=rewarded, vertical=auto) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 56: Depth 2 (within ad_format=rewarded, vertical=auto) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 57: Depth 2 (within ad_format=rewarded, vertical=auto) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 58: Depth 2 (within ad_format=rewarded, vertical=auto) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 59: Depth 2 (within ad_format=rewarded, vertical=auto) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 60: Depth 2 (within ad_format=rewarded, vertical=auto) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'auto'
        GROUP BY segment;

-- Step 61: Depth 3 (within ad_format=rewarded, vertical=auto, region=MEA) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA'
        GROUP BY segment;

-- Step 62: Depth 3 (within ad_format=rewarded, vertical=auto, region=MEA) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA'
        GROUP BY segment;

-- Step 63: Depth 3 (within ad_format=rewarded, vertical=auto, region=MEA) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA'
        GROUP BY segment;

-- Step 64: Depth 3 (within ad_format=rewarded, vertical=auto, region=MEA) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA'
        GROUP BY segment;

-- Step 65: Depth 3 (within ad_format=rewarded, vertical=auto, region=MEA) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA'
        GROUP BY segment;

-- Step 66: Depth 3 (within ad_format=rewarded, vertical=auto, region=MEA) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA'
        GROUP BY segment;

-- Step 67: Depth 4 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 68: Depth 4 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 69: Depth 4 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 70: Depth 4 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 71: Depth 4 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2'
        GROUP BY segment;

-- Step 72: Depth 5 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2, category=ecommerce) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 73: Depth 5 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2, category=ecommerce) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 74: Depth 5 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2, category=ecommerce) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 75: Depth 5 (within ad_format=rewarded, vertical=auto, region=MEA, os_version=iOS 17.2, category=ecommerce) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND region = 'MEA' AND os_version = 'iOS 17.2' AND category = 'ecommerce'
        GROUP BY segment;

-- Step 76: Depth 3 (within ad_format=rewarded, vertical=auto, category=entertainment) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment'
        GROUP BY segment;

-- Step 77: Depth 3 (within ad_format=rewarded, vertical=auto, category=entertainment) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment'
        GROUP BY segment;

-- Step 78: Depth 3 (within ad_format=rewarded, vertical=auto, category=entertainment) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment'
        GROUP BY segment;

-- Step 79: Depth 3 (within ad_format=rewarded, vertical=auto, category=entertainment) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment'
        GROUP BY segment;

-- Step 80: Depth 3 (within ad_format=rewarded, vertical=auto, category=entertainment) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment'
        GROUP BY segment;

-- Step 81: Depth 3 (within ad_format=rewarded, vertical=auto, category=entertainment) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment'
        GROUP BY segment;

-- Step 82: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, os_version=Android 13) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 83: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, os_version=Android 13) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 84: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, os_version=Android 13) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 85: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, os_version=Android 13) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 86: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, os_version=Android 13) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND os_version = 'Android 13'
        GROUP BY segment;

-- Step 87: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 88: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 89: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 90: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8) — rank segments for dimension 'country'
SELECT
            country AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND country != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 91: Depth 4 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8'
        GROUP BY segment;

-- Step 92: Depth 5 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8, country=FR) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8' AND country = 'FR'
        GROUP BY segment;

-- Step 93: Depth 5 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8, country=FR) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8' AND country = 'FR'
        GROUP BY segment;

-- Step 94: Depth 5 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8, country=FR) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8' AND country = 'FR'
        GROUP BY segment;

-- Step 95: Depth 5 (within ad_format=rewarded, vertical=auto, category=entertainment, device_model=Pixel 8, country=FR) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND ad_format = 'rewarded' AND vertical = 'auto' AND category = 'entertainment' AND device_model = 'Pixel 8' AND country = 'FR'
        GROUP BY segment;

-- Step 96: Depth 1 (within country=FR) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'FR'
        GROUP BY segment;

-- Step 97: Depth 1 (within country=FR) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'FR'
        GROUP BY segment;

-- Step 98: Depth 1 (within country=FR) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'FR'
        GROUP BY segment;

-- Step 99: Depth 1 (within country=FR) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'FR'
        GROUP BY segment;

-- Step 100: Depth 1 (within country=FR) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR'
        GROUP BY segment;

-- Step 101: Depth 1 (within country=FR) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR'
        GROUP BY segment;

-- Step 102: Depth 1 (within country=FR) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'FR'
        GROUP BY segment;

-- Step 103: Depth 1 (within country=FR) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'FR'
        GROUP BY segment;

-- Step 104: Depth 2 (within country=FR, device_model=Galaxy A54) — rank segments for dimension 'ad_format'
SELECT
            ad_format AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND ad_format != ''
        AND country = 'FR' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 105: Depth 2 (within country=FR, device_model=Galaxy A54) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'FR' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 106: Depth 2 (within country=FR, device_model=Galaxy A54) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'FR' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 107: Depth 2 (within country=FR, device_model=Galaxy A54) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'FR' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 108: Depth 2 (within country=FR, device_model=Galaxy A54) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 109: Depth 2 (within country=FR, device_model=Galaxy A54) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 110: Depth 2 (within country=FR, device_model=Galaxy A54) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'FR' AND device_model = 'Galaxy A54'
        GROUP BY segment;

-- Step 111: Depth 2 (within country=FR, ad_format=banner) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'FR' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 112: Depth 2 (within country=FR, ad_format=banner) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'FR' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 113: Depth 2 (within country=FR, ad_format=banner) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'FR' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 114: Depth 2 (within country=FR, ad_format=banner) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 115: Depth 2 (within country=FR, ad_format=banner) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 116: Depth 2 (within country=FR, ad_format=banner) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'FR' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 117: Depth 2 (within country=FR, ad_format=banner) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'FR' AND ad_format = 'banner'
        GROUP BY segment;

-- Step 118: Depth 3 (within country=FR, ad_format=banner, device_model=Redmi Note 12) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 119: Depth 3 (within country=FR, ad_format=banner, device_model=Redmi Note 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 120: Depth 3 (within country=FR, ad_format=banner, device_model=Redmi Note 12) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 121: Depth 3 (within country=FR, ad_format=banner, device_model=Redmi Note 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 122: Depth 3 (within country=FR, ad_format=banner, device_model=Redmi Note 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 123: Depth 3 (within country=FR, ad_format=banner, device_model=Redmi Note 12) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12'
        GROUP BY segment;

-- Step 124: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel'
        GROUP BY segment;

-- Step 125: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel'
        GROUP BY segment;

-- Step 126: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel'
        GROUP BY segment;

-- Step 127: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel'
        GROUP BY segment;

-- Step 128: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel'
        GROUP BY segment;

-- Step 129: Depth 5 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel, os_version=Android 15) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 130: Depth 5 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel, os_version=Android 15) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 131: Depth 5 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel, os_version=Android 15) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 132: Depth 5 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel, os_version=Android 15) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel' AND os_version = 'Android 15'
        GROUP BY segment;

-- Step 133: Depth 6 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel, os_version=Android 15, publisher_tier=tier_1) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel' AND os_version = 'Android 15' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 134: Depth 6 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel, os_version=Android 15, publisher_tier=tier_1) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel' AND os_version = 'Android 15' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 135: Depth 6 (within country=FR, ad_format=banner, device_model=Redmi Note 12, vertical=travel, os_version=Android 15, publisher_tier=tier_1) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND vertical = 'travel' AND os_version = 'Android 15' AND publisher_tier = 'tier_1'
        GROUP BY segment;

-- Step 136: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, os_version=Android 12) — rank segments for dimension 'category'
SELECT
            category AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND category != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 137: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, os_version=Android 12) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 138: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, os_version=Android 12) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 139: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, os_version=Android 12) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 140: Depth 4 (within country=FR, ad_format=banner, device_model=Redmi Note 12, os_version=Android 12) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR' AND ad_format = 'banner' AND device_model = 'Redmi Note 12' AND os_version = 'Android 12'
        GROUP BY segment;

-- Step 141: Depth 3 (within country=FR, ad_format=banner, category=news) — rank segments for dimension 'publisher_tier'
SELECT
            publisher_tier AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND publisher_tier != ''
        AND country = 'FR' AND ad_format = 'banner' AND category = 'news'
        GROUP BY segment;

-- Step 142: Depth 3 (within country=FR, ad_format=banner, category=news) — rank segments for dimension 'vertical'
SELECT
            vertical AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND vertical != ''
        AND country = 'FR' AND ad_format = 'banner' AND category = 'news'
        GROUP BY segment;

-- Step 143: Depth 3 (within country=FR, ad_format=banner, category=news) — rank segments for dimension 'campaign_type'
SELECT
            campaign_type AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND campaign_type != ''
        AND country = 'FR' AND ad_format = 'banner' AND category = 'news'
        GROUP BY segment;

-- Step 144: Depth 3 (within country=FR, ad_format=banner, category=news) — rank segments for dimension 'region'
SELECT
            region AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND region != ''
        AND country = 'FR' AND ad_format = 'banner' AND category = 'news'
        GROUP BY segment;

-- Step 145: Depth 3 (within country=FR, ad_format=banner, category=news) — rank segments for dimension 'device_model'
SELECT
            device_model AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND device_model != ''
        AND country = 'FR' AND ad_format = 'banner' AND category = 'news'
        GROUP BY segment;

-- Step 146: Depth 3 (within country=FR, ad_format=banner, category=news) — rank segments for dimension 'os_version'
SELECT
            os_version AS segment,
            countIf(event_date BETWEEN '2026-06-30' AND '2026-07-02') AS requests_b,
            sumIf(is_filled, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS fills_b,
            sumIf(is_impression, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS impressions_b,
            sumIf(is_click, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS clicks_b,
            sumIf(revenue, event_date BETWEEN '2026-06-30' AND '2026-07-02') AS revenue_b,
            countIf(event_date BETWEEN '2026-07-07' AND '2026-07-09') AS requests_c,
            sumIf(is_filled, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS fills_c,
            sumIf(is_impression, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS impressions_c,
            sumIf(is_click, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS clicks_c,
            sumIf(revenue, event_date BETWEEN '2026-07-07' AND '2026-07-09') AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN '2026-06-30' AND '2026-07-09'
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND os_version != ''
        AND country = 'FR' AND ad_format = 'banner' AND category = 'news'
        GROUP BY segment;
