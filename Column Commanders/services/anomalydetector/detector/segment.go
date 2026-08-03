package detector

import (
	"context"
	"fmt"
	"log/slog"
	"math"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector"
)

// SegmentZScoreDetector — Detector D.
// Runs the same robust median/IQR z-score check as the platform-level Detector A,
// but per value of one broad dimension (e.g. every os_version, every region),
// every Detect() cycle — not only after a platform-level detector has already
// fired. This closes the gap documented live against the real dataset: both
// known fill-rate incidents (Android 15, iOS 18.1 x APAC) are invisible at the
// platform aggregate (deviation stays under 4.5%) while being severe within a
// segment — a cascade-only design (segment scanning only inside drilldown,
// triggered by a platform-level signal) can miss a segment that's badly broken
// while the platform average stays quiet. Backed by hourly_by_dimension
// (built by db.Client.MigrateDimensionRollup), so this is a single cheap query
// against a ~tens-of-thousands-of-rows rollup, not a raw ad_events scan.
type SegmentZScoreDetector struct {
	qe        *query.Executor
	dimension string
	cfg       config.DetectionConfig
	logger    *slog.Logger
}

// NewSegmentZScoreDetector creates a SegmentZScoreDetector scoped to one dimension
// (e.g. "os_version", "region" — see drilldown.AllDimensions for valid keys).
func NewSegmentZScoreDetector(qe *query.Executor, dimension string, cfg config.DetectionConfig, logger *slog.Logger) *SegmentZScoreDetector {
	return &SegmentZScoreDetector{qe: qe, dimension: dimension, cfg: cfg, logger: logger}
}

func (d *SegmentZScoreDetector) Name() string { return "segment_zscore_" + d.dimension }

func (d *SegmentZScoreDetector) Metrics() []string {
	return []string{anomalydetector.MetricFillRate, anomalydetector.MetricECPM}
}

func (d *SegmentZScoreDetector) Detect(ctx context.Context, w anomalydetector.Window) ([]anomalydetector.AnomalySignal, error) {
	var sqlStr, timeParam, timeKey string
	if w.Grain() == "daily" {
		sqlStr = query.SegmentDailyBaselineSQL
		timeParam = w.Target().Format("2006-01-02")
		timeKey = "target_date"
	} else {
		sqlStr = query.SegmentHourlyBaselineSQL
		timeParam = w.Target().Format("2006-01-02T15:04:05")
		timeKey = "target_hour"
	}

	rendered := query.RenderSQL(sqlStr, "lookback_weeks", d.cfg.LookbackWeeks, "min_n", d.cfg.MinBaselineN)
	rows, err := d.qe.Rows(ctx, "segment_baseline_"+d.dimension, rendered,
		"dimension_name", d.dimension,
		timeKey, timeParam,
	)
	if err != nil {
		return nil, fmt.Errorf("segment detector (%s): %w", d.dimension, err)
	}

	var signals []anomalydetector.AnomalySignal
	for _, row := range rows {
		seg, _ := row["seg"].(string)
		n := int(segToInt64(row["n"]))

		for _, metric := range d.Metrics() {
			var curr, med, sigma float64
			switch metric {
			case anomalydetector.MetricFillRate:
				curr = segToFloat64(row["curr_fill_rate"])
				med = segToFloat64(row["med_fill_rate"])
				sigma = segToFloat64(row["sigma_fill_rate"])
			case anomalydetector.MetricECPM:
				curr = segToFloat64(row["curr_ecpm"])
				med = segToFloat64(row["med_ecpm"])
				sigma = segToFloat64(row["sigma_ecpm"])
			}

			devPct := float64(0)
			if med != 0 {
				devPct = (curr - med) / med
			}
			z := float64(0)
			if sigma != 0 {
				z = (curr - med) / sigma
			}

			threshold := d.cfg.ZScoreThreshold
			// Same magnitude-floor rationale as the platform detectors: at this
			// row count sigma can be tiny enough that ordinary noise produces a
			// huge z-score, so require both the z-test and a minimum real-world
			// magnitude before alerting.
			isAnomaly := sigma != 0 && math.Abs(z) > threshold && math.Abs(devPct) > d.cfg.MinDeviationPct

			signals = append(signals, anomalydetector.AnomalySignal{
				Metric:       metric,
				Window:       w,
				DetectorID:   "segment_zscore",
				CurrentVal:   curr,
				BaselineVal:  med,
				ZScore:       z,
				DeviationPct: devPct,
				Severity:     severityFromZ(math.Abs(z), threshold),
				IsAnomaly:    isAnomaly,
				BaselineN:    n,
				Dimension:    d.dimension,
				Segment:      seg,
			})
		}
	}
	return signals, nil
}

func segToFloat64(v any) float64 {
	switch t := v.(type) {
	case float64:
		return t
	case float32:
		return float64(t)
	case int64:
		return float64(t)
	case uint64:
		return float64(t)
	case int:
		return float64(t)
	}
	return 0
}

func segToInt64(v any) int64 {
	switch t := v.(type) {
	case int64:
		return t
	case uint64:
		return int64(t)
	case int:
		return int64(t)
	case float64:
		return int64(t)
	}
	return 0
}
