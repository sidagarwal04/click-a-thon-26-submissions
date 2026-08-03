-- Factor decomposition per day from rca_daily_wow (Revenue ≈ Req × Fill × eCPM/1000).

TRUNCATE TABLE rca_factor_day;

INSERT INTO rca_factor_day
SELECT
    event_date,
    baseline_day,
    multiIf(
        ifNull(req_chg, 0) <= -0.15, 'requests',
        flag_volume = 1 AND flag_fill = 0 AND flag_ecpm = 0, 'requests',
        flag_fill = 1
            AND ifNull(fill_chg, 0) < 0
            AND abs(ifNull(fill_chg, 0)) >= abs(ifNull(ecpm_chg, 0)) / 10,
            'fill_rate',
        flag_ecpm = 1 AND flag_fill = 0 AND ifNull(ecpm_chg, 0) < 0, 'ecpm',
        flag_ecpm = 1 AND ifNull(ecpm_chg, 0) > 0 AND ifNull(fill_chg, 0) < 0, 'fill_rate',
        flag_ecpm = 1 AND ifNull(ecpm_chg, 0) > 0 AND ifNull(req_chg, 0) < 0, 'requests',
        arrayElement(
            ['requests', 'fill_rate', 'ecpm'],
            indexOf(
                [
                    abs(ifNull(req_chg, 0)),
                    abs(ifNull(rca_pct_chg(fill_rate, base_fill_rate), 0)),
                    abs(ifNull(rca_pct_chg(ecpm, base_ecpm), 0))
                ],
                arrayMax([
                    abs(ifNull(req_chg, 0)),
                    abs(ifNull(rca_pct_chg(fill_rate, base_fill_rate), 0)),
                    abs(ifNull(rca_pct_chg(ecpm, base_ecpm), 0))
                ])
            )
        )
    ) AS primary_factor,
    abs(ifNull(req_chg, 0))
        / nullIf(
            abs(ifNull(req_chg, 0))
            + abs(ifNull(rca_pct_chg(fill_rate, base_fill_rate), 0))
            + abs(ifNull(rca_pct_chg(ecpm, base_ecpm), 0)),
            0
        ) AS share_requests,
    abs(ifNull(rca_pct_chg(fill_rate, base_fill_rate), 0))
        / nullIf(
            abs(ifNull(req_chg, 0))
            + abs(ifNull(rca_pct_chg(fill_rate, base_fill_rate), 0))
            + abs(ifNull(rca_pct_chg(ecpm, base_ecpm), 0)),
            0
        ) AS share_fill_rate,
    abs(ifNull(rca_pct_chg(ecpm, base_ecpm), 0))
        / nullIf(
            abs(ifNull(req_chg, 0))
            + abs(ifNull(rca_pct_chg(fill_rate, base_fill_rate), 0))
            + abs(ifNull(rca_pct_chg(ecpm, base_ecpm), 0)),
            0
        ) AS share_ecpm,
    ifNull(req_chg, 0) AS rel_requests,
    ifNull(rca_pct_chg(fill_rate, base_fill_rate), 0) AS rel_fill_rate,
    ifNull(rca_pct_chg(ecpm, base_ecpm), 0) AS rel_ecpm,
    toUInt8(ifNull(req_chg, 0) >= 0.15) AS is_recovery_volume,
    toUInt8(ifNull(fill_chg, 0) >= 0.015) AS is_recovery_fill,
    toUInt8(ifNull(ecpm_chg, 0) >= 0.04) AS is_recovery_ecpm,
    now() AS built_at
FROM rca_daily_wow;
