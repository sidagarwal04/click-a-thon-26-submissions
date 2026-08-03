-- Glossary-aligned metric helpers + detection thresholds (sum/sum only).
-- Idempotent: CREATE OR REPLACE FUNCTION.

CREATE OR REPLACE FUNCTION rca_fill_rate AS (fills, requests) ->
    fills / nullIf(requests, 0);

CREATE OR REPLACE FUNCTION rca_ecpm AS (revenue, impressions) ->
    (revenue / nullIf(impressions, 0)) * 1000;

CREATE OR REPLACE FUNCTION rca_ctr AS (clicks, impressions) ->
    clicks / nullIf(impressions, 0);

CREATE OR REPLACE FUNCTION rca_rpr AS (revenue, requests) ->
    revenue / nullIf(requests, 0);

CREATE OR REPLACE FUNCTION rca_pct_chg AS (t, b) ->
    (t - b) / nullIf(b, 0);

CREATE OR REPLACE FUNCTION rca_abs_chg AS (t, b) ->
    t - b;

-- Thresholds match src/clickathon/metrics.py
CREATE OR REPLACE FUNCTION rca_flag_volume AS (req_chg) ->
    abs(ifNull(req_chg, 0)) >= 0.15;

CREATE OR REPLACE FUNCTION rca_flag_fill AS (fill_chg) ->
    abs(ifNull(fill_chg, 0)) >= 0.015;

CREATE OR REPLACE FUNCTION rca_flag_ecpm AS (ecpm_chg) ->
    abs(ifNull(ecpm_chg, 0)) >= 0.04;

CREATE OR REPLACE FUNCTION rca_flag_revenue AS (rev_chg) ->
    abs(ifNull(rev_chg, 0)) >= 0.03;
