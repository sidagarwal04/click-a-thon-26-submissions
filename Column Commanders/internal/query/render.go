package query

import (
	"fmt"
	"regexp"
	"strconv"
)

// RenderSQL replaces {paramName:Type} placeholders in sql with their literal values.
// Use this for int and float parameters to avoid type-mismatch errors with the
// native clickhouse-go/v2 driver. String parameters should still use named binding.
//
// Example:
//
//	sql = RenderSQL(sql, "lookback_weeks", 3, "slack_k", 0.5)
//	// {lookback_weeks:Int64} → 3
//	// {slack_k:Float64} → 0.500000
func RenderSQL(sql string, keysAndVals ...any) string {
	for i := 0; i+1 < len(keysAndVals); i += 2 {
		name, ok := keysAndVals[i].(string)
		if !ok {
			continue
		}
		val := keysAndVals[i+1]
		re := regexp.MustCompile(`\{` + regexp.QuoteMeta(name) + `:[^}]+\}`)
		var literal string
		switch v := val.(type) {
		case int:
			literal = strconv.Itoa(v)
		case int64:
			literal = strconv.FormatInt(v, 10)
		case float64:
			literal = fmt.Sprintf("%.6g", v)
		case float32:
			literal = fmt.Sprintf("%.6g", float64(v))
		case string:
			// Strings: single-quote escape — only used when caller explicitly passes string
			literal = "'" + escapeSingleQuote(v) + "'"
		default:
			literal = fmt.Sprintf("%v", v)
		}
		sql = re.ReplaceAllString(sql, literal)
	}
	return sql
}

func escapeSingleQuote(s string) string {
	out := make([]byte, 0, len(s))
	for i := 0; i < len(s); i++ {
		if s[i] == '\'' {
			out = append(out, '\'', '\'')
		} else {
			out = append(out, s[i])
		}
	}
	return string(out)
}
