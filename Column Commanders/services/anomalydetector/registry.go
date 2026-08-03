package anomalydetector

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"strings"
)

// MetricKind describes how a metric must be rolled up. Ratio metrics retain
// their additive components and divide only after all rows are summed.
type MetricKind string

const (
	MetricAdditive    MetricKind = "additive"
	MetricRatio       MetricKind = "ratio"
	MetricScaledRatio MetricKind = "scaled_ratio"
)

// AggregateColumn is a column exposed by both global rollup tables. Keeping
// this as a closed set prevents metric configuration from becoming raw SQL.
type AggregateColumn string

const (
	ColumnRequests    AggregateColumn = "requests"
	ColumnFills       AggregateColumn = "fills"
	ColumnImpressions AggregateColumn = "impressions"
	ColumnClicks      AggregateColumn = "clicks"
	ColumnRevenue     AggregateColumn = "revenue"
)

var allowedAggregateColumns = map[AggregateColumn]struct{}{
	ColumnRequests:    {},
	ColumnFills:       {},
	ColumnImpressions: {},
	ColumnClicks:      {},
	ColumnRevenue:     {},
}

// MetricDefinition is the validated, data-only representation of one metric.
// Threshold is a fractional change (0.05 means five percent).
type MetricDefinition struct {
	Name               string
	Kind               MetricKind
	Numerator          AggregateColumn
	Denominator        AggregateColumn
	Scale              float64
	Threshold          float64
	MinimumDenominator uint64
	MinimumRequests    uint64
}

func (d MetricDefinition) Validate() error {
	if strings.TrimSpace(d.Name) == "" {
		return errors.New("metric name is required")
	}
	if _, ok := allowedAggregateColumns[d.Numerator]; !ok {
		return fmt.Errorf("metric %s: unsupported numerator %q", d.Name, d.Numerator)
	}
	if d.Threshold <= 0 {
		return fmt.Errorf("metric %s: threshold must be positive", d.Name)
	}

	switch d.Kind {
	case MetricAdditive:
		if d.Denominator != "" {
			return fmt.Errorf("metric %s: additive metric cannot have a denominator", d.Name)
		}
		if d.Scale != 0 && d.Scale != 1 {
			return fmt.Errorf("metric %s: additive metric cannot be scaled", d.Name)
		}
	case MetricRatio, MetricScaledRatio:
		if _, ok := allowedAggregateColumns[d.Denominator]; !ok {
			return fmt.Errorf("metric %s: unsupported denominator %q", d.Name, d.Denominator)
		}
		if d.Numerator == d.Denominator {
			return fmt.Errorf("metric %s: numerator and denominator must differ", d.Name)
		}
		if d.Kind == MetricRatio && d.Scale != 0 && d.Scale != 1 {
			return fmt.Errorf("metric %s: ratio scale must be one", d.Name)
		}
		if d.Kind == MetricScaledRatio && d.Scale <= 0 {
			return fmt.Errorf("metric %s: scaled ratio requires a positive scale", d.Name)
		}
	default:
		return fmt.Errorf("metric %s: unsupported kind %q", d.Name, d.Kind)
	}

	return nil
}

// SQLExpression compiles a metric from the closed aggregate-column set. The
// returned expression is safe to embed in trusted scanner SQL.
func (d MetricDefinition) SQLExpression() (string, error) {
	if err := d.Validate(); err != nil {
		return "", err
	}

	numerator := fmt.Sprintf("sum(%s)", d.Numerator)
	if d.Kind == MetricAdditive {
		return numerator, nil
	}
	if d.Kind == MetricScaledRatio {
		numerator = fmt.Sprintf("%s * %s", numerator, formatScale(d.Scale))
	}
	return fmt.Sprintf("%s / nullIf(sum(%s), 0)", numerator, d.Denominator), nil
}

func formatScale(scale float64) string {
	return strings.TrimRight(strings.TrimRight(fmt.Sprintf("%.9f", scale), "0"), ".")
}

// MetricRegistry holds immutable metric definitions indexed by name.
type MetricRegistry struct {
	definitions map[string]MetricDefinition
}

func NewMetricRegistry(definitions []MetricDefinition) (*MetricRegistry, error) {
	if len(definitions) == 0 {
		return nil, errors.New("metric registry cannot be empty")
	}

	items := make(map[string]MetricDefinition, len(definitions))
	for _, definition := range definitions {
		if err := definition.Validate(); err != nil {
			return nil, err
		}
		if _, exists := items[definition.Name]; exists {
			return nil, fmt.Errorf("duplicate metric %q", definition.Name)
		}
		items[definition.Name] = definition
	}
	return &MetricRegistry{definitions: items}, nil
}

func (r *MetricRegistry) Get(name string) (MetricDefinition, bool) {
	definition, ok := r.definitions[name]
	return definition, ok
}

func (r *MetricRegistry) Definitions() []MetricDefinition {
	definitions := make([]MetricDefinition, 0, len(r.definitions))
	for _, definition := range r.definitions {
		definitions = append(definitions, definition)
	}
	sort.Slice(definitions, func(i, j int) bool { return definitions[i].Name < definitions[j].Name })
	return definitions
}

// Checksum changes whenever the effective registry changes and can therefore
// invalidate compiled query templates safely.
func (r *MetricRegistry) Checksum() string {
	hash := sha256.New()
	for _, definition := range r.Definitions() {
		_, _ = fmt.Fprintf(hash, "%s|%s|%s|%s|%.9f|%.9f|%d|%d\n",
			definition.Name,
			definition.Kind,
			definition.Numerator,
			definition.Denominator,
			definition.Scale,
			definition.Threshold,
			definition.MinimumDenominator,
			definition.MinimumRequests,
		)
	}
	return hex.EncodeToString(hash.Sum(nil))
}

// DefaultMetricRegistry returns the seven metrics in the architecture. These
// defaults will later be overlaid by validated deployment configuration.
func DefaultMetricRegistry() (*MetricRegistry, error) {
	return NewMetricRegistry([]MetricDefinition{
		{Name: MetricRequests, Kind: MetricAdditive, Numerator: ColumnRequests, Threshold: 0.05, MinimumRequests: 1000},
		{Name: MetricRevenue, Kind: MetricAdditive, Numerator: ColumnRevenue, Threshold: 0.05, MinimumRequests: 1000},
		{Name: MetricFillRate, Kind: MetricRatio, Numerator: ColumnFills, Denominator: ColumnRequests, Scale: 1, Threshold: 0.05, MinimumDenominator: 1000},
		{Name: MetricRenderRate, Kind: MetricRatio, Numerator: ColumnImpressions, Denominator: ColumnFills, Scale: 1, Threshold: 0.05, MinimumDenominator: 1000},
		{Name: MetricCTR, Kind: MetricRatio, Numerator: ColumnClicks, Denominator: ColumnImpressions, Scale: 1, Threshold: 0.05, MinimumDenominator: 500},
		{Name: MetricECPM, Kind: MetricScaledRatio, Numerator: ColumnRevenue, Denominator: ColumnImpressions, Scale: 1000, Threshold: 0.05, MinimumDenominator: 500},
		{Name: MetricRPR, Kind: MetricRatio, Numerator: ColumnRevenue, Denominator: ColumnRequests, Scale: 1, Threshold: 0.05, MinimumDenominator: 1000},
	})
}
