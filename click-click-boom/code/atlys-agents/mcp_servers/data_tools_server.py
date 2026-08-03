"""Lean, size-capped ClickHouse tools — built to replace the official mcp-clickhouse
server's list_tables/run_query as the agents' default, after measuring that a single
list_tables(database='atlys') call returns ~62,000 chars (~15,500 tokens): full
column metadata (types, comments, codecs) for every table in one response. In a
multi-turn tool-calling loop, every subsequent turn resends the whole growing
conversation, so one oversized call compounds across every later turn in the same
agent invocation — this is what actually drove real runs to ~90-100K input tokens
for a SINGLE agent call (measured via LibreChat's own transaction ledger in Mongo).

Two things fix this:
1. Tools here are narrow and compact by construction (list_tables returns just
   name/engine/row count; describe_table returns columns for ONE table, name+type
   only — no comments/codecs/stats bloat).
2. Anything still large gets offloaded: run_query writes the full result to a
   scratch file and returns a small preview + pointer, with grep_scratch/read_scratch
   tools to inspect the rest without ever pulling it all into context at once.
"""
import ast
import json
import pathlib
import re
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from mcp.server import FastMCP

from agent_meta.db import get_client

SCRATCH_DIR = pathlib.Path(__file__).resolve().parent.parent / ".tool_scratch"
SCRATCH_DIR.mkdir(exist_ok=True)

PREVIEW_ROW_LIMIT = 20
PREVIEW_CHAR_LIMIT = 3000
MAX_ROWS_HARD_CAP = 10_000  # a query forgetting its own LIMIT must still never pull all 1M+ rows

server = FastMCP(
    name="atlys_data", instructions="Read-only, size-capped tools for real Atlys ClickHouse data.",
    host="0.0.0.0", port=8102, stateless_http=True,
)


@server.tool()
def list_tables(database: str = "atlys") -> dict:
    """Lists tables in a database — name, engine, row count only. For column
    details on a SPECIFIC table you already know you need, use describe_table."""
    client = get_client(database=database)
    start_time = time.perf_counter()
    rows = client.query(
        "SELECT name, engine, total_rows FROM system.tables WHERE database = {db:String} ORDER BY name",
        parameters={"db": database},
    ).result_rows
    execution_time_ms = (time.perf_counter() - start_time) * 1000
    return {
        "tables": [{"table": n, "engine": e, "row_count": r} for n, e, r in rows],
        "execution_time_ms": round(execution_time_ms, 2)
    }


@server.tool()
def describe_table(table_name: str, database: str = "atlys") -> dict:
    """Column name + type for ONE table. Call this per-table, not in bulk —
    there's no "describe everything" tool on purpose; if you need several tables,
    call this once per table you actually need."""
    client = get_client(database=database)
    start_time = time.perf_counter()
    rows = client.query(
        "SELECT name, type FROM system.columns WHERE database = {db:String} AND table = {t:String} ORDER BY position",
        parameters={"db": database, "t": table_name},
    ).result_rows
    execution_time_ms = (time.perf_counter() - start_time) * 1000
    return {
        "columns": [{"column": n, "type": t} for n, t in rows],
        "execution_time_ms": round(execution_time_ms, 2)
    }


