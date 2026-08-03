package chx

import (
	"context"
	"fmt"
	"io/fs"
	"sort"
	"strings"

	ingest "github.com/sonyliv-clickathon/ingest"
)

// schemaFS carries the DDL into the binary so `sonyliv-ingest schema` works
// from any working directory, including a container with no repo checkout.
var schemaFS = ingest.SchemaFS

// SchemaStatements returns every DDL statement, in file-name order.
//
// Only the TOP LEVEL of sql/ is applied. Files in sql/manual/ are embedded and
// shipped but deliberately skipped, because `e.IsDir()` filters the subdirectory
// out and ReadDir does not recurse. That is the mechanism behind the convention:
//
//	sql/*.sql          converges the schema. Idempotent, safe to re-run, applied
//	                   by `make schema`.
//	sql/manual/*.sql   needs a human: a privilege this service user does not
//	                   hold, a placeholder to substitute, or a data mutation.
//
// The convention exists because two such files had already been written with
// headers saying "not applied by make schema" while sitting in the glob that
// applies everything — 009 would have run CREATE USER with a literal
// '__MCP_PASSWORD__', and 010 an ALTER ... DELETE, on every schema apply.
func SchemaStatements() ([]NamedStatement, error) {
	entries, err := fs.ReadDir(schemaFS, "sql")
	if err != nil {
		return nil, fmt.Errorf("read embedded sql: %w", err)
	}
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".sql") {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)

	var out []NamedStatement
	for _, name := range names {
		body, err := schemaFS.ReadFile("sql/" + name)
		if err != nil {
			return nil, fmt.Errorf("read %s: %w", name, err)
		}
		for i, stmt := range splitStatements(string(body)) {
			out = append(out, NamedStatement{File: name, Index: i, SQL: stmt})
		}
	}
	return out, nil
}

// NamedStatement is one DDL statement with enough provenance to report which
// file and position failed.
type NamedStatement struct {
	File  string
	Index int
	SQL   string
}

// Summary is the first meaningful line of the statement, for progress output.
func (s NamedStatement) Summary() string {
	for _, line := range strings.Split(s.SQL, "\n") {
		if t := strings.TrimSpace(line); t != "" {
			if len(t) > 96 {
				return t[:93] + "..."
			}
			return t
		}
	}
	return "(empty)"
}

// Render substitutes the DDL placeholders for this connection.
//
// {{db}} keeps the schema portable: the project targets `default` today, and
// moving to a dedicated database is a config change rather than a rewrite.
// {{ch_user}} / {{ch_password}} exist only for the content dictionary's SOURCE
// clause; pass redactSecrets when the output will be printed.
func (c *Client) Render(sql string, redactSecrets bool) string {
	password := c.password
	if redactSecrets {
		password = "********"
	}
	r := strings.NewReplacer(
		"{{db}}", c.Database,
		"{{ch_user}}", escapeSQLString(c.user),
		"{{ch_password}}", escapeSQLString(password),
	)
	return r.Replace(sql)
}

// escapeSQLString escapes a value for a single-quoted SQL literal.
func escapeSQLString(v string) string {
	return strings.NewReplacer(`\`, `\\`, `'`, `\'`).Replace(v)
}

// ApplySchema executes every DDL statement in order. All statements are
// idempotent (IF NOT EXISTS / OR REPLACE), so this is safe to re-run.
func (c *Client) ApplySchema(ctx context.Context, log func(string)) error {
	stmts, err := SchemaStatements()
	if err != nil {
		return err
	}
	for _, s := range stmts {
		if log != nil {
			log(fmt.Sprintf("  %s[%d] %s", s.File, s.Index, c.Render(s.Summary(), true)))
		}
		if err := c.Conn.Exec(ctx, c.Render(s.SQL, false)); err != nil {
			// Redact before surfacing: a failing CREATE DICTIONARY would
			// otherwise print the password in the error.
			return fmt.Errorf("%s statement %d: %w\n--- SQL ---\n%s",
				s.File, s.Index, err, c.Render(s.SQL, true))
		}
	}
	return nil
}

// splitStatements splits a SQL file on top-level semicolons.
//
// It is comment- and literal-aware because the DDL is heavily commented and
// those comments contain both semicolons and quote characters; a naive
// strings.Split(sql, ";") mangles them.
func splitStatements(sql string) []string {
	var (
		out   []string
		cur   strings.Builder
		runes = []rune(sql)

		inLineComment  bool
		inBlockComment bool
		quote          rune // 0 when not inside a literal
	)

	flush := func() {
		if s := strings.TrimSpace(cur.String()); s != "" {
			out = append(out, s)
		}
		cur.Reset()
	}

	for i := 0; i < len(runes); i++ {
		c := runes[i]
		var next rune
		if i+1 < len(runes) {
			next = runes[i+1]
		}

		switch {
		case inLineComment:
			if c == '\n' {
				inLineComment = false
				cur.WriteRune(c)
			}
		case inBlockComment:
			if c == '*' && next == '/' {
				inBlockComment = false
				i++
			}
		case quote != 0:
			cur.WriteRune(c)
			if c == '\\' && next != 0 {
				cur.WriteRune(next)
				i++
				break
			}
			if c == quote {
				quote = 0
			}
		case c == '-' && next == '-':
			inLineComment = true
			i++
		case c == '/' && next == '*':
			inBlockComment = true
			i++
		case c == '\'' || c == '`' || c == '"':
			quote = c
			cur.WriteRune(c)
		case c == ';':
			flush()
		default:
			cur.WriteRune(c)
		}
	}
	flush()
	return out
}
