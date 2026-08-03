package main

import _ "embed"

// The guide is embedded rather than read from disk so the binary shipped to EC2 carries
// its own knowledge — the same reason the rollup SQL is embedded in sonyliv-ingest.
//
//go:embed knowledge.md
var knowledgeGuide string

// Returned from initialize. Clients place this in front of the model before the first
// tool call, so the two rules that are most expensive to get wrong arrive before any SQL
// does rather than only if the model happens to read a resource.
const knowledgeSummary = `This server exposes SonyLIV's pre-aggregated concurrency serving layer. No per-user or
per-event data is reachable through it.

Two rules govern every correct answer here:

 1. NEVER SUM OR AVERAGE A PEAK. active_ms is additive across dimensions and time;
    ending_concurrency is additive across dimensions at one instant; peaks are additive
    across nothing. Average concurrency is sum(active_ms)/window_ms, never avg(peak).
    Combine peaks over TIME with max(); across DIMENSIONS you cannot combine at all.

 2. ALWAYS FILTER ON grouping. The minute layer holds eleven overlapping aggregations of
    the same traffic. Querying without pinning grouping sums them: measured 9,411.64
    average concurrency where the truth was 855.58. Pick the narrowest grouping that
    answers the question — 'total' is 60 rows per hour, 'all dimensions' is 41,845.

Timestamps are UTC and windows are half-open. The minute layer publishes on a ~5 minute
lag, so recent minutes are ABSENT, not empty — call data_freshness before reporting any
decline. Read the sonyliv://serving/guide resource for the full model.`

type catalogueEntry struct{ name, purpose string }

// What each object is FOR, which is the part a schema dump cannot convey.
var servingCatalogue = []catalogueEntry{
	{"serving_minute_current",
		"  Primary analytical source. 1-minute grain, corrected, published on a ~5min lag.\n" +
			"  Filter on `grouping`; `dim_values` is the readable label for the slice."},
	{"serving_live_total",
		"  Live total concurrency at 10s grain, ~7s behind. Best-effort: aged buckets keep an\n" +
			"  optimistic reading (measured 0.053% high). Use for 'right now', not for analysis."},
	{"serving_live_content",
		"  Live concurrency per title at 10s grain, with title/type/category resolved."},
	{"serving_drop_signal",
		"  Parameterised view. Retention of each slice against its own trailing median.\n" +
			"  Call via the detect_drops tool, which sets the parameters correctly."},
	{"serving_watermark",
		"  How current each layer is. Consult before reading any recent window as a decline."},
	{"serving_watermark_history",
		"  Append-only build history: rollup duration and rows written over time."},
	{"serving_concurrency_minute",
		"  The fact table behind serving_minute_current. Prefer the view — it resolves titles."},
	{"serving_concurrency_live",
		"  The fact table behind the live views. Prefer the views."},
}

type promptBodyT struct{ description, text string }

func promptDefs() []map[string]any {
	return []map[string]any{
		{"name": "viewing-trends", "title": "Analyse viewing trends",
			"description": "How to answer a viewing-trends question against this serving layer without falling into its traps."},
		{"name": "investigate-drop", "title": "Investigate a drop in viewers",
			"description": "Ordered procedure for deciding whether viewers actually fell, and where."},
	}
}

func promptBody(name string) (promptBodyT, bool) {
	switch name {
	case "viewing-trends":
		return promptBodyT{
			description: "How to answer a viewing-trends question against this serving layer.",
			text: `Answer a viewing-trends question about SonyLIV concurrency.

Procedure:
 1. Decide which measure the question actually asks for. "How many were watching" is
    ambiguous: peak concurrent, average concurrent and viewer-hours differ by orders of
    magnitude. Say which you used.
 2. Pick the NARROWEST grouping that answers it. Overall shape -> 'total' (60 rows/hour).
    Per-device -> 'platform'. Per-title -> 'content' (31,537 rows/hour, so only when the
    question is genuinely about titles).
 3. Use peak_and_average for headline numbers, viewing_trend for shape over time,
    rank_dimension to compare slices, top_titles for a leaderboard.
 4. If the window touches the present, call data_freshness first. The minute layer runs
    ~5 minutes behind; unpublished minutes are absent, not zero.
 5. Sanity-check against the reference: hot hour 2026-07-26 10:00-11:00Z at
    grouping='total' is peak 2305, average 855.578199.

Report the measure, the grouping, and the window in UTC, so the number can be reproduced.
Never sum or average a peak.`,
		}, true
	case "investigate-drop":
		return promptBodyT{
			description: "Ordered procedure for investigating a suspected drop in viewers.",
			text: `Investigate whether SonyLIV viewers have dropped, and where.

Procedure, in this order — step 1 is not optional:
 1. data_freshness. If the minute layer's lag is large, recent minutes are unpublished
    and WILL look like zero viewers. A stalled pipeline and an outage are the same shape.
    Rule this out before anything else.
 2. detect_drops on 'platform' — the dimension where a partial failure shows first. Then
    'video type' (is it only live?), 'category', and 'country'. Retention is measured
    against each slice's own trailing median, so a small slice and a large one are
    comparable.
 3. If one slice breaches while others hold, it is a client, device or delivery fault. If
    all breach together, look for a scheduled end-of-broadcast before declaring an
    incident — a baseline-relative detector cannot tell those apart on its own.
 4. Quantify with peak_and_average over the affected window versus the preceding one, at
    the grouping that isolated the fault.

Report which slices breached, how far they fell against their own baseline, when it
started, and whether the layer was current enough for the finding to mean anything.`,
		}, true
	}
	return promptBodyT{}, false
}

func resourceDefs() []map[string]any {
	return []map[string]any{{
		"uri":         "sonyliv://serving/guide",
		"name":        "Serving layer guide",
		"title":       "How to read viewing trends",
		"description": "Schema semantics, the additivity rule, grouping selection and read cost, freshness, reference figures, and query recipes.",
		"mimeType":    "text/markdown",
	}}
}

func resourceBody(uri string) (string, string, bool) {
	if uri == "sonyliv://serving/guide" {
		return knowledgeGuide, "text/markdown", true
	}
	return "", "", false
}
