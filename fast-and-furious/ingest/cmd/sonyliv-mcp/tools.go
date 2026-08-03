package main

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
)

// The tools. Each curated tool exists because the equivalent hand-written SQL has a trap
// in it that has already been fallen into on this data — summing a peak, blending
// groupings, reading an unsettled minute as zero. run_select_query stays for anything
// they do not cover, guarded and grant-limited.

type handler func(context.Context, json.RawMessage) (*toolResult, error)

func (s *server) registerTools() {
	s.handlers = map[string]handler{}
	s.tools = nil

	s.add(toolDef{
		Name:  "list_serving_tables",
		Title: "List the serving layer",
		Description: "List every table and view this connection can read, with the columns of each " +
			"and what it is for. Nothing outside the serving layer is reachable — there is no " +
			"per-user or per-event data behind this server. Call this first when unsure what exists.",
		InputSchema: obj(nil, nil),
	}, s.listServingTables)

	s.add(toolDef{
		Name:  "data_freshness",
		Title: "Check layer freshness",
		Description: "Report how current each serving layer is. CALL THIS BEFORE CONCLUDING THAT " +
			"VIEWERS DROPPED. The minute layer publishes on a deliberate ~5 minute lag, so the most " +
			"recent minutes are absent rather than empty, and reading them as zero is the most " +
			"common wrong answer this data produces.",
		InputSchema: obj(nil, nil),
	}, s.dataFreshness)

	s.add(toolDef{
		Name:  "viewing_trend",
		Title: "Concurrency over time",
		Description: "Audience size over time: average concurrent viewers and exact peak per bucket. " +
			"The average is time-weighted (sum(active_ms)/bucket_ms), never a mean of peaks. Use " +
			"grouping='total' for overall shape, or a narrower grouping with dim_value to trend one " +
			"slice. Grain may be minute, hour or day.",
		InputSchema: obj(map[string]any{
			"from":      strProp("Window start, UTC. 'YYYY-MM-DD HH:MM:SS' or an ISO timestamp."),
			"to":        strProp("Window end, UTC, exclusive."),
			"grouping":  groupingProp(),
			"dim_value": strProp("Optional: restrict to one slice of that grouping, e.g. 'IPHONE'. Match the dim_values column exactly."),
			"grain":     enumProp("Bucket size.", []string{"minute", "hour", "day"}, "minute"),
		}, []string{"from", "to"}),
	}, s.viewingTrend)

	s.add(toolDef{
		Name:  "peak_and_average",
		Title: "Headline numbers for a window",
		Description: "The two headline figures for a window: exact peak concurrency, and " +
			"time-weighted average concurrency, plus viewer-hours and when the peak occurred. " +
			"A peak is read from a pre-aggregated row, never summed. Reference: the hot hour " +
			"2026-07-26 10:00-11:00Z at grouping='total' is peak 2305, average 855.578199.",
		InputSchema: obj(map[string]any{
			"from":      strProp("Window start, UTC."),
			"to":        strProp("Window end, UTC, exclusive."),
			"grouping":  groupingProp(),
			"dim_value": strProp("Optional: restrict to one slice."),
		}, []string{"from", "to"}),
	}, s.peakAndAverage)

	s.add(toolDef{
		Name:  "rank_dimension",
		Title: "Rank slices within a dimension",
		Description: "Rank the values of one dimension by audience — exact peak, when each peaked, " +
			"and viewer-hours. This is how to answer 'which platform/title/category was biggest', " +
			"and it shows that different slices peak at different instants, which is why peaks " +
			"cannot be summed.",
		InputSchema: obj(map[string]any{
			"from":     strProp("Window start, UTC."),
			"to":       strProp("Window end, UTC, exclusive."),
			"grouping": groupingProp(),
			"order_by": enumProp("Ranking measure.", []string{"peak", "viewer_hours"}, "peak"),
			"limit":    intProp("Rows to return.", 20),
		}, []string{"from", "to", "grouping"}),
	}, s.rankDimension)

	s.add(toolDef{
		Name:  "top_titles",
		Title: "Title leaderboard",
		Description: "The most-watched titles in a window, by peak concurrency and viewer-hours, " +
			"with content type and category. Reads the 'content' grouping, which is 31,537 rows per " +
			"hour — prefer rank_dimension on a narrower grouping when the question is not about titles.",
		InputSchema: obj(map[string]any{
			"from":  strProp("Window start, UTC."),
			"to":    strProp("Window end, UTC, exclusive."),
			"limit": intProp("Titles to return.", 20),
		}, []string{"from", "to"}),
	}, s.topTitles)

	s.add(toolDef{
		Name:  "detect_drops",
		Title: "Find slices that are falling",
		Description: "Find slices whose audience has fallen against their OWN trailing median, which " +
			"is what makes a drop comparable between a slice that runs 4,000 concurrent and one that " +
			"runs 40. Returns only settled minutes above the noise floor, so it will not report the " +
			"publish lag as an outage. retention 1.0 = holding, 0.0 = gone.",
		InputSchema: obj(map[string]any{
			"from":      strProp("Window start, UTC."),
			"to":        strProp("Window end, UTC, exclusive."),
			"grouping":  enumProp("Dimension to watch. Bounded-cardinality groupings only.", []string{"country", "platform", "video type", "category"}, "platform"),
			"threshold": numProp("Retention below which a slice counts as breaching.", 0.7),
		}, []string{"from", "to"}),
	}, s.detectDrops)

	s.add(toolDef{
		Name:  "run_select_query",
		Title: "Run a read-only SELECT",
		Description: "Run an arbitrary read-only SELECT against the serving layer for questions the " +
			"other tools do not cover. Only the serving tables and views are reachable; anything else " +
			"is refused, and the database connection has no write privilege and no access to " +
			"per-user data. Read the sonyliv://serving/guide resource before composing SQL — in " +
			"particular, never SUM a peak, and always filter on grouping.",
		InputSchema: obj(map[string]any{
			"query": strProp("A single SELECT (or WITH ... SELECT) statement."),
			"limit": intProp("Maximum rows returned. A LIMIT is appended when the query has none.", 200),
		}, []string{"query"}),
	}, s.runSelectQuery)
}

