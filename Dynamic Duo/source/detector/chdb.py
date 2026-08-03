"""ClickHouse access for the detector — zero dependencies, one code path.

Transport selection (mirrors load.sh connection logic):
  CH_HOST set, CH_TRANSPORT=http -> ClickHouse HTTP interface via urllib. No binary
                                    needed — the path the rca-mcp container uses.
                                    CH_SECURE=0 -> http://host:8123, else https:8443.
  CH_HOST set, otherwise         -> `clickhouse client` subprocess.
                                    CH_SECURE=0 -> plain TCP, port 9000, password
                                    optional (local docker); else --secure 9440 (Cloud).
  CH_HOST unset                  -> `clickhouse local --path <repo>/.chlocal`

Query results come back as JSONEachRow -> list[dict] on every transport.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_MIN_LOCAL_MAJOR = 23   # clickhouse-local gained --param_* support in 23.x
_version_checked = False


def _secure() -> bool:
    return os.environ.get("CH_SECURE", "1") not in ("0", "false", "no")


def _use_http() -> bool:
    return bool(os.environ.get("CH_HOST")) and \
        os.environ.get("CH_TRANSPORT", "").lower() == "http"


def _check_local_version(binary: list[str]) -> None:
    """Old local binaries (e.g. Homebrew 22.13) silently break bound params —
    fail loudly with the fix instead (Nitya hit this; see sql/agent/VALIDATED.md)."""
    global _version_checked
    if _version_checked:
        return
    _version_checked = True
    out = subprocess.run(binary + ["--version"], capture_output=True, text=True).stdout
    for tok in out.split():
        if tok[0:1].isdigit() and "." in tok:
            major = int(tok.split(".")[0])
            if major < _MIN_LOCAL_MAJOR:
                raise RuntimeError(
                    f"clickhouse {tok.strip('.')} is too old for local mode "
                    f"(needs >= {_MIN_LOCAL_MAJOR}.x for --param support). "
                    "Fix: `brew upgrade clickhouse` (or set CH_HOST to a server).")
            return


def _base_cmd() -> list[str]:
    single = shutil.which("clickhouse")
    host = os.environ.get("CH_HOST")
    if host:
        cmd = [single, "client"] if single else [shutil.which("clickhouse-client") or "clickhouse-client"]
        cmd += ["--host", host, "--user", os.environ.get("CH_USER", "default")]
        if _secure():
            cmd += ["--port", os.environ.get("CH_PORT", "9440"), "--secure",
                    "--password", os.environ["CH_PASSWORD"]]
        else:
            cmd += ["--port", os.environ.get("CH_PORT", "9000"),
                    "--password", os.environ.get("CH_PASSWORD", "")]
        return cmd
    cmd = [single, "local"] if single else [shutil.which("clickhouse-local") or "clickhouse-local"]
    _check_local_version(cmd)
    return cmd + ["--path", str(REPO_ROOT / ".chlocal")]


# ── HTTP transport ────────────────────────────────────────────────────────────

def _http_call(sql: str, params: dict | None, fmt: str | None,
               body_data: str | None = None, settings: dict | None = None) -> str:
    scheme = "https" if _secure() else "http"
    port = os.environ.get("CH_HTTP_PORT", "8443" if _secure() else "8123")
    qs = {k: str(v) for k, v in (settings or {}).items()}
    if fmt:
        qs["default_format"] = fmt
    for k, v in (params or {}).items():
        qs[f"param_{k}"] = str(v)
    if body_data is not None:            # INSERT: query in URL, data in body
        qs["query"] = sql
        body = body_data.encode()
    else:                                # SELECT/DDL: query is the body
        body = sql.encode()
    url = (f"{scheme}://{os.environ['CH_HOST']}:{port}/?"
           + urllib.parse.urlencode(qs))
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "X-ClickHouse-User": os.environ.get("CH_USER", "default"),
        "X-ClickHouse-Key": os.environ.get("CH_PASSWORD", ""),
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:2000]
        raise RuntimeError(f"clickhouse http error {e.code}:\n{detail}\n"
                           f"--- query was:\n{sql[:2000]}") from None


# ── public API (transport-agnostic) ───────────────────────────────────────────

def query_raw(sql: str, params: dict | None = None, fmt: str | None = None,
              settings: dict | None = None) -> str:
    if _use_http():
        return _http_call(sql, params, fmt, settings=settings)
    cmd = _base_cmd() + ["--query", sql]
    for k, v in (params or {}).items():
        cmd += [f"--param_{k}", str(v)]
    for k, v in (settings or {}).items():
        cmd += [f"--{k}", str(v)]
    if fmt:
        cmd += ["--format", fmt]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"clickhouse error:\n{res.stderr.strip()}\n--- query was:\n{sql[:2000]}")
    return res.stdout


def query(sql: str, params: dict | None = None) -> list[dict]:
    # 64-bit ints as JSON numbers, not quoted strings — callers do arithmetic on them
    out = query_raw(sql, params, fmt="JSONEachRow",
                    settings={"output_format_json_quote_64bit_integers": 0})
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def query_file(path: Path | str, params: dict | None = None) -> list[dict]:
    return query(Path(path).read_text(), params)


def insert_rows(table: str, rows: list[dict]) -> None:
    if not rows:
        return
    payload = "\n".join(json.dumps(r) for r in rows)
    sql = f"INSERT INTO {table} FORMAT JSONEachRow"
    if _use_http():
        _http_call(sql, None, None, body_data=payload)
        return
    cmd = _base_cmd() + ["--query", sql]
    res = subprocess.run(cmd, input=payload, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"insert into {table} failed:\n{res.stderr.strip()}")


def scalar(sql: str, params: dict | None = None):
    rows = query(f"SELECT ({sql}) AS v", params)
    return rows[0]["v"] if rows else None
