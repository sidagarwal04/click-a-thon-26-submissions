// Package ingest is the module root. It exists to embed the DDL in sql/ into
// every binary, so `sonyliv-ingest schema` works without a repo checkout while
// the SQL itself stays in a plain, readable directory rather than buried inside
// an internal package.
package ingest

import "embed"

// SchemaFS holds the ClickHouse DDL, applied in file-name order. Every
// statement is idempotent, so applying it repeatedly is safe.
//
//go:embed all:sql
var SchemaFS embed.FS
