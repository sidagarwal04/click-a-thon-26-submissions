package main

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

// Tool bodies. Every window is half-open — t >= from AND t < to — because an inclusive
// right edge adds a bucket, which on an hour-long window overstated the average by 4.3%
// when the dashboards made the same mistake.

const dimFilter = "AND (({dim:String} = '') OR (dim_values = {dim:String}))"

func (s *server) listServingTables(ctx context.Context, _ json.RawMessage) (*toolResult, error) {
	var b strings.Builder
	b.WriteString("Serving layer — everything this connection can read.\n")
	b.WriteString("No per-user or per-event data is reachable from here.\n\n")
	for _, r := range servingCatalogue {
		b.WriteString(fmt.Sprintf("## %s\n%s\n", r.name, r.purpose))
		cols, err := s.describe(ctx, r.name)
		if err != nil {
			// A view that fails to describe is worth surfacing rather than hiding: it
			// usually means a grant is missing, which is the thing most likely to be
			// misconfigured on a fresh deployment.
			b.WriteString(fmt.Sprintf("  (columns unavailable: %v)\n\n", err))
			continue
		}
		b.WriteString("  " + strings.Join(cols, ", ") + "\n\n")
	}
	b.WriteString("Groupings available in serving_minute_current: " + strings.Join(validGroupings, ", ") + "\n")
	b.WriteString("\nRead sonyliv://serving/guide before composing SQL.\n")
	return textResult(b.String()), nil
}

func (s *server) describe(ctx context.Context, table string) ([]string, error) {
	// DESCRIBE needs only the SELECT grant on the object, so introspection works without
	// granting the MCP user anything in system.*.
	rows, err := s.ch.Conn.Query(ctx, fmt.Sprintf("DESCRIBE TABLE %s.%s", s.database, table))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var name, typ, defKind, defExpr, comment, codec, ttl string
		if err := rows.Scan(&name, &typ, &defKind, &defExpr, &comment, &codec, &ttl); err != nil {
			return nil, err
		}
		if name == "dim_mask" {
			continue // internal bit field; grouping is its readable 1:1 label
		}
		out = append(out, name+" "+typ)
	}
	return out, rows.Err()
}

func (s *server) dataFreshness(ctx context.Context, _ json.RawMessage) (*toolResult, error) {
	const q = `
SELECT layer,
       toString(watermark_ts)                        AS settled_through_utc,
       dateDiff('second', watermark_ts, now())       AS lag_seconds,
       toString(built_at)                            AS last_built_utc,
       build_ms,
       rows_out
FROM %s.serving_watermark FINAL
ORDER BY layer`
	out, err := s.queryText(ctx, fmt.Sprintf(q, s.database))
	if err != nil {
		return nil, err
	}
	return textResult(out + "\n" +
		"Do not report a decline whose last minute is at or after the 'minute' layer's " +
		"settled_through_utc — those minutes are not yet published, not empty.\n"), nil
}

func (s *server) viewingTrend(ctx context.Context, raw json.RawMessage) (*toolResult, error) {
	a := parseArgs(raw)
	from, to := a.require("from"), a.require("to")
	grouping := a.grouping("total")
	grain := a.str("grain", "minute")
	dim := a.str("dim_value", "")
	if a.err != nil {
		return nil, a.err
	}
	bucket := map[string]string{
		"minute": "minute_start",
		"hour":   "toStartOfHour(minute_start)",
		"day":    "toDate(minute_start)",
	}[grain]
	if bucket == "" {
		return nil, fmt.Errorf("grain must be minute, hour or day; got %q", grain)
	}
	// Divisor is the bucket's own length, so avg_concurrent is a true time-weighted
	// average within each bucket rather than a mean of per-minute means.
	perBucketMs := map[string]string{"minute": "60000.0", "hour": "3600000.0", "day": "86400000.0"}[grain]

	q := fmt.Sprintf(`
SELECT toString(%s)                              AS bucket_utc,
       round(sum(active_ms) / %s, 3)             AS avg_concurrent,
       max(minute_peak)                          AS peak_concurrent,
       round(sum(active_ms) / 3600000.0, 3)      AS viewer_hours
FROM %s.serving_minute_current
WHERE grouping = {grouping:String}
  AND minute_start >= parseDateTimeBestEffort({from:String}, 'UTC')
  AND minute_start <  parseDateTimeBestEffort({to:String}, 'UTC')
  %s
GROUP BY bucket_utc
ORDER BY bucket_utc`, bucket, perBucketMs, s.database, dimFilter)

	out, err := s.queryText(ctx, q,
		named("grouping", grouping), named("from", from), named("to", to), named("dim", dim))
	if err != nil {
		return nil, err
	}
	return textResult(header(grouping, dim, from, to) + out), nil
}