@server.tool()
def run_query(query: str, database: str = "atlys") -> dict:
    """Runs a READ-ONLY query (writes rejected server-side). Results up to
    ~10,000 rows are allowed through — small ones come back inline, large ones go
    to a scratch file (see below) — but the query is always capped at
    MAX_ROWS_HARD_CAP regardless of whether you added your own LIMIT, so a
    forgotten LIMIT can't pull millions of rows into memory. Prefer aggregate
    queries (GROUP BY/count/uniq) over row dumps where the question allows it."""
    client = get_client(database=database)
    # Wrapping as an outer-LIMIT subquery caps the result regardless of whether the
    # query has its own LIMIT (a redundant outer LIMIT >= an existing inner one is
    # harmless) — safer than trying to detect/parse an existing LIMIT clause.
    capped_query = f"SELECT * FROM ({query}) LIMIT {MAX_ROWS_HARD_CAP}"
    start_time = time.perf_counter()
    result = client.query(capped_query, settings={"readonly": 1})
    execution_time_ms = (time.perf_counter() - start_time) * 1000
    rows = [dict(zip(result.column_names, row)) for row in result.result_rows]
    hit_cap = len(rows) == MAX_ROWS_HARD_CAP
    inline_json = json.dumps({"columns": result.column_names, "rows": rows}, default=str)

    if len(rows) <= PREVIEW_ROW_LIMIT and len(inline_json) <= PREVIEW_CHAR_LIMIT:
        return {
            "columns": result.column_names,
            "rows": rows,
            "row_count": len(rows),
            "truncated": False,
            "execution_time_ms": round(execution_time_ms, 2)
        }

    # NDJSON — one row per line — is essential here, not cosmetic: grep_scratch and
    # read_scratch operate line-by-line, so a single minified JSON blob (one giant
    # line) would make both tools return the *entire* file regardless of pattern or
    # line range, silently defeating the whole point of offloading to scratch. Caught
    # by actually testing this against a 500-row query before treating it as done.
    scratch_file = SCRATCH_DIR / f"query_{uuid.uuid4().hex[:8]}.ndjson"
    with scratch_file.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")
    total_bytes = scratch_file.stat().st_size
    hint = (
        f"{len(rows)} total rows saved to scratch_file, one JSON row per line ({total_bytes} bytes). "
        f"Use grep_scratch(scratch_file, pattern) to search it, or read_scratch(scratch_file, start_line, n_lines) to page through it — don't ask for this query again."
    )
    if hit_cap:
        hint += f" NOTE: hit the {MAX_ROWS_HARD_CAP}-row hard cap — there may be more rows than this; narrow with WHERE/a smaller LIMIT if you need a specific slice rather than everything."
    return {
        "columns": result.column_names,
        "preview_rows": rows[:PREVIEW_ROW_LIMIT],
        "row_count": len(rows),
        "hit_row_cap": hit_cap,
        "truncated": True,
        "scratch_file": str(scratch_file),
        "hint": hint,
        "execution_time_ms": round(execution_time_ms, 2)
    }


MAX_LINES_RETURNED = 50  # hard cap regardless of what the caller asks for


@server.tool()
def grep_scratch(scratch_file: str, pattern: str, max_matches: int = 30) -> list[str]:
    """Greps a file saved by run_query for a regex pattern, returning matching
    lines only (case-insensitive). Use this instead of read_scratch when you're
    looking for something specific rather than browsing."""
    # run_query's scratch_file pointer is an absolute path, but the proposer's
    # OWN sample_events pointer (orchestrator/pipeline.py's
    # _write_sample_scratch_file) is a bare filename -- execute_python's
    # subprocess runs with cwd=SCRATCH_DIR so a bare name works there, but a
    # relative Path is never is_relative_to an absolute SCRATCH_DIR, so callers
    # passing that same bare filename here always 400'd even though the file
    # genuinely exists. Resolve relative to SCRATCH_DIR before checking.
    path = pathlib.Path(scratch_file)
    if not path.is_absolute():
        path = SCRATCH_DIR / path
    path = path.resolve()
    if not path.is_relative_to(SCRATCH_DIR):
        raise ValueError("scratch_file must be a path returned by run_query")
    regex = re.compile(pattern, re.IGNORECASE)
    matches = [line for line in path.read_text().splitlines() if regex.search(line)]
    return matches[: min(max_matches, MAX_LINES_RETURNED)]


