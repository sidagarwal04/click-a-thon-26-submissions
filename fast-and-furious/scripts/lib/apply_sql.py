#!/usr/bin/env python3
"""Apply a ClickHouse .sql file over HTTPS, one statement at a time.

Exists because the two obvious alternatives both fail here:

  * ClickHouse's HTTP interface executes ONE statement per request, so a
    multi-statement file cannot simply be POSTed.
  * Splitting on ';' with sed/awk breaks on semicolons inside string literals
    and inside comments, and this repo's DDL has both.

Standard library only, so the bootstrap has no pip dependency.

Reads the password from the CLICKHOUSE_PASSWORD environment variable and never
prints it, not even in an error.
"""

from __future__ import annotations

import argparse
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def split_statements(sql: str) -> list[str]:
    """Split on top-level semicolons.

    Tracks single-quoted strings (with '' and backslash escapes), backquoted
    identifiers, double-quoted identifiers, -- line comments and /* */ block
    comments, so a ';' inside any of them does not end a statement.
    """
    out: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    in_squote = in_dquote = in_backtick = False
    in_line_comment = in_block_comment = False

    while i < n:
        c = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if in_line_comment:
            buf.append(c)
            if c == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            buf.append(c)
            if c == "*" and nxt == "/":
                buf.append(nxt)
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue
        if in_squote:
            buf.append(c)
            if c == "\\" and nxt:
                buf.append(nxt)
                i += 2
                continue
            if c == "'":
                if nxt == "'":          # '' is an escaped quote, not a close
                    buf.append(nxt)
                    i += 2
                    continue
                in_squote = False
            i += 1
            continue
        if in_dquote or in_backtick:
            buf.append(c)
            if (in_dquote and c == '"') or (in_backtick and c == "`"):
                in_dquote = in_backtick = False
            i += 1
            continue

        # Not inside anything.
        if c == "-" and nxt == "-":
            in_line_comment = True
            buf.append(c)
            i += 1
            continue
        if c == "/" and nxt == "*":
            in_block_comment = True
            buf.append(c)
            buf.append(nxt)
            i += 2
            continue
        if c == "'":
            in_squote = True
            buf.append(c)
            i += 1
            continue
        if c == '"':
            in_dquote = True
            buf.append(c)
            i += 1
            continue
        if c == "`":
            in_backtick = True
            buf.append(c)
            i += 1
            continue
        if c == ";":
            out.append("".join(buf))
            buf = []
            i += 1
            continue

        buf.append(c)
        i += 1

    out.append("".join(buf))
    return [s for s in (strip_to_sql(x) for x in out) if s]


def strip_to_sql(stmt: str) -> str:
    """Drop a statement that is only whitespace and comments."""
    body_chars = []
    i, n = 0, len(stmt)
    in_line = in_block = False
    while i < n:
        c = stmt[i]
        nxt = stmt[i + 1] if i + 1 < n else ""
        if in_line:
            if c == "\n":
                in_line = False
            i += 1
            continue
        if in_block:
            if c == "*" and nxt == "/":
                in_block = False
                i += 2
                continue
            i += 1
            continue
        if c == "-" and nxt == "-":
            in_line = True
            i += 2
            continue
        if c == "/" and nxt == "*":
            in_block = True
            i += 2
            continue
        body_chars.append(c)
        i += 1
    return stmt.strip() if "".join(body_chars).strip() else ""


def substitute_literals(sql: str, literals: dict[str, str]) -> str:
    """Replace {name:Type} with a SQL literal, before the server ever parses it.

    WHY THIS EXISTS. ClickHouse cannot bind a query parameter inside a SETTINGS
    clause. Measured -- identical error in chdb 26.5 and on the 26.2 service:

        SELECT 1 SETTINGS max_execution_time = {t:UInt64}
        Code: 62. Syntax error: failed at position 49 (}).
                  Expected substitution type (identifier).

    while the same placeholder in a SELECT list or a WHERE binds fine. Settings
    take literals only, which CLAUDE.md already records for a different reason.

    Four placeholders in this repo sit in a SETTINGS clause -- the
    insert_deduplication_token of the INSERT in 011 and the three in 022 -- so
    they are unreachable by --param and MUST be substituted client-side.
    clickhouse-client did this silently, which is why the pipeline worked before
    it was ever applied over HTTP.

    The type in the placeholder decides the literal form: String-ish types are
    quoted and escaped, numeric types are emitted bare and validated as numbers
    so this cannot become a SQL-injection seam.
    """
    for name, value in literals.items():
        pattern = re.compile(r"\{" + re.escape(name) + r":([A-Za-z0-9_()\s,']+)\}")

        def repl(m: "re.Match[str]") -> str:
            declared = m.group(1).strip()
            if declared.lower().startswith(("string", "fixedstring", "uuid", "date", "datetime")):
                return "'" + escape_sql_string(value) + "'"
            # Numeric or anything else: refuse a non-numeric value rather than
            # paste it in unquoted.
            if not re.fullmatch(r"-?\d+(\.\d+)?", value):
                raise SystemExit(
                    f"error: --literal {name}={value!r} is declared {declared} in the SQL "
                    f"but is not numeric; refusing to substitute it unquoted"
                )
            return value

        sql, n = pattern.subn(repl, sql)
        if n == 0:
            print(f"  warning: --literal {name} matched nothing", file=sys.stderr)
    return sql


