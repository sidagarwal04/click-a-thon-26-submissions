package drilldown

import "time"

// FactorDelta captures one revenue-identity factor's change.
type FactorDelta struct {
	Current  float64
	Baseline float64
	DeltaPct float64 // (current - baseline) / baseline
	IsGuilty bool
}

// FactorDecomposition shows how each revenue factor changed.
// Revenue = Requests × Fill rate × Render rate × eCPM / 1000 — render_rate is
// kept separate from fill_rate/ecpm so a render-failure incident (fills
// succeed, ad doesn't render) isn't misattributed to either of them.
type FactorDecomposition struct {
	Requests     FactorDelta
	FillRate     FactorDelta
	RenderRate   FactorDelta
	ECPM         FactorDelta
	Revenue      FactorDelta
	GuiltyFactor string   // "fill_rate" | "render_rate" | "ecpm" | "requests" | "mixed"
	RuledOut     []string // factors that did not meet their guilt threshold
}

// SegmentFinding is one dimension segment that contributed to the anomaly.
type SegmentFinding struct {
	Dimension       string
	Segment         string
	Metric          string
	CurrentValue    float64
	BaselineValue   float64
	Delta           float64
	ContributionPct float64
	ColdStart       bool    // true if this segment has no history in one of the two periods
	ZScore          float64 // from bottom-up segment scan; 0 if not computed
	QuerySQL        string  // the SQL that produced this finding (for traceability)
}

// HoldOutResult verifies the winning segment by recomputing the guilty metric
// with it excluded. If the segment is truly the cause, the excluded-population
// value should revert to (near) baseline rather than staying anomalous.
type HoldOutResult struct {
	Dimension       string
	ExcludedSegment string
	ExcludingValue  float64 // metric value with the segment excluded, current period
	ExcludingBase   float64 // metric value with the segment excluded, baseline period
	DeviationPct    float64 // (ExcludingValue - ExcludingBase) / ExcludingBase
	Reverted        bool    // true if the excluded-population deviation is within the revert threshold
}

// PairwiseFinding narrows an over-broad single-dimension claim down to the
// precise two-dimension intersection responsible (the Simpson's-paradox
// correction: two independently-high-EP single dimensions can be two views of
// the same, smaller, event rather than two separate causes).
type PairwiseFinding struct {
	Dim1, Value1  string
	Dim2, Value2  string
	CurrentValue  float64
	BaselineValue float64
	CurrentN      int64
	QuerySQL      string
}

// DrillDownResult is the complete output of an investigation.
type DrillDownResult struct {
	AnomalyDate     string
	BaselineDate    string
	Decomposition   FactorDecomposition
	CulpritSegments []SegmentFinding
	RuledOutDims    []string
	HoldOut         *HoldOutResult   // nil if no culprit was found to verify
	Pairwise        *PairwiseFinding // nil unless the top 2 culprits triggered an intersection check
	// Classification is "global" (no segment stands out), "single-segment"
	// (one dimension's value explains it), or "intersection" (only the pairwise
	// combination does — see Pairwise). CompletenessScore is the top culprit's
	// |contribution_pct| — since a dimension's segments fully partition traffic,
	// this approximates how much of the platform-wide change is explained,
	// surfacing a low value as its own signal that a second cause may be present.
	Classification    string
	CompletenessScore float64
	AllQueries        []string
	ExecutionTime     time.Duration
}

// DimensionConfig describes how to join and filter for a drilldown dimension.
type DimensionConfig struct {
	Key              string
	DimCol           string // SQL column expression, e.g. "g.region"
	FromClause       string // e.g. "FROM ad_events e INNER JOIN ..."
	FilledOnlyFilter string // "" or "AND e.advertiser_id != ''"
	JoinFamily       string // "" | "apps" | "advertisers" | "geo" — lets CombinedFromClause merge two dims' joins generically
}

