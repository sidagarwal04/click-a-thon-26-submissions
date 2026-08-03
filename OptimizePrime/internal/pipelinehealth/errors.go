package pipelinehealth

import (
	"database/sql"
	"errors"
)

// isNoRowsErr reports whether err is the clickhouse-go v2 driver's
// zero-rows sentinel — verified against v2.47.0's own source
// (clickhouse_rows.go), which returns database/sql.ErrNoRows from
// Row.Scan rather than a package-local error type.
func isNoRowsErr(err error) bool {
	return errors.Is(err, sql.ErrNoRows)
}