func (s *server) add(d toolDef, h handler) {
	s.tools = append(s.tools, d)
	s.handlers[d.Name] = h
}

func (s *server) toolDefs() []toolDef { return s.tools }

// ---------------------------------------------------------------- schema helpers ----

func obj(props map[string]any, required []string) map[string]any {
	if props == nil {
		props = map[string]any{}
	}
	m := map[string]any{"type": "object", "properties": props}
	if len(required) > 0 {
		m["required"] = required
	}
	return m
}

func strProp(desc string) map[string]any {
	return map[string]any{"type": "string", "description": desc}
}

func intProp(desc string, def int) map[string]any {
	return map[string]any{"type": "integer", "description": desc, "default": def}
}

func numProp(desc string, def float64) map[string]any {
	return map[string]any{"type": "number", "description": desc, "default": def}
}

func enumProp(desc string, vals []string, def string) map[string]any {
	return map[string]any{"type": "string", "description": desc, "enum": vals, "default": def}
}

func groupingProp() map[string]any {
	return map[string]any{
		"type": "string",
		"enum": validGroupings,
		"description": "Which pre-aggregated slice to read. MUST be set — the layer holds eleven " +
			"overlapping aggregations of the same traffic, and reading them together overstates " +
			"concurrency several times over. Choose the NARROWEST grouping that answers the " +
			"question: 'total' is 60 rows per hour where 'all dimensions' is 41,845.",
		"default": "total",
	}
}

// The labels materialised by the rollup. Kept in sync with 030_rollup_minute.sql; an
// unknown value is rejected rather than silently returning nothing.
var validGroupings = []string{
	"total", "platform", "country", "platform + country", "content",
	"platform + content", "video type", "platform + video type",
	"app version", "category", "all dimensions",
}

// ------------------------------------------------------------------ arg parsing ----

type args struct {
	raw map[string]any
	err error
}

func parseArgs(b json.RawMessage) *args {
	a := &args{raw: map[string]any{}}
	if len(b) > 0 && string(b) != "null" {
		if err := json.Unmarshal(b, &a.raw); err != nil {
			a.err = fmt.Errorf("malformed arguments: %w", err)
		}
	}
	return a
}

func (a *args) str(key, def string) string {
	if v, ok := a.raw[key].(string); ok && v != "" {
		return v
	}
	return def
}

func (a *args) require(key string) string {
	v := a.str(key, "")
	if v == "" && a.err == nil {
		a.err = fmt.Errorf("%q is required", key)
	}
	return v
}

func (a *args) num(key string, def float64) float64 {
	if v, ok := a.raw[key].(float64); ok {
		return v
	}
	return def
}

func (a *args) intv(key string, def, max int) int {
	v := int(a.num(key, float64(def)))
	if v <= 0 {
		v = def
	}
	if v > max {
		v = max
	}
	return v
}

// grouping validates against the materialised label set, so a typo fails loudly instead
// of returning an empty result the model would read as "no viewers".
func (a *args) grouping(def string) string {
	g := a.str("grouping", def)
	for _, v := range validGroupings {
		if g == v {
			return g
		}
	}
	if a.err == nil {
		a.err = fmt.Errorf("unknown grouping %q; valid values are: %s", g, strings.Join(validGroupings, ", "))
	}
	return def
}
