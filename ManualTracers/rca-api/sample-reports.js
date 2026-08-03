/**
 * Sample RCA reports — ledger numbers match RCA/tests/test_grounding.py (Android 15)
 * and the confirmed iOS 18.1 incident from CLAUDE.md.
 *
 * Template shape mirrors what the RCA agent emits + structured UI sections.
 */

const ANDROID_LEDGER = {
  metric_id: "fill_rate",
  window: { start: "2026-06-23T00:00:00", end: "2026-06-25T23:00:00" },
  dimension_id: "os_version",
  decomposition: null,
  findings: [
    {
      factor: "fill_rate",
      global: { actual: 0.7499, expected: 0.7813, hours: 72, peak_abs_z: 11.4 },
      candidates: [
        {
          dim_name: "os_version",
          dim_value: "Android 15",
          avg_actual: 0.4287,
          avg_expected: 0.7449,
          peak_abs_z: 28.1,
          contribution: 4208.36,
        },
        {
          dim_name: "device_model",
          dim_value: "Galaxy A54",
          avg_actual: 0.412,
          avg_expected: 0.751,
          peak_abs_z: 18.2,
          contribution: 2890.12,
        },
        {
          dim_name: "region",
          dim_value: "EU",
          avg_actual: 0.701,
          avg_expected: 0.788,
          peak_abs_z: 9.8,
          contribution: 1420.55,
        },
        {
          dim_name: "publisher_tier",
          dim_value: "tier_2",
          avg_actual: 0.7792,
          avg_expected: 0.8089,
          peak_abs_z: 6.68,
          contribution: 1790.85,
        },
      ],
      holdout: {
        candidate: [{ dim_name: "os_version", dim_value: "Android 15" }],
        residual_actual: 0.7841,
        residual_delta: 0.0029,
        candidate_delta: -0.3162,
        verdict: "localized",
      },
      interaction: null,
      verdict: "localized",
      ruled_out: [
        "publisher_tier=tier_2",
        "region=EU",
        "device_model=Galaxy A54",
      ],
    },
  ],
  verdict: "localized",
};

const IOS_LEDGER = {
  metric_id: "fill_rate",
  window: { start: "2026-06-29T00:00:00", end: "2026-06-30T23:00:00" },
  dimension_id: "os_version",
  decomposition: null,
  findings: [
    {
      factor: "fill_rate",
      global: { actual: 0.762, expected: 0.785, hours: 48, peak_abs_z: 8.2 },
      candidates: [
        {
          dim_name: "os_version",
          dim_value: "iOS 18.1",
          avg_actual: 0.683,
          avg_expected: 0.78,
          peak_abs_z: 10.6,
          contribution: 2105.4,
        },
        {
          dim_name: "ad_format",
          dim_value: "interstitial",
          avg_actual: 0.71,
          avg_expected: 0.79,
          peak_abs_z: 5.1,
          contribution: 890.2,
        },
      ],
      holdout: {
        candidate: [{ dim_name: "os_version", dim_value: "iOS 18.1" }],
        residual_actual: 0.781,
        residual_delta: -0.004,
        candidate_delta: -0.097,
        verdict: "localized",
      },
      interaction: null,
      verdict: "localized",
      ruled_out: ["ad_format=interstitial"],
    },
  ],
  verdict: "localized",
};

function buildReport(id, ledger, meta) {
  const finding = ledger.findings[0];
  const top = finding.candidates[0];
  return {
    id,
    created_at: meta.created_at,
    title: meta.title,
    status: ledger.verdict,
    trigger: {
      metric_id: ledger.metric_id,
      alert_title: meta.alert_title,
      alert_body: meta.alert_body,
      window: ledger.window,
      dimension_hint: ledger.dimension_id,
      actual: finding.global.actual,
      expected: finding.global.expected,
      peak_abs_z: finding.global.peak_abs_z,
      hours: finding.global.hours,
    },
    sections: {
      what_went_wrong: meta.what_went_wrong,
      why_it_happened: meta.why_it_happened,
      supporting_data_summary: meta.supporting_data_summary,
    },
    ruled_out: finding.ruled_out.map((entry) => {
      const [dim, val] = entry.split("=");
      const candidate = finding.candidates.find(
        (c) => c.dim_name === dim && c.dim_value === val,
      );
      return {
        segment: entry,
        reason: candidate
          ? `Holdout residual (${finding.holdout.residual_delta.toFixed(4)}) did not move with this slice; contribution ${candidate.contribution.toFixed(0)} is a correlated follower of ${top.dim_name}=${top.dim_value}.`
          : "Tested at depth 1; movement did not localize to this segment after conditioning on the primary culprit.",
      };
    }),
    candidates: finding.candidates,
    holdout: finding.holdout,
    ledger,
  };
}

const REPORTS = [
  buildReport("rca-android15-fill", ANDROID_LEDGER, {
    created_at: "2026-06-26T08:15:00Z",
    title: "Global fill rate drop — Android 15 localized",
    alert_title: "fill_rate anomaly (z ≥ 3)",
    alert_body: "Global fill_rate deviated from seasonal baseline for 72 hours starting 2026-06-23.",
    what_went_wrong:
      "Global fill rate fell from an expected 0.7813 to 0.7499 over 72 hours (peak |z| 11.4). The drop is not uniform — one OS slice accounts for most of the gap.",
    why_it_happened:
      "os_version=Android 15 is the localized culprit. Its fill rate averaged 0.4287 vs baseline 0.7449 (peak |z| 28.1), with contribution 4208.36. Holdout conditioning confirmed: residual fill rate returned to 0.7841 (delta 0.0029) while the Android 15 slice alone moved −0.3162.",
    supporting_data_summary:
      "62 depth-1 dimension slices were scanned. Android 15 ranks first by delta_contribution; correlated followers (Galaxy A54, EU) move with the OS upgrade cohort but fail holdout when Android 15 is conditioned out.",
  }),
  buildReport("rca-ios181-fill", IOS_LEDGER, {
    created_at: "2026-07-01T09:42:00Z",
    title: "Fill rate dip — iOS 18.1 cohort",
    alert_title: "fill_rate anomaly (z ≥ 3)",
    alert_body: "Marginal fill_rate alert on os_version dimension; global metric also elevated.",
    what_went_wrong:
      "Global fill rate was 0.762 vs expected 0.785 over 48 hours (peak |z| 8.2). The movement concentrates on a single OS version.",
    why_it_happened:
      "os_version=iOS 18.1 is implicated: actual 0.683 vs expected 0.78 (peak |z| 10.6), contribution 2105.4. Holdout verdict localized — residual 0.781 after removing the iOS 18.1 slice.",
    supporting_data_summary:
      "Depth-1 scan across alert-eligible dimensions. iOS 18.1 is the top contributor; interstitial ad_format is a near-miss but ruled out after holdout.",
  }),
];

module.exports = { REPORTS, ANDROID_LEDGER, IOS_LEDGER };
