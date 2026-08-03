package main

import (
	"fmt"
	"sort"
	"strings"
)

type MetricDefinition struct {
	Name        string   `json:"name"`
	Label       string   `json:"label"`
	Description string   `json:"description"`
	Aliases     []string `json:"aliases"`
	IsRatio     bool     `json:"is_ratio"`
}

var metricDefinitions = []MetricDefinition{
	{Name: "requests", Label: "Requests", Description: "Ad opportunities at the top of the funnel.", Aliases: []string{"requests"}},
	{Name: "fills", Label: "Fills", Description: "Requests answered with an ad.", Aliases: []string{"fills"}},
	{Name: "fill_rate", Label: "Fill Rate", Description: "Share of requests that filled.", Aliases: []string{"fill rate", "fill-rate", "fill_rate"}, IsRatio: true},
	{Name: "impressions", Label: "Impressions", Description: "Ads actually rendered.", Aliases: []string{"impressions"}},
	{Name: "render_rate", Label: "Render Rate", Description: "Share of fills that rendered as impressions.", Aliases: []string{"render rate", "render-rate", "render_rate"}, IsRatio: true},
	{Name: "clicks", Label: "Clicks", Description: "Ads tapped by users.", Aliases: []string{"clicks"}},
	{Name: "ctr", Label: "CTR", Description: "Click-through rate.", Aliases: []string{"ctr", "click through rate", "click-through rate"}, IsRatio: true},
	{Name: "revenue", Label: "Revenue", Description: "Money earned on impressions.", Aliases: []string{"revenue"}},
	{Name: "ecpm", Label: "eCPM", Description: "Effective revenue per 1,000 impressions.", Aliases: []string{"ecpm", "eCPM", "effective cpm"}, IsRatio: true},
	{Name: "rpr", Label: "RPR", Description: "Revenue per request.", Aliases: []string{"rpr", "revenue per request", "revenue_per_request"}, IsRatio: true},
}

var metricLookup = func() map[string]MetricDefinition {
	lookup := make(map[string]MetricDefinition, len(metricDefinitions)*4)
	for _, def := range metricDefinitions {
		lookup[def.Name] = def
		for _, alias := range def.Aliases {
			lookup[normalizeMetricName(alias)] = def
		}
	}
	return lookup
}()

func normalizeMetricName(metric string) string {
	metric = strings.ToLower(strings.TrimSpace(metric))
	metric = strings.ReplaceAll(metric, "-", "_")
	metric = strings.ReplaceAll(metric, " ", "_")
	return metric
}

func resolveMetric(metric string) (MetricDefinition, error) {
	if metric == "" {
		return metricLookup["revenue"], nil
	}

	canonical := normalizeMetricName(metric)
	if def, ok := metricLookup[canonical]; ok {
		return def, nil
	}

	return MetricDefinition{}, fmt.Errorf("unsupported metric: %s", metric)
}

func supportedMetrics() []MetricDefinition {
	defs := make([]MetricDefinition, len(metricDefinitions))
	copy(defs, metricDefinitions)
	sort.Slice(defs, func(i, j int) bool {
		return defs[i].Name < defs[j].Name
	})
	return defs
}

func metricExpr(metric string) (string, error) {
	def, err := resolveMetric(metric)
	if err != nil {
		return "", err
	}

	switch def.Name {
	case "requests":
		return "count()", nil
	case "fills":
		return "sum(is_filled)", nil
	case "fill_rate":
		return "sum(is_filled) / nullIf(count(), 0)", nil
	case "impressions":
		return "sum(is_impression)", nil
	case "render_rate":
		return "sum(is_impression) / nullIf(sum(is_filled), 0)", nil
	case "clicks":
		return "sum(is_click)", nil
	case "ctr":
		return "sum(is_click) / nullIf(sum(is_impression), 0)", nil
	case "revenue":
		return "sum(revenue)", nil
	case "ecpm":
		return "sum(revenue) / nullIf(sum(is_impression), 0) * 1000.0", nil
	case "rpr":
		return "sum(revenue) / nullIf(count(), 0)", nil
	default:
		return "", fmt.Errorf("unsupported metric: %s", metric)
	}
}

func metricColumns(metric string) (currentCol, baseCol, stdCol string, err error) {
	def, err := resolveMetric(metric)
	if err != nil {
		return "", "", "", err
	}

	switch def.Name {
	case "requests":
		return "requests", "req_base", "req_std", nil
	case "fills":
		return "fills", "fills_base", "fills_std", nil
	case "fill_rate":
		return "fill_rate", "fill_rate_base", "fill_rate_std", nil
	case "impressions":
		return "impressions", "impressions_base", "impressions_std", nil
	case "render_rate":
		return "render_rate", "render_rate_base", "render_rate_std", nil
	case "clicks":
		return "clicks", "clicks_base", "clicks_std", nil
	case "ctr":
		return "ctr", "ctr_base", "ctr_std", nil
	case "revenue":
		return "revenue", "rev_base", "rev_std", nil
	case "ecpm":
		return "ecpm", "ecpm_base", "ecpm_std", nil
	case "rpr":
		return "rpr", "rpr_base", "rpr_std", nil
	default:
		return "", "", "", fmt.Errorf("unsupported metric: %s", metric)
	}
}