@server.tool()
def read_scratch(scratch_file: str, start_line: int = 0, n_lines: int = 50) -> list[str]:
    """Pages through a file saved by run_query, n_lines at a time starting at
    start_line. Use this to browse when grep_scratch's pattern search isn't what
    you need."""
    n_lines = min(n_lines, MAX_LINES_RETURNED)
    # run_query's scratch_file pointer is an absolute path, but the proposer's
    # OWN sample_events pointer (orchestrator/pipeline.py's
    # _write_sample_scratch_file) is a bare filename -- execute_python's
    # subprocess runs with cwd=SCRATCH_DIR so a bare name works there, but a
    # relative Path is never is_relative_to an absolute SCRATCH_DIR, so callers
    # passing that same bare filename here always 400'd even though the file
    # genuinely exists. Resolve relative to SCRATCH_DIR before checking.
    path = pathlib.Path(scratch_file)
    if not path.is_absolute():
        path = SCRATCH_DIR / path
    path = path.resolve()
    if not path.is_relative_to(SCRATCH_DIR):
        raise ValueError("scratch_file must be a path returned by run_query")
    lines = path.read_text().splitlines()
    return lines[start_line : start_line + n_lines]


EXEC_TIMEOUT_S = 15
EXEC_OUTPUT_CHAR_CAP = 4000
ALLOWED_IMPORTS = {"pandas"}  # nothing else — no os/subprocess/socket/etc.


def _check_imports_allowed(code: str) -> str | None:
    """Static allowlist check via ast — this is not the sandboxing (there isn't
    real sandboxing here, see execute_python's docstring), it's a guardrail against
    the LLM reaching for stdlib/network/filesystem-escape modules by habit. Returns
    an error string if a disallowed import is found, else None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in ALLOWED_IMPORTS:
                    return f"Import not allowed: '{alias.name}'. Only `pandas` may be imported in execute_python."
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top not in ALLOWED_IMPORTS:
                return f"Import not allowed: 'from {node.module} import ...'. Only `pandas` may be imported in execute_python."
    return None


@server.tool()
def execute_python(code: str) -> dict:
    """Runs Python for dataframe analysis SQL can't express cleanly (correlation,
    pivoting, custom stats over a scratch file from run_query) — pandas is ALREADY
    imported as `pd`, don't import it yourself; no other imports permitted (checked
    before execution; you'll get an error, not a silent failure, if you try). NOT
    strongly sandboxed — plain subprocess, same OS privileges as this tool server,
    no container isolation, no network, 15s timeout. Working directory is the
    scratch dir, so `pd.read_json("some_query_file.ndjson", lines=True)` works with
    just the filename. Print everything you want to see; only stdout/stderr are
    returned (truncated if long)."""
    import_error = _check_imports_allowed(code)
    if import_error:
        return {"stdout": "", "stderr": import_error, "exit_code": -1, "truncated": False}
    try:
        # pd pre-imported here rather than relying on the model to remember its
        # own `import pandas as pd` -- a real run hit the identical NameError
        # ("pd is not defined") repeatedly across several tool calls because it
        # kept forgetting. Safe to prepend unconditionally: pandas is the only
        # allowed import, and Python re-importing an already-imported module is
        # a no-op if the model's own code also imports it.
        full_code = "import pandas as pd\n" + code
        result = subprocess.run(
            [sys.executable, "-c", full_code],
            cwd=SCRATCH_DIR, capture_output=True, text=True, timeout=EXEC_TIMEOUT_S,
        )
        return {
            "stdout": result.stdout[:EXEC_OUTPUT_CHAR_CAP],
            "stderr": result.stderr[:EXEC_OUTPUT_CHAR_CAP],
            "exit_code": result.returncode,
            "truncated": len(result.stdout) > EXEC_OUTPUT_CHAR_CAP or len(result.stderr) > EXEC_OUTPUT_CHAR_CAP,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {EXEC_TIMEOUT_S}s", "exit_code": -1, "truncated": False}


if __name__ == "__main__":
    server.run(transport="streamable-http")
