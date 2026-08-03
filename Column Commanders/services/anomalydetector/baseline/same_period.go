package baseline

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"sync"
	"time"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/db"
	"clickhouse-go-service/internal/query"
)

// Metric name constants — duplicated here to avoid importing anomalydetector (cycle prevention).
const (
	metricFillRate = "fill_rate"
	metricECPM     = "ecpm"
	metricCTR      = "ctr"
	metricRequests = "requests"
	metricRevenue  = "revenue"
)

var allMetrics = []string{metricRevenue, metricFillRate, metricECPM, metricCTR, metricRequests}

// SamePeriodBaselineProvider computes baselines by comparing against prior
// same-weekday, same-hour-of-day windows.
type SamePeriodBaselineProvider struct {
	qe     *query.Executor
	cfg    config.DetectionConfig
	logger *slog.Logger
}

// NewSamePeriodProvider creates a SamePeriodBaselineProvider.
func NewSamePeriodProvider(qe *query.Executor, cfg config.DetectionConfig, logger *slog.Logger) *SamePeriodBaselineProvider {
	return &SamePeriodBaselineProvider{qe: qe, cfg: cfg, logger: logger}
}

// ── Per-run baseline cache via context ────────────────────────────────────────

type cacheKey struct{}

type cacheEntry struct {
	mu    sync.RWMutex
	items map[string]ComputeResult // key: grain+"|"+unix
}

// WithCache injects a fresh per-run cache into the context.
// Call once at DetectionEngine.Detect() start so all detectors share one SQL round-trip.
func WithCache(ctx context.Context) context.Context {
	return context.WithValue(ctx, cacheKey{}, &cacheEntry{items: make(map[string]ComputeResult)})
}

func cacheKeyStr(grain string, windowEnd time.Time) string {
	return grain + "|" + fmt.Sprintf("%d", windowEnd.Unix())
}

