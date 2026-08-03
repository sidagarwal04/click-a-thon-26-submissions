package detector

import (
	"context"
	"errors"
	"fmt"
	"log/slog"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/anomalydetector/baseline"
)

// DirectionalCUSUMDetector — Detector C.
// Two-sided rolling-window CUSUM for fill_rate and eCPM.
// Catches persistent multi-window drifts that single z-scores miss.
type DirectionalCUSUMDetector struct {
	qe     *query.Executor
	bp     baseline.Provider
	cfg    config.DetectionConfig
	logger *slog.Logger
}

func NewDirectionalCUSUMDetector(qe *query.Executor, bp baseline.Provider, cfg config.DetectionConfig, logger *slog.Logger) *DirectionalCUSUMDetector {
	return &DirectionalCUSUMDetector{qe: qe, bp: bp, cfg: cfg, logger: logger}
}

func (d *DirectionalCUSUMDetector) Name() string { return "cusum" }
func (d *DirectionalCUSUMDetector) Metrics() []string {
	return []string{anomalydetector.MetricFillRate, anomalydetector.MetricECPM}
}

func (d *DirectionalCUSUMDetector) Detect(ctx context.Context, w anomalydetector.Window) ([]anomalydetector.AnomalySignal, error) {
	blResult, err := d.bp.Compute(ctx, w.Grain(), w.Start)
	if err != nil {
		if errors.Is(err, baseline.ErrInsufficientBaseline) {
			return insufficientSignals(d.Name(), d.Metrics(), w), nil
		}
		return nil, fmt.Errorf("cusum detector: %w", err)
	}

	var signals []anomalydetector.AnomalySignal

	for _, metric := range d.Metrics() {
		bl := baseline.BaselineFor(blResult, metric, d.cfg.MinBaselineN)
		d.logger.Debug("cusum baseline",
			slog.String("metric", metric),
			slog.Float64("sigma", bl.Sigma),
			slog.Int("n", bl.N),
			slog.Bool("sufficient", bl.Sufficient),
		)
		if !bl.Sufficient || bl.Sigma == 0 {
			d.logger.Warn("cusum skipping metric",
				slog.String("metric", metric),
				slog.Float64("sigma", bl.Sigma),
				slog.Bool("sufficient", bl.Sufficient),
			)
			signals = append(signals,
				noopSignal("cusum_down", metric, w),
				noopSignal("cusum_up", metric, w),
			)
			continue
		}

		// Choose daily vs hourly CUSUM based on window grain
		var rendered string
		var qName string
		var timeParam string
		var timeKey string

		if w.Grain() == "daily" {
			// Daily CUSUM: uses daily_global_agg, rolling window in days
			var cusumSQL string
			if metric == anomalydetector.MetricECPM {
				cusumSQL = query.RollingCUSUMDailyECPMSQL
			} else {
				cusumSQL = query.RollingCUSUMDailyFillRateSQL
			}
			rendered = cusumSQL
			qName = "cusum_daily_" + metric
			timeParam = w.Start.Format("2006-01-02")
			timeKey = "target_date"
		} else {
			// Hourly CUSUM
			cusumSQL := query.RollingCUSUMFillRateSQL
			if metric == anomalydetector.MetricECPM {
				cusumSQL = query.RollingCUSUMECPMSQL
			}
			rendered = query.RenderSQL(cusumSQL,
				"rolling_window", d.cfg.CUSUMRollingWindow,
				"lookback_weeks", d.cfg.LookbackWeeks,
				"slack_k", d.cfg.CUSUMSlackK,
			)
			qName = "cusum_hourly_" + metric
			timeParam = w.Start.Format("2006-01-02T15:04:05")
			timeKey = "target_hour"
		}

		rows, err := d.qe.Rows(ctx, qName, rendered,
			timeKey, timeParam,
		)
		if err != nil {
			d.logger.Warn("cusum query failed",
				slog.String("metric", metric),
				slog.Any("error", err),
			)
			continue
		}
		if len(rows) == 0 {
			continue
		}

		last := rows[len(rows)-1]
		cusumDown := toFloat64Ch(last["cusum_down"])
		cusumUp := toFloat64Ch(last["cusum_up"])
		threshold := d.cfg.CUSUMThresholdH * bl.Sigma

		currentVal := blResult.CurrentVals[metric]
		baselineVal := bl.AdjustedMedian(w.Target().Unix(), bl.BaselineMidpointUnix)
		devPct := bl.DeviationPct(currentVal, w.Target().Unix())
		// Same magnitude-floor rationale as the z-score detector: CUSUM
		// accumulating over a rolling window can still cross threshold on
		// persistent-but-tiny noise. Require a minimum real-world magnitude too.
		floor := d.cfg.MinDeviationPct
		if metric == anomalydetector.MetricCTR {
			floor = d.cfg.MinDeviationPctCTR
		}
		magnitudeOK := abs64(devPct) > floor

		signals = append(signals,
			anomalydetector.AnomalySignal{
				Metric:       metric,
				Window:       w,
				DetectorID:   "cusum_down",
				CurrentVal:   currentVal,
				BaselineVal:  baselineVal,
				CUSUMVal:     cusumDown,
				DeviationPct: devPct,
				IsAnomaly:    cusumDown < -threshold && magnitudeOK,
				Severity:     cusumSeverity(cusumDown, -threshold),
				BaselineN:    bl.N,
			},
			anomalydetector.AnomalySignal{
				Metric:       metric,
				Window:       w,
				DetectorID:   "cusum_up",
				CurrentVal:   currentVal,
				BaselineVal:  baselineVal,
				CUSUMVal:     cusumUp,
				DeviationPct: devPct,
				IsAnomaly:    cusumUp > threshold && magnitudeOK,
				Severity:     cusumSeverity(cusumUp, threshold),
				BaselineN:    bl.N,
			},
		)
	}
	return signals, nil
}

