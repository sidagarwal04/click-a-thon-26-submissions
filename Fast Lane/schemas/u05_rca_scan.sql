CREATE OR REPLACE VIEW `inmobi-hari`.rca_scan AS
WITH
    src AS (
        SELECT dimension, value,
               toDate(hour) BETWEEN {test_from:Date} AND {test_to:Date} AS t,
               multiIf({metric:String}='fill_rate',   toFloat64(fills),
                       {metric:String}='render_rate', toFloat64(impressions),
                       {metric:String}='ecpm',        revenue*1000,
                                                      revenue*1000) AS num,
               multiIf({metric:String}='fill_rate',   toFloat64(requests),
                       {metric:String}='render_rate', toFloat64(fills),
                       {metric:String}='ecpm',        toFloat64(impressions),
                                                      toFloat64(requests)) AS den
        FROM `inmobi-hari`.rollup_marginal_1h
        WHERE toDate(hour) BETWEEN {test_from:Date} AND {test_to:Date}
           OR toDate(hour) BETWEEN {base_from:Date} AND {base_to:Date}
    ),
    seg AS (
        SELECT dimension, value,
               sumIf(num, NOT t) AS n0, sumIf(num, t) AS n1,
               sumIf(den, NOT t) AS d0, sumIf(den, t) AS d1
        FROM src GROUP BY dimension, value HAVING d0 > 0 AND d1 > 0
    ),
    seg2 AS (
        SELECT dimension, value, n0/d0 AS m0, n1/d1 AS m1, m1-m0 AS dm,
               d0/sum(d0) OVER (PARTITION BY dimension) AS w0,
               d1/sum(d1) OVER (PARTITION BY dimension) AS w1,
               sum(n0) OVER (PARTITION BY dimension)/sum(d0) OVER (PARTITION BY dimension) AS M0,
               sum(n1) OVER (PARTITION BY dimension)/sum(d1) OVER (PARTITION BY dimension) AS M1,
               M1-M0 AS DM
        FROM seg
    )
SELECT dimension, count() AS segments,
       round(any(M0),5) AS baseline, round(any(M1),5) AS observed, round(any(DM),5) AS delta,
       round(sqrt(sum((w0+w1)/2*pow(dm-DM,2))),5) AS dispersion,
       round(dispersion/abs(any(DM)),2) AS concentration,
       round(max(abs(dm))/abs(any(DM)),2) AS worst_seg_x
FROM seg2 GROUP BY dimension ORDER BY concentration DESC;

CREATE OR REPLACE VIEW `inmobi-hari`.rca_seg AS
WITH
    src AS (
        SELECT value,
               toDate(hour) BETWEEN {test_from:Date} AND {test_to:Date} AS t,
               multiIf({metric:String}='fill_rate',   toFloat64(fills),
                       {metric:String}='render_rate', toFloat64(impressions),
                       {metric:String}='ecpm',        revenue*1000,
                                                      revenue*1000) AS num,
               multiIf({metric:String}='fill_rate',   toFloat64(requests),
                       {metric:String}='render_rate', toFloat64(fills),
                       {metric:String}='ecpm',        toFloat64(impressions),
                                                      toFloat64(requests)) AS den
        FROM `inmobi-hari`.rollup_marginal_1h
        WHERE dimension = {dim:String}
          AND (toDate(hour) BETWEEN {test_from:Date} AND {test_to:Date}
            OR toDate(hour) BETWEEN {base_from:Date} AND {base_to:Date})
    ),
    seg AS (
        SELECT value, sumIf(num, NOT t) AS n0, sumIf(num, t) AS n1,
                      sumIf(den, NOT t) AS d0, sumIf(den, t) AS d1
        FROM src GROUP BY value HAVING d0 > 0 AND d1 > 0
    ),
    seg2 AS (
        SELECT value, n0/d0 AS m0, n1/d1 AS m1, m1-m0 AS dm,
               d0/sum(d0) OVER () AS w0, d1/sum(d1) OVER () AS w1,
               (w0+w1)/2*dm AS rate_effect, (m0+m1)/2*(w1-w0) AS mix_effect
        FROM seg
    )
SELECT value AS segment,
       concat(toString(round(w1*100,1)),'%') AS traffic_share,
       round(m0,5) AS baseline, round(m1,5) AS observed,
       concat(if(dm>=0,'+',''), toString(round(dm/m0*100,1)),'%') AS change,
       round(rate_effect,6) AS rate_effect, round(mix_effect,6) AS mix_effect,
       round(rate_effect+mix_effect,6) AS total_effect
FROM seg2 ORDER BY abs(rate_effect+mix_effect) DESC;