func fromCache(ctx context.Context, grain string, windowEnd time.Time) (ComputeResult, bool) {
	c, ok := ctx.Value(cacheKey{}).(*cacheEntry)
	if !ok {
		return ComputeResult{}, false
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	r, found := c.items[cacheKeyStr(grain, windowEnd)]
	return r, found
}

func toCache(ctx context.Context, grain string, windowEnd time.Time, r ComputeResult) {
	c, ok := ctx.Value(cacheKey{}).(*cacheEntry)
	if !ok {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items[cacheKeyStr(grain, windowEnd)] = r
}

// ── Compute ───────────────────────────────────────────────────────────────────

// Compute fetches baseline stats + current values for the given window grain and end time.
func (p *SamePeriodBaselineProvider) Compute(ctx context.Context, grain string, windowEnd time.Time) (ComputeResult, error) {
	if r, ok := fromCache(ctx, grain, windowEnd); ok {
		return r, nil
	}

	var (
		sqlStr    string
		timeParam string
		paramName string
	)
	switch grain {
	case "daily":
		sqlStr = query.DailyZScoreBaselineSQL
		timeParam = windowEnd.Format("2006-01-02")
		paramName = "target_date"
	default:
		sqlStr = query.HourlyZScoreBaselineSQL
		timeParam = windowEnd.Format("2006-01-02T15:04:05")
		paramName = "target_hour"
	}

	// Pre-render integer params to avoid type mismatch with native driver.
	// Only the date/time string stays as a named binding.
	// Revenue is the key V1 metric and the existing V1 algorithm starts with two
	// same-period observations. Fetch at that floor; each detector still applies
	// its own required N through BaselineFor, so requests and ratio metrics retain
	// the configured (normally three-period) requirement.
	queryMinN := p.cfg.MinBaselineN
	if queryMinN > 2 {
		queryMinN = 2
	}
	rendered := query.RenderSQL(sqlStr,
		"lookback_weeks", p.cfg.LookbackWeeks,
		"min_n", queryMinN,
	)
	row, err := p.qe.Row(ctx, "baseline_"+grain, rendered,
		paramName, timeParam,
	)
	if err != nil {
		if errors.Is(err, db.ErrNoRows) {
			return ComputeResult{}, ErrInsufficientBaseline
		}
		return ComputeResult{}, fmt.Errorf("baseline compute: %w", err)
	}

	n := int(toInt64(row["n"]))
	if n < queryMinN {
		return ComputeResult{}, ErrInsufficientBaseline
	}

	midpointUnix := toInt64(row["baseline_midpoint_unix"])
	trendSlope := toFloat64(row["trend_slope"])

	// Current values for all metrics
	currVals := map[string]float64{
		metricRevenue:  toFloat64(row["curr_revenue"]),
		metricFillRate: toFloat64(row["curr_fill_rate"]),
		metricECPM:     toFloat64(row["curr_ecpm"]),
		metricCTR:      toFloat64(row["curr_ctr"]),
		metricRequests: toFloat64(row["curr_requests"]),
	}

	// Encode per-metric baseline stats as float64 entries in the same map
	type colPair struct{ med, sigma string }
	cols := map[string]colPair{
		metricRevenue:  {"med_revenue", "sigma_revenue"},
		metricFillRate: {"med_fill_rate", "sigma_fill_rate"},
		metricECPM:     {"med_ecpm", "sigma_ecpm"},
		metricCTR:      {"med_ctr", "sigma_ctr"},
		metricRequests: {"med_requests", "sigma_requests"},
	}
	for metric, cp := range cols {
		currVals["bl:med:"+metric] = toFloat64(row[cp.med])
		currVals["bl:sigma:"+metric] = toFloat64(row[cp.sigma])
	}
	currVals["bl:n"] = float64(n)
	currVals["bl:midpoint"] = float64(midpointUnix)
	currVals["bl:slope:"+metricRequests] = trendSlope
	currVals["bl:midpoint:"+metricRequests] = float64(midpointUnix)

	// Representative Baseline struct (fill_rate)
	bl := Baseline{
		Metric:               metricFillRate,
		Median:               currVals["bl:med:"+metricFillRate],
		IQR:                  currVals["bl:sigma:"+metricFillRate] * 1.35,
		Sigma:                currVals["bl:sigma:"+metricFillRate],
		TrendSlope:           0,
		BaselineMidpointUnix: midpointUnix,
		N:                    n,
		Sufficient:           n >= p.cfg.MinBaselineN,
	}

	result := ComputeResult{Baseline: bl, CurrentVals: currVals}
	toCache(ctx, grain, windowEnd, result)
	return result, nil
}

// BaselineFor extracts a metric-specific Baseline from a ComputeResult.
func BaselineFor(r ComputeResult, metric string, minN int) Baseline {
	med := r.CurrentVals["bl:med:"+metric]
	sigma := r.CurrentVals["bl:sigma:"+metric]
	n := int(r.CurrentVals["bl:n"])
	mp := int64(r.CurrentVals["bl:midpoint"])
	slope := float64(0)
	if metric == metricRequests {
		slope = r.CurrentVals["bl:slope:"+metricRequests]
		mp = int64(r.CurrentVals["bl:midpoint:"+metricRequests])
	}
	return Baseline{
		Metric:               metric,
		Median:               med,
		IQR:                  sigma * 1.35,
		Sigma:                sigma,
		TrendSlope:           slope,
		BaselineMidpointUnix: mp,
		N:                    n,
		Sufficient:           n >= minN,
	}
}

// ── Type conversion helpers ───────────────────────────────────────────────────

func toFloat64(v any) float64 {
	if v == nil {
		return 0
	}
	switch t := v.(type) {
	case float64:
		if math.IsNaN(t) || math.IsInf(t, 0) {
			return 0
		}
		return t
	case float32:
		if math.IsNaN(float64(t)) {
			return 0
		}
		return float64(t)
	case int64:
		return float64(t)
	case int32:
		return float64(t)
	case int:
		return float64(t)
	case uint64:
		return float64(t)
	case uint32:
		return float64(t)
	case uint8:
		return float64(t)
	case time.Time:
		// time.Time appears in UInt64 timestamp columns sometimes
		return float64(t.Unix())
	}
	return 0
}

func toInt64(v any) int64 {
	if v == nil {
		return 0
	}
	switch t := v.(type) {
	case int64:
		return t
	case int32:
		return int64(t)
	case int:
		return int64(t)
	case uint64:
		return int64(t)
	case uint32:
		return int64(t)
	case float64:
		return int64(t)
	case float32:
		return int64(t)
	case time.Time:
		return t.Unix()
	}
	return 0
}