func (s *server) peakAndAverage(ctx context.Context, raw json.RawMessage) (*toolResult, error) {
	a := parseArgs(raw)
	from, to := a.require("from"), a.require("to")
	grouping := a.grouping("total")
	dim := a.str("dim_value", "")
	if a.err != nil {
		return nil, a.err
	}
	// The average divides by the SELECTED window, not by the span of rows that happen to
	// exist, or an idle tail would inflate it. greatest(...,1) keeps an empty window from
	// dividing by zero.
	q := fmt.Sprintf(`
SELECT max(minute_peak)                                    AS exact_peak,
       toString(argMax(minute_start, minute_peak))         AS peaked_at_utc,
       round(sum(active_ms) / greatest(dateDiff('millisecond',
            parseDateTimeBestEffort({from:String}, 'UTC'),
            parseDateTimeBestEffort({to:String}, 'UTC')), 1), 6) AS avg_concurrency,
       round(sum(active_ms) / 3600000.0, 3)                AS viewer_hours,
       count()                                             AS rows_read
FROM %s.serving_minute_current
WHERE grouping = {grouping:String}
  AND minute_start >= parseDateTimeBestEffort({from:String}, 'UTC')
  AND minute_start <  parseDateTimeBestEffort({to:String}, 'UTC')
  %s
HAVING count() > 0`, s.database, dimFilter)

	out, err := s.queryText(ctx, q,
		named("grouping", grouping), named("from", from), named("to", to), named("dim", dim))
	if err != nil {
		return nil, err
	}
	if strings.Contains(out, "(0 rows)") {
		return textResult(header(grouping, dim, from, to) +
			"No rows. Either the window holds no viewers, or it is ahead of the published " +
			"watermark — call data_freshness to tell those apart.\n"), nil
	}
	return textResult(header(grouping, dim, from, to) + out), nil
}

func (s *server) rankDimension(ctx context.Context, raw json.RawMessage) (*toolResult, error) {
	a := parseArgs(raw)
	from, to := a.require("from"), a.require("to")
	grouping := a.grouping("platform")
	limit := a.intv("limit", 20, 500)
	order := "exact_peak"
	if a.str("order_by", "peak") == "viewer_hours" {
		order = "viewer_hours"
	}
	if a.err != nil {
		return nil, a.err
	}
	q := fmt.Sprintf(`
SELECT dim_values,
       max(minute_peak)                              AS exact_peak,
       toString(argMax(minute_start, minute_peak))   AS peaked_at_utc,
       round(sum(active_ms) / 3600000.0, 3)          AS viewer_hours
FROM %s.serving_minute_current
WHERE grouping = {grouping:String}
  AND minute_start >= parseDateTimeBestEffort({from:String}, 'UTC')
  AND minute_start <  parseDateTimeBestEffort({to:String}, 'UTC')
GROUP BY dim_values
ORDER BY %s DESC
LIMIT %d`, s.database, order, limit)

	out, err := s.queryText(ctx, q, named("grouping", grouping), named("from", from), named("to", to))
	if err != nil {
		return nil, err
	}
	return textResult(header(grouping, "", from, to) + out +
		"\npeaked_at_utc differs between rows because slices peak at different instants — " +
		"which is why these peaks must not be added together.\n"), nil
}