// ── Shared helpers (used by all three detectors) ──────────────────────────────

func severityFromZ(absZ, threshold float64) anomalydetector.Severity {
	if threshold == 0 {
		return anomalydetector.SeverityLow
	}
	ratio := absZ / threshold
	switch {
	case ratio >= 10:
		return anomalydetector.SeverityCrit
	case ratio >= 5:
		return anomalydetector.SeverityHigh
	case ratio >= 2:
		return anomalydetector.SeverityMedium
	default:
		return anomalydetector.SeverityLow
	}
}

func cusumSeverity(val, threshold float64) anomalydetector.Severity {
	if threshold == 0 {
		return anomalydetector.SeverityLow
	}
	absRatio := abs64(val) / abs64(threshold)
	switch {
	case absRatio >= 3:
		return anomalydetector.SeverityCrit
	case absRatio >= 2:
		return anomalydetector.SeverityHigh
	case absRatio >= 1:
		return anomalydetector.SeverityMedium
	default:
		return anomalydetector.SeverityLow
	}
}

func insufficientSignals(detectorID string, metrics []string, w anomalydetector.Window) []anomalydetector.AnomalySignal {
	sigs := make([]anomalydetector.AnomalySignal, 0, len(metrics))
	for _, m := range metrics {
		sigs = append(sigs, noopSignal(detectorID, m, w))
	}
	return sigs
}

func noopSignal(detectorID, metric string, w anomalydetector.Window) anomalydetector.AnomalySignal {
	return anomalydetector.AnomalySignal{
		Metric: metric, Window: w, DetectorID: detectorID, IsAnomaly: false,
	}
}

func toFloat64Ch(v any) float64 {
	if v == nil {
		return 0
	}
	switch t := v.(type) {
	case float64:
		return t
	case float32:
		return float64(t)
	case int64:
		return float64(t)
	}
	return 0
}

func abs64(f float64) float64 {
	if f < 0 {
		return -f
	}
	return f
}