// AllDimensions is the canonical list of 9 drilldown dimensions.
// Note: JOIN not FULL OUTER JOIN — all dimension values appear every day (verified).
var AllDimensions = []DimensionConfig{
	{
		Key:        "ad_format",
		DimCol:     "e.ad_format",
		FromClause: "FROM ad_events e",
	},
	{
		Key:        "app_category",
		DimCol:     "a.category",
		FromClause: "FROM ad_events e INNER JOIN apps a ON e.app_id = a.app_id",
		JoinFamily: "apps",
	},
	{
		Key:        "publisher_tier",
		DimCol:     "a.publisher_tier",
		FromClause: "FROM ad_events e INNER JOIN apps a ON e.app_id = a.app_id",
		JoinFamily: "apps",
	},
	{
		Key:              "adv_vertical",
		DimCol:           "v.vertical",
		FromClause:       "FROM ad_events e INNER JOIN advertisers v ON e.advertiser_id = v.advertiser_id",
		FilledOnlyFilter: "AND e.advertiser_id != ''",
		JoinFamily:       "advertisers",
	},
	{
		Key:              "campaign_type",
		DimCol:           "v.campaign_type",
		FromClause:       "FROM ad_events e INNER JOIN advertisers v ON e.advertiser_id = v.advertiser_id",
		FilledOnlyFilter: "AND e.advertiser_id != ''",
		JoinFamily:       "advertisers",
	},
	{
		Key:        "region",
		DimCol:     "g.region",
		FromClause: "FROM ad_events e INNER JOIN geo_device g ON e.geo_device_id = g.geo_device_id",
		JoinFamily: "geo",
	},
	{
		Key:        "country",
		DimCol:     "g.country",
		FromClause: "FROM ad_events e INNER JOIN geo_device g ON e.geo_device_id = g.geo_device_id",
		JoinFamily: "geo",
	},
	{
		Key:        "device_model",
		DimCol:     "g.device_model",
		FromClause: "FROM ad_events e INNER JOIN geo_device g ON e.geo_device_id = g.geo_device_id",
		JoinFamily: "geo",
	},
	{
		Key:        "os_version",
		DimCol:     "g.os_version",
		FromClause: "FROM ad_events e INNER JOIN geo_device g ON e.geo_device_id = g.geo_device_id",
		JoinFamily: "geo",
	},
}

// CombinedFromClause merges two dimensions' joins into one FROM clause, so a
// pairwise/intersection query can filter on both dim1 and dim2 regardless of
// which underlying table(s) they come from. Safe because each join family uses
// a distinct, fixed alias (a=apps, v=advertisers, g=geo_device) that never
// collides with another family's alias.
func CombinedFromClause(dim1, dim2 DimensionConfig) (fromClause, filledOnlyFilter string) {
	families := map[string]bool{}
	if dim1.JoinFamily != "" {
		families[dim1.JoinFamily] = true
	}
	if dim2.JoinFamily != "" {
		families[dim2.JoinFamily] = true
	}
	from := "FROM ad_events e"
	if families["apps"] {
		from += " INNER JOIN apps a ON e.app_id = a.app_id"
	}
	if families["advertisers"] {
		from += " INNER JOIN advertisers v ON e.advertiser_id = v.advertiser_id"
		filledOnlyFilter = "AND e.advertiser_id != ''"
	}
	if families["geo"] {
		from += " INNER JOIN geo_device g ON e.geo_device_id = g.geo_device_id"
	}
	return from, filledOnlyFilter
}

// DimsToSkip returns the dimension keys to exclude for a given guilty factor.
// Advertiser dimensions are meaningless for fill_rate (they don't cover unfilled events).
func DimsToSkip(guiltyFactor string) map[string]bool {
	if guiltyFactor == "fill_rate" {
		return map[string]bool{"adv_vertical": true, "campaign_type": true}
	}
	return map[string]bool{}
}

// FindDimConfig returns the DimensionConfig for the given key, or nil.
func FindDimConfig(key string) *DimensionConfig {
	for i := range AllDimensions {
		if AllDimensions[i].Key == key {
			return &AllDimensions[i]
		}
	}
	return nil
}