def escape_sql_string(s: str) -> str:
    """Escape for a single-quoted ClickHouse string literal.

    Mirrors escapeSQLString in ingest/internal/chx/schema.go. A password with a
    quote or a backslash in it would otherwise either break the DDL or, worse,
    terminate the literal early and change what the statement means.
    """
    return s.replace("\\", "\\\\").replace("'", "\\'")


def redact(text: str, secret: str) -> str:
    """Remove a secret from anything about to be printed.

    Applied to dry-run output, progress lines and server errors alike. The
    content dictionary's SOURCE clause embeds credentials, so the substituted
    DDL contains the password in plaintext -- printing a statement verbatim
    would put it on the terminal and into any captured log. ClickHouse also
    echoes offending SQL back in some error messages, which is why this wraps
    errors too and not just the dry-run path.

    BOTH the raw and the SQL-escaped spelling are removed, longest first.
    Redacting only the raw form is not enough and fails silently: the statement
    holds the ESCAPED password, so a secret containing a quote or a backslash
    would not match and would be printed in full. Caught by testing with
    p@ss\\/w0rd'x, which leaked as PASSWORD 'p@ss\\\\/w0rd\\'x'.
    """
    if not secret:
        return text
    for form in sorted({secret, escape_sql_string(secret)}, key=len, reverse=True):
        text = text.replace(form, "********")
    return text


def summarise(stmt: str, width: int = 110) -> str:
    """First non-comment line, for progress output."""
    for line in stmt.splitlines():
        s = line.strip()
        if s and not s.startswith("--"):
            return s[:width] + ("…" if len(s) > width else "")
    return stmt.strip()[:width]


