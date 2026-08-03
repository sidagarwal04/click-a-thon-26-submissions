#!/usr/bin/env python3
"""Create the ClickHouse users and grants this project depends on.

WHY THIS EXISTS
---------------
Every grant was originally applied by hand over curl and existed in no file.
That is invisible until the database is rebuilt or the repo is cloned, at which
point the compound scan fails with ACCESS_DENIED and nobody knows why — the kind
of thing that surfaces in production rather than in testing.

Grants are safe to commit; passwords are not. Passwords are read from .env
(gitignored), so this file fully reproduces the access model without carrying a
secret.

Least privilege is deliberate:
  * dashboard_ro — what the API and engine read as. SELECT only, readonly = 2
    (not 1: HyperDX-style clients append harmless SETTINGS to every query and
    readonly = 1 rejects ANY setting override).
  * mcp_ro       — what the Claude Code MCP reads as. SELECT only, readonly = 1.
  * mcp_agent    — what LibreChat reads as. SELECT only, readonly = 1.

None of the three can write. Verified at the end of this script rather than
assumed, because a grant that silently failed looks identical to one that worked.

Usage:
    setup_access.py            apply users + grants, then verify
    setup_access.py --verify   verify only, change nothing
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch import query, _load_env  # noqa: E402

# dictGet is required to resolve dimensions from the raw table. The
# materialized views do this at insert time as the admin user, so read-only
# users never needed it until pair/compound analysis started reading raw events
# directly — which is exactly how it came to be missing.
DICTIONARIES = ("dict_apps", "dict_advertisers", "dict_geo_device")

READERS = {
    "dashboard_ro": {
        "env": "CLICKHOUSE_PASSWORD",
        "readonly": 2,
        "grants": [
            "GRANT SELECT ON inmobi.* TO dashboard_ro",
            "GRANT SELECT ON otel.* TO dashboard_ro",
            *[f"GRANT dictGet ON inmobi.{d} TO dashboard_ro" for d in DICTIONARIES],
        ],
    },
    "mcp_ro": {
        "env": "MCP_RO_PASSWORD",
        "readonly": 1,
        "grants": [
            "GRANT SELECT ON inmobi.* TO mcp_ro",
            "GRANT SELECT ON system.tables TO mcp_ro",
            "GRANT SELECT ON system.columns TO mcp_ro",
            "GRANT SELECT ON system.databases TO mcp_ro",
            "GRANT SELECT ON system.parts TO mcp_ro",
            *[f"GRANT dictGet ON inmobi.{d} TO mcp_ro" for d in DICTIONARIES],
        ],
    },
    "mcp_agent": {
        "env": "MCP_AGENT_PASSWORD",
        "readonly": 1,
        "grants": [
            "GRANT SELECT ON inmobi.* TO mcp_agent",
            "GRANT SELECT ON system.tables TO mcp_agent",
            "GRANT SELECT ON system.columns TO mcp_agent",
            "GRANT SELECT ON system.databases TO mcp_agent",
            *[f"GRANT dictGet ON inmobi.{d} TO mcp_agent" for d in DICTIONARIES],
        ],
    },
}


def apply() -> None:
    _load_env()
    for user, spec in READERS.items():
        password = os.environ.get(spec["env"])
        if password:
            query(f"CREATE USER IF NOT EXISTS {user} "
                  f"IDENTIFIED WITH sha256_password BY '{password}'")
            print(f"  {user}: ensured")
        else:
            print(f"  {user}: no {spec['env']} in .env — assuming the user exists")
        for grant in spec["grants"]:
            query(grant)
        query(f"ALTER USER {user} SETTINGS readonly = {spec['readonly']}")
        print(f"  {user}: {len(spec['grants'])} grants, readonly = {spec['readonly']}")


def verify() -> bool:
    """Check the grants that actually matter, rather than trusting the applies."""
    _load_env()
    ok = True
    rows = query(
        "SELECT user_name, access_type, table FROM system.grants "
        "WHERE user_name IN ('dashboard_ro','mcp_ro','mcp_agent') FORMAT TSV"
    ).strip().splitlines()
    have = {tuple(r.split("\t")[:3]) for r in rows if r}

    print("\n  dictGet on every dictionary (needed for compound/pair analysis):")
    for user in READERS:
        for d in DICTIONARIES:
            present = (user, "dictGet", d) in have
            ok &= present
            print(f"    {user:<14} {d:<18} {'OK' if present else 'MISSING'}")

    print("\n  none of the readers may write:")
    for user in READERS:
        env = READERS[user]["env"]
        password = os.environ.get(env)
        if not password:
            print(f"    {user:<14} skipped (no {env} in .env)")
            continue
        try:
            query(f"CREATE TABLE inmobi._writetest_{user} (x UInt8) ENGINE=Memory",
                  user=user, password=password)
            print(f"    {user:<14} WRITE SUCCEEDED — privileges are too broad")
            ok = False
        except RuntimeError as exc:
            blocked = "Not enough privileges" in str(exc) or "readonly" in str(exc).lower()
            ok &= blocked
            print(f"    {user:<14} {'correctly refused' if blocked else f'unexpected: {exc}'}")

    print(f"\n  {'ACCESS MODEL OK' if ok else 'ACCESS MODEL HAS GAPS'}")
    return ok


if __name__ == "__main__":
    if "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)
    print("Applying users and grants ...")
    apply()
    sys.exit(0 if verify() else 1)
