package investigation

import (
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/services/anomalydetector"
)

type QueryRequest struct {
	Purpose         string   `json:"purpose"`
	SQL             string   `json:"sql"`
	ExpectedColumns []string `json:"expected_columns"`
}

type ValidatedQuery struct {
	Purpose         string
	SQL             string
	ExpectedColumns []string
}

type Validator struct {
	cfg config.DetectionConfig
}

func NewValidator(cfg config.DetectionConfig) *Validator { return &Validator{cfg: cfg} }

var tablePattern = regexp.MustCompile(`(?i)\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_\-.]*)`)
var ctePattern = regexp.MustCompile(`(?i)(?:\bwith|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(`)
var limitPattern = regexp.MustCompile(`(?i)\blimit\s+(\d+)\b`)

var approvedTables = map[string]struct{}{
	"ad_events": {}, "apps": {}, "advertisers": {}, "geo_device": {},
	"metrics_global_1m": {}, "metrics_global_1h": {},
}

func (v *Validator) Validate(request QueryRequest, mode anomalydetector.DetectionMode) (ValidatedQuery, error) {
	sql := strings.TrimSpace(request.SQL)
	lower := strings.ToLower(sql)
	if strings.TrimSpace(request.Purpose) == "" {
		return ValidatedQuery{}, errors.New("query purpose is required")
	}
	if len(request.ExpectedColumns) == 0 {
		return ValidatedQuery{}, errors.New("expected_columns is required")
	}
	if !(strings.HasPrefix(lower, "select ") || strings.HasPrefix(lower, "with ") || strings.HasPrefix(lower, "explain ")) {
		return ValidatedQuery{}, errors.New("only SELECT, WITH, or EXPLAIN queries are allowed")
	}
	if strings.Contains(sql, ";") || strings.Contains(lower, "--") || strings.Contains(lower, "/*") {
		return ValidatedQuery{}, errors.New("comments and multiple statements are not allowed")
	}
	for _, blocked := range []string{
		" insert ", " update ", " delete ", " drop ", " alter ", " truncate ", " create ",
		" attach ", " detach ", " optimize ", " system ", " grant ", " revoke ",
		" url(", " remote(", " remotesecure(", " s3(", " file(", " hdfs(", " mysql(", " postgresql(",
		" settings ", " into outfile", " format ",
	} {
		if strings.Contains(" "+lower+" ", blocked) {
			return ValidatedQuery{}, fmt.Errorf("query contains blocked construct %q", strings.TrimSpace(blocked))
		}
	}
	if regexp.MustCompile(`(?i)\bselect\s+\*`).MatchString(sql) {
		return ValidatedQuery{}, errors.New("SELECT * is not allowed")
	}
	if regexp.MustCompile(`(?i)\bavg\s*\(\s*(fill_rate|render_rate|ctr|ecpm|rpr)\s*\)`).MatchString(sql) {
		return ValidatedQuery{}, errors.New("ratios must be recomputed from summed components, not averaged")
	}
	if !strings.Contains(sql, "{window_start:String}") || !strings.Contains(sql, "{window_end:String}") {
		return ValidatedQuery{}, errors.New("query must use bounded window_start and window_end parameters")
	}
	if !strings.Contains(lower, "event_time") && !strings.Contains(lower, "window_start") {
		return ValidatedQuery{}, errors.New("query must constrain a time column")
	}
	if mode == anomalydetector.ModeRealTime && (strings.Contains(lower, "now(") || strings.Contains(lower, "today(")) {
		return ValidatedQuery{}, errors.New("real-time queries cannot use clock-based future data")
	}

	matches := tablePattern.FindAllStringSubmatch(sql, -1)
	if len(matches) == 0 {
		return ValidatedQuery{}, errors.New("query does not reference an approved table")
	}
	cteNames := make(map[string]struct{})
	for _, match := range ctePattern.FindAllStringSubmatch(sql, -1) {
		cteNames[strings.ToLower(match[1])] = struct{}{}
	}
	approvedTableFound := false
	for _, match := range matches {
		table := strings.ToLower(strings.Trim(match[1], "`\""))
		if strings.Contains(table, ".") {
			return ValidatedQuery{}, fmt.Errorf("qualified table %q is not allowed; use the configured database", table)
		}
		if _, ok := approvedTables[table]; ok {
			approvedTableFound = true
			continue
		}
		if _, ok := cteNames[table]; !ok {
			return ValidatedQuery{}, fmt.Errorf("table %q is not approved", table)
		}
	}
	if !approvedTableFound {
		return ValidatedQuery{}, errors.New("query does not reference an approved physical table")
	}

	limits := limitPattern.FindAllStringSubmatch(sql, -1)
	if len(limits) == 0 {
		return ValidatedQuery{}, errors.New("query must include a LIMIT")
	}
	lastLimit, _ := strconv.ParseUint(limits[len(limits)-1][1], 10, 64)
	if lastLimit == 0 || lastLimit > v.cfg.AgentMaxResultRows {
		return ValidatedQuery{}, fmt.Errorf("LIMIT must be between 1 and %d", v.cfg.AgentMaxResultRows)
	}

	hardened := fmt.Sprintf(`%s
SETTINGS max_execution_time = %d, max_rows_to_read = %d, max_bytes_to_read = %d,
	max_result_rows = %d, result_overflow_mode = 'break', timeout_before_checking_execution_speed = 0,
	prefer_column_name_to_alias = 1`,
		sql, max(1, int(v.cfg.AgentQueryTimeout.Seconds())), v.cfg.AgentMaxRowsRead,
		v.cfg.AgentMaxBytesRead, v.cfg.AgentMaxResultRows)
	return ValidatedQuery{Purpose: request.Purpose, SQL: hardened, ExpectedColumns: append([]string(nil), request.ExpectedColumns...)}, nil
}