func (s *server) topTitles(ctx context.Context, raw json.RawMessage) (*toolResult, error) {
	a := parseArgs(raw)
	from, to := a.require("from"), a.require("to")
	limit := a.intv("limit", 20, 200)
	if a.err != nil {
		return nil, a.err
	}
	q := fmt.Sprintf(`
SELECT title,
       any(video_type)                              AS content_type,
       any(category)                                AS category,
       max(minute_peak)                             AS exact_peak,
       toString(argMax(minute_start, minute_peak))  AS peaked_at_utc,
       round(sum(active_ms) / 3600000.0, 3)         AS viewer_hours
FROM %s.serving_minute_current
WHERE grouping = 'content'
  AND minute_start >= parseDateTimeBestEffort({from:String}, 'UTC')
  AND minute_start <  parseDateTimeBestEffort({to:String}, 'UTC')
GROUP BY title
ORDER BY viewer_hours DESC
LIMIT %d`, s.database, limit)

	out, err := s.queryText(ctx, q, named("from", from), named("to", to))
	if err != nil {
		return nil, err
	}
	return textResult(fmt.Sprintf("grouping=content  window=%s .. %s UTC\n\n", from, to) + out), nil
}

func (s *server) detectDrops(ctx context.Context, raw json.RawMessage) (*toolResult, error) {
	a := parseArgs(raw)
	from, to := a.require("from"), a.require("to")
	grouping := a.str("grouping", "platform")
	threshold := a.num("threshold", 0.7)
	if a.err != nil {
		return nil, a.err
	}
	switch grouping {
	case "country", "platform", "video type", "category":
	default:
		return nil, fmt.Errorf("detect_drops supports bounded-cardinality groupings only "+
			"(country, platform, video type, category); got %q", grouping)
	}
	// has_opinion filters slices under the noise floor; is_settled filters minutes the
	// layer has not published. Without both this reports the publish lag as an outage.
	q := fmt.Sprintf(`
SELECT dim_values,
       count()                                       AS breaching_minutes,
       toString(min(minute_start))                   AS first_breach_utc,
       toString(max(minute_start))                   AS last_breach_utc,
       round(min(retention_sustained), 4)            AS worst_retention,
       round(max(drop_pct), 2)                       AS worst_drop_pct,
       round(min(delta_viewers), 1)                  AS worst_delta_viewers
FROM %s.serving_drop_signal(
        win_from = {from:String}, win_to = {to:String},
        grouping_key = {grouping:String},
        baseline_minutes = 15, min_baseline = 25, persist_minutes = 1)
WHERE has_opinion AND is_settled AND retention_sustained < {threshold:Float64}
GROUP BY dim_values
ORDER BY worst_retention ASC
LIMIT 50`, s.database)

	out, err := s.queryText(ctx, q,
		named("from", from), named("to", to),
		named("grouping", grouping), named("threshold", threshold))
	if err != nil {
		return nil, err
	}
	if strings.Contains(out, "(0 rows)") {
		return textResult(fmt.Sprintf(
			"No slice of %q fell below retention %.2f for two consecutive settled minutes "+
				"between %s and %s UTC.\n\nThat is a real all-clear only if the layer is current — "+
				"check data_freshness, because a stalled pipeline produces this same answer.\n",
			grouping, threshold, from, to)), nil
	}
	return textResult(fmt.Sprintf("grouping=%s  retention < %.2f  window=%s .. %s UTC\n"+
		"retention is measured against each slice's own trailing 15-minute median.\n\n",
		grouping, threshold, from, to) + out), nil
}

var reHasLimit = regexp.MustCompile(`(?i)\blimit\s+\d`)

func (s *server) runSelectQuery(ctx context.Context, raw json.RawMessage) (*toolResult, error) {
	a := parseArgs(raw)
	q := a.require("query")
	limit := a.intv("limit", 200, 10000)
	if a.err != nil {
		return nil, a.err
	}
	if err := validateQuery(q); err != nil {
		return nil, err
	}
	final := strings.TrimSuffix(strings.TrimSpace(q), ";")
	if !reHasLimit.MatchString(final) {
		final = fmt.Sprintf("%s\nLIMIT %d", final, limit)
	}
	out, err := s.queryText(ctx, final)
	if err != nil {
		return nil, err
	}
	return textResult(out), nil
}

func header(grouping, dim, from, to string) string {
	if dim != "" {
		return fmt.Sprintf("grouping=%s  dim_values=%s  window=%s .. %s UTC\n\n", grouping, dim, from, to)
	}
	return fmt.Sprintf("grouping=%s  window=%s .. %s UTC\n\n", grouping, from, to)
}