def execute(cfg, sql: str, params: dict[str, str] | None = None) -> str:
    query = {"database": cfg.database}
    for k, v in (params or {}).items():
        query[f"param_{k}"] = v
    url = f"{cfg.base_url}/?{urllib.parse.urlencode(query)}"

    req = urllib.request.Request(url, data=sql.encode("utf-8"), method="POST")
    req.add_header("X-ClickHouse-User", cfg.user)
    if cfg.password:
        req.add_header("X-ClickHouse-Key", cfg.password)

    ctx = ssl.create_default_context()
    last_err = None
    for attempt in range(1, cfg.retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            # A server-side rejection is deterministic; retrying is pointless.
            raise RuntimeError(e.read().decode("utf-8", "replace").strip()) from None
        except (urllib.error.URLError, TimeoutError, ssl.SSLError) as e:
            # Transport-level. Cloud replaces replicas under load (a graceful
            # rolling restart was observed on this service on 2026-08-01), and
            # the documented expectation is that the client retries.
            last_err = e
            if attempt < cfg.retries:
                time.sleep(min(2 ** attempt, 15))
    raise RuntimeError(f"transport failure after {cfg.retries} attempts: {last_err}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", nargs="?", help="path to a .sql file ('-' for stdin)")
    ap.add_argument("--query", help="run a single statement instead of a file")
    ap.add_argument("--database", default=os.environ.get("CLICKHOUSE_DATABASE", "default"))
    ap.add_argument("--host", default=os.environ.get("CLICKHOUSE_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8443")))
    ap.add_argument("--user", default=os.environ.get("CLICKHOUSE_USER", "default"))
    ap.add_argument("--insecure", action="store_true", help="plain HTTP (local dev)")
    ap.add_argument("--param", action="append", default=[], metavar="K=V",
                    help="bound query parameter, repeatable")
    ap.add_argument("--literal", action="append", default=[], metavar="K=V",
                    help="textually substitute {K:Type} with V before parsing, repeatable. "
                         "Needed ONLY for placeholders inside a SETTINGS clause, which "
                         "ClickHouse cannot bind as query parameters -- see substitute_literals.")
    ap.add_argument("--rewrite-db", metavar="FROM", default=None,
                    help="rewrite a hardcoded 'FROM.' database prefix to --database. "
                         "pipeline/sql/* hardcode 'sonyliv.' rather than using {{db}}, so "
                         "without this they would create their objects in 'sonyliv' while "
                         "ingest/sql/* went to --database — a silent split across two databases. "
                         "'sonyliv_prod.' is NOT matched by 'sonyliv.' (the underscore differs).")
    ap.add_argument("--dry-run", action="store_true", help="print statements, execute nothing")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--retries", type=int, default=4)
    args = ap.parse_args()

    args.password = os.environ.get("CLICKHOUSE_PASSWORD", "")
    scheme = "http" if args.insecure else "https"
    args.base_url = f"{scheme}://{args.host}:{args.port}"

    literals = {}
    for p in args.literal:
        if "=" not in p:
            print(f"error: --literal must be K=V, got {p!r}", file=sys.stderr)
            return 2
        k, v = p.split("=", 1)
        literals[k] = v

    params = {}
    for p in args.param:
        if "=" not in p:
            print(f"error: --param must be K=V, got {p!r}", file=sys.stderr)
            return 2
        k, v = p.split("=", 1)
        params[k] = v

    if args.query:
        statements = [args.query]
        label = "<--query>"
    else:
        if not args.file:
            print("error: give a .sql file or --query", file=sys.stderr)
            return 2
        raw = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        # {{db}} keeps the DDL portable across sonyliv / sonyliv_prod / a scratch db.
        raw = raw.replace("{{db}}", args.database)
        # {{ch_user}} / {{ch_password}} exist only for the content dictionary's
        # SOURCE(CLICKHOUSE(...)) clause, which authenticates even when it points
        # at a table on the same server.
        #
        # These were NOT substituted here, and the consequence was silent:
        # ingest/sql/001_content.sql would be applied with a literal
        # '{{ch_user}}' as the username, CREATE OR REPLACE DICTIONARY would
        # SUCCEED because Cloud lazy-loads dictionaries, and the failure would
        # only appear on first use -- as an empty load, which
        # system.dictionaries still reports as status = 'LOADED'. Every
        # dictGetOrDefault would then return its default and video_type would be
        # '__unknown__' everywhere, with no error anywhere.
        #
        # ingest/internal/chx/schema.go already did this correctly, so the
        # dictionary worked when created by `sonyliv-ingest schema` and would
        # have been broken by bootstrap.sh -- two paths, one of them wrong.
        if literals:
            raw = substitute_literals(raw, literals)
        raw = raw.replace("{{ch_user}}", escape_sql_string(args.user))
        raw = raw.replace("{{ch_password}}", escape_sql_string(args.password))
        if args.rewrite_db and args.rewrite_db != args.database:
            src = f"{args.rewrite_db}."
            n = raw.count(src)
            raw = raw.replace(src, f"{args.database}.")
            if not args.quiet and n:
                print(f"  rewrote {n} occurrence(s) of '{src}' -> '{args.database}.'")
        statements = split_statements(raw)
        label = args.file

    if not args.quiet:
        print(f"  {label}: {len(statements)} statement(s) -> {args.database}")

    # Every print below goes through redact(): after the substitution above, the
    # dictionary statement contains the real password in plaintext.
    for idx, stmt in enumerate(statements, 1):
        if args.dry_run:
            print(redact(f"\n-- [{idx}/{len(statements)}] {label}\n{stmt};", args.password))
            continue
        try:
            out = execute(args, stmt, params)
        except RuntimeError as e:
            # Fail loud, and say exactly which statement, so the operator can
            # resume from here rather than re-running the whole stage blind.
            print(f"\nFAILED {label} statement {idx}/{len(statements)}:", file=sys.stderr)
            print(redact(f"  {summarise(stmt)}", args.password), file=sys.stderr)
            print(redact(f"\n{e}\n", args.password), file=sys.stderr)
            return 1
        if not args.quiet:
            print(redact(f"    [{idx}/{len(statements)}] ok  {summarise(stmt, 88)}", args.password))
        if out.strip():
            print(redact(out.rstrip(), args.password))
    return 0


if __name__ == "__main__":
    sys.exit(main())
