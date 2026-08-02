"""Applies monitoring_rollups.sql + monitoring_state.sql to the live ClickHouse
instance, backfills the new rollups from ad_events, and reconciles them against
the raw fact table.

Why this exists instead of `clickhouse-client --queries-file`: this repo's
ClickHouse MCP connection is read-only (CLICKHOUSE_ALLOW_WRITE_ACCESS unset),
so DDL/DML goes through a direct clickhouse-connect client. Same reason, and
same shape, as scripts/apply_and_backfill.py.

WHAT IS DIFFERENT FROM apply_and_backfill.py, AND WHY IT MATTERS
----------------------------------------------------------------
The older script's idempotency guard is `if count(*) > 0: SKIP` -- all or
nothing per table. That is fine for a one-shot backfill of an already-loaded
dataset, but it fails in exactly the situation this project is built for: the
unseen-incident dataset.

  If a rollup is created BEFORE new rows land in ad_events, its materialized
  view fires and the rollup is correct -- no backfill needed.

  If a rollup is created AFTER, the MV never saw those rows. The table is
  non-empty (it has the earlier backfill), so `count(*) > 0` skips it, and the
  hole is never filled. Nothing errors. Every query against that rollup then
  returns a confidently wrong number.

So this script reconciles and backfills PER DAY: it compares each rollup's
per-day request count against raw ad_events, and repairs only the days that
disagree (deleting the partial day first, so a half-populated day cannot be
double-counted). A day that already matches exactly is left untouched.

Nothing here writes to ad_events or the dimension tables -- only CREATE, and
INSERT ... SELECT into the new tables -- so the existing Phase-0 reconciliation
of the fact table stays valid.

The same argument applies one level up, to COLUMNS rather than rows, and that
gap shipped: `CREATE TABLE IF NOT EXISTS` is a no-op on an existing table, so a
column added to clickhouse/monitoring_state.sql is silently never created by
`ddl`. Three columns had in fact been applied to ad_events_main out-of-band and
were missing from the .sql file, so any database built from this repo crashed on
the first save_incidents. The `columns` step reconciles that; see the long
comment above column_parity().

Usage:
    .venv/Scripts/python.exe scripts/apply_monitoring.py [ddl|columns|backfill|reconcile|all|verify]

    ddl        create the rollup tables/MVs and the state tables
    columns    add any state-table column present in the .sql file but missing
               from the database (ALTER ... ADD COLUMN IF NOT EXISTS). Type
               mismatches are reported and fail, never silently altered.
    backfill   per-day repair of any rollup day that disagrees with raw
    reconcile  report only; exits 1 on any mismatch, rows AND columns
    verify     alias for reconcile (read-only; makes no changes)
    all        ddl -> columns -> backfill -> reconcile   (default)

Every step is unqualified SQL against the connection's default database, so the
target is whatever CLICKHOUSE_DATABASE says. It is printed on every run.
"""

import os
import re
import sys
import time

import clickhouse_connect
from dotenv import load_dotenv

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(REPO, "utils", ".env"))

MEASURES = ("requests", "fills", "impressions", "clicks", "revenue")


def get_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        database=os.environ.get("CLICKHOUSE_DATABASE", "ad_events_main"),
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
    )


def split_statements(sql_text):
    lines = []
    for line in sql_text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(re.sub(r"--.*$", "", line))
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def run_file(client, path):
    with open(path, "r", encoding="utf-8") as f:
        statements = split_statements(f.read())
    for i, stmt in enumerate(statements, 1):
        label = stmt.splitlines()[0][:80]
        try:
            client.command(stmt)
            print(f"  [{i}/{len(statements)}] OK   {label}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  [{i}/{len(statements)}] SKIP (exists) {label}")
            else:
                raise


# ---------------------------------------------------------------------------
# Backfill definitions.
#
# Each SELECT body is the EXACT body of the matching materialized view in
# clickhouse/monitoring_rollups.sql, with one addition: a {where} placeholder
# so the same statement can backfill a single day instead of all history.
# Keeping them identical to the MV bodies is what guarantees a backfilled row
# and an MV-produced row are the same row -- if these ever drift, the rollup
# silently disagrees with itself depending on when a row arrived.
# ---------------------------------------------------------------------------
BACKFILLS = {
    "minute5_overall": (
        "bucket",
        """SELECT toStartOfFiveMinute(event_time) AS bucket,
                  count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
                  sum(is_click) AS clicks, sum(revenue) AS revenue
           FROM ad_events {where} GROUP BY bucket""",
    ),
    "minute5_by_region": (
        "bucket",
        """SELECT toStartOfFiveMinute(event_time) AS bucket,
                  dictGet('geo_device_dict', 'region', geo_device_id) AS region,
                  count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
                  sum(is_click) AS clicks, sum(revenue) AS revenue
           FROM ad_events {where} GROUP BY bucket, region""",
    ),
    "minute5_by_format": (
        "bucket",
        """SELECT toStartOfFiveMinute(event_time) AS bucket, ad_format,
                  count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
                  sum(is_click) AS clicks, sum(revenue) AS revenue
           FROM ad_events {where} GROUP BY bucket, ad_format""",
    ),
    "hourly_geo_cell": (
        "hour",
        """SELECT toStartOfHour(event_time) AS hour,
                  dictGet('geo_device_dict', 'region', geo_device_id)       AS region,
                  dictGet('geo_device_dict', 'country', geo_device_id)      AS country,
                  dictGet('geo_device_dict', 'device_model', geo_device_id) AS device_model,
                  count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
                  sum(is_click) AS clicks, sum(revenue) AS revenue
           FROM ad_events {where} GROUP BY hour, region, country, device_model""",
    ),
    "hourly_os_family_region": (
        "hour",
        """SELECT toStartOfHour(event_time) AS hour,
                  splitByChar(' ', dictGet('geo_device_dict', 'os_version', geo_device_id))[1] AS os_family,
                  dictGet('geo_device_dict', 'region', geo_device_id) AS region,
                  count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
                  sum(is_click) AS clicks, sum(revenue) AS revenue
           FROM ad_events {where} GROUP BY hour, os_family, region""",
    ),
    "hourly_format_region": (
        "hour",
        """SELECT toStartOfHour(event_time) AS hour, ad_format,
                  dictGet('geo_device_dict', 'region', geo_device_id) AS region,
                  count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
                  sum(is_click) AS clicks, sum(revenue) AS revenue
           FROM ad_events {where} GROUP BY hour, ad_format, region""",
    ),
    "reach_hourly": (
        "hour",
        """SELECT toStartOfHour(event_time) AS hour,
                  count() AS requests,
                  uniqState(toString(geo_device_id)) AS uniq_devices,
                  uniqState(toString(app_id))        AS uniq_apps
           FROM ad_events {where} GROUP BY hour""",
    ),
}


def _raw_days(client):
    """Per-day request counts straight from the fact table -- the reference
    every rollup is repaired against."""
    rows = client.query(
        "SELECT toDate(event_time) AS d, count() AS requests FROM ad_events GROUP BY d ORDER BY d"
    ).result_rows
    return {str(r[0]): int(r[1]) for r in rows}


def _rollup_days(client, table, time_col):
    rows = client.query(
        f"SELECT toDate({time_col}) AS d, sum(requests) AS requests FROM {table} GROUP BY d ORDER BY d"
    ).result_rows
    return {str(r[0]): int(r[1]) for r in rows}


def backfill(client):
    raw = _raw_days(client)
    if not raw:
        print("ad_events is empty -- nothing to backfill.")
        return
    print(f"ad_events spans {len(raw)} day(s): {min(raw)} .. {max(raw)}")

    for table, (time_col, select_body) in BACKFILLS.items():
        have = _rollup_days(client, table, time_col)
        # A day is repaired when its rollup total does not equal raw's. That
        # covers all three real cases: day missing entirely, day partially
        # populated (rollup created mid-load), and day double-counted.
        bad = [d for d, want in raw.items() if have.get(d) != want]
        extra = [d for d in have if d not in raw]
        if not bad and not extra:
            print(f"{table}: OK ({len(have)} days match raw exactly)")
            continue

        print(f"{table}: repairing {len(bad)} day(s)" + (f", dropping {len(extra)} stale day(s)" if extra else ""))
        t0 = time.time()
        for d in sorted(set(bad) | set(extra)):
            if d in have:
                # Delete before re-inserting: a partially-populated day would
                # otherwise be summed on top of itself. mutations_sync=2 waits
                # for the mutation on all replicas, so the INSERT below cannot
                # race it.
                client.command(
                    f"ALTER TABLE {table} DELETE WHERE toDate({time_col}) = toDate('{d}') "
                    f"SETTINGS mutations_sync = 2"
                )
            if d in raw:
                where = f"WHERE toDate(event_time) = toDate('{d}')"
                client.command(f"INSERT INTO {table} {select_body.format(where=where).strip()}")
        after = _rollup_days(client, table, time_col)
        still_bad = [d for d, want in raw.items() if after.get(d) != want]
        status = "OK" if not still_bad else f"STILL MISMATCHED on {len(still_bad)} day(s)"
        print(f"{table}: repaired in {time.time()-t0:.1f}s -> {status}")


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------
def _totals(client, sql):
    r = client.query(sql).first_row
    # revenue compared as a string: Decimal(38,6) vs Decimal(18,6) are equal in
    # value but not as Python floats, and a float round-trip is exactly the kind
    # of silent drift this check exists to catch.
    return (int(r[0]), int(r[1]), int(r[2]), int(r[3]), str(r[4]))


def reconcile(client):
    ok = True
    raw = _totals(
        client,
        "SELECT count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions, "
        "sum(is_click) AS clicks, sum(revenue) AS revenue FROM ad_events",
    )
    print(f"ad_events (reference): requests={raw[0]} fills={raw[1]} impressions={raw[2]} clicks={raw[3]} revenue={raw[4]}")

    for table, (time_col, _) in BACKFILLS.items():
        if table == "reach_hourly":
            continue  # only carries requests + distinct-count states; checked separately below
        got = _totals(
            client,
            f"SELECT sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue) FROM {table}",
        )
        match = got == raw
        ok = ok and match
        print(f"  {'OK  ' if match else 'FAIL'} {table:26s} requests={got[0]} fills={got[1]} "
              f"impressions={got[2]} clicks={got[3]} revenue={got[4]}")

    # reach_hourly carries no fills/impressions/clicks/revenue -- requests only.
    reach = client.query("SELECT sum(requests) FROM reach_hourly").first_row
    reach_ok = int(reach[0]) == raw[0]
    ok = ok and reach_ok
    print(f"  {'OK  ' if reach_ok else 'FAIL'} reach_hourly               requests={int(reach[0])}")

    # Cross-check the composite against an independently-built 1-D rollup that
    # was reconciled in Phase 0. This catches a wrong dictGet or a wrong GROUP
    # BY in the composite MV, which a grand-total check alone would not: a
    # mis-keyed row still sums to the same total.
    cross = client.query(
        """SELECT g.region, g.req, r.req FROM
             (SELECT region, sum(requests) AS req FROM hourly_geo_cell GROUP BY region) g
           FULL OUTER JOIN
             (SELECT region, sum(requests) AS req FROM hourly_by_region GROUP BY region) r
           USING (region) ORDER BY g.region"""
    ).result_rows
    cross_bad = [row for row in cross if int(row[1] or 0) != int(row[2] or 0)]
    ok = ok and not cross_bad
    print(f"  {'OK  ' if not cross_bad else 'FAIL'} hourly_geo_cell vs hourly_by_region, per region "
          f"({len(cross)} region(s) compared)")
    for row in cross_bad:
        print(f"       region={row[0]}: geo_cell={row[1]} by_region={row[2]}")

    # os_family must partition the same request total as os_version does.
    osfam = client.query("SELECT sum(requests) FROM hourly_os_family_region").first_row
    osfam_ok = int(osfam[0]) == raw[0]
    ok = ok and osfam_ok
    print(f"  {'OK  ' if osfam_ok else 'FAIL'} hourly_os_family_region partitions all requests")

    # Distinct counts must be plausible, i.e. bounded by the dimension tables.
    reach_row = client.query(
        "SELECT uniqMerge(uniq_devices), uniqMerge(uniq_apps) FROM reach_hourly"
    ).first_row
    dims = client.query("SELECT (SELECT count() FROM geo_device), (SELECT count() FROM apps)").first_row
    reach_sane = 0 < int(reach_row[0]) <= int(dims[0]) and 0 < int(reach_row[1]) <= int(dims[1])
    ok = ok and reach_sane
    print(f"  {'OK  ' if reach_sane else 'FAIL'} reach_hourly distinct: devices={reach_row[0]}/{dims[0]} "
          f"apps={reach_row[1]}/{dims[1]}")

    print("\nRECONCILED OK" if ok else "\nMISMATCH -- do not trust these rollups until resolved")
    return ok


# ---------------------------------------------------------------------------
# Column reconciliation
#
# WHY THIS EXISTS, and why row reconciliation was not enough.
#
# The per-day backfill above fixes missing ROWS. This fixes missing COLUMNS, and
# it is the same class of bug one level up -- with the same property that nothing
# errors at apply time:
#
#   `CREATE TABLE IF NOT EXISTS` on an existing table is a NO-OP. Add a column to
#   the .sql file and re-run `ddl`, and the statement is skipped as "already
#   exists". The new column is never created, nothing is reported, and the next
#   INSERT naming it fails at runtime in a completely different place.
#
# That is not hypothetical: `incidents.windows_spanned` and
# `sweep_{runs,coverage}.skipped_incomplete_window` existed in ad_events_main but
# were absent from clickhouse/monitoring_state.sql, having been applied
# out-of-band. A database built from this repo's own DDL was therefore missing
# three columns that engine/monitor_store.py names explicitly, and crashed on the
# first save_incidents -- i.e. on the unseen-incident dataset this project exists
# to serve.
#
# The expected shape is PARSED FROM THE .sql FILE rather than declared in a list
# here. A second hand-maintained copy of the schema is exactly what drifted in the
# first place; deriving it means the file stays the single source of truth.
#
# Parity is by NAME and TYPE, never position: ad_events_main carries
# impact_usd_per_day at ordinal 27 (it arrived as an ALTER) where a fresh database
# puts it at 15, and column order cannot be changed without recreating the table.
# It is harmless because every insert in engine/ passes explicit column_names.
# ---------------------------------------------------------------------------
_STATE_TABLES = ("baselines", "contribution", "metric_events", "incidents",
                 "sweep_runs", "sweep_coverage")


def expected_columns(path):
    """{table: [(name, type, default_sql), ...]} parsed from a DDL file.

    Deliberately a small parser rather than a full one: it only has to read the
    `CREATE TABLE IF NOT EXISTS x ( ... )` bodies this repo writes. Every type in
    them is a single whitespace-free token (`LowCardinality(String)`,
    `Array(LowCardinality(String))`, `Nullable(UUID)`), so `name type [rest]`
    splits correctly, and comments are already stripped by split_statements().
    """
    with open(path, "r", encoding="utf-8") as f:
        statements = split_statements(f.read())

    out = {}
    for stmt in statements:
        m = re.match(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)\s*\(", stmt, re.I | re.S)
        if not m:
            continue
        table = m.group(1)
        body = stmt[m.end():]
        # Cut at the matching close paren of the column list, tracking nesting so
        # a type like Array(LowCardinality(String)) does not end the body early.
        depth, end = 1, None
        for i, ch in enumerate(body):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            continue

        cols, depth, current = [], 0, ""
        for ch in body[:end]:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                cols.append(current)
                current = ""
            else:
                current += ch
        cols.append(current)

        parsed = []
        for raw in cols:
            parts = raw.split()
            if len(parts) < 2:
                continue
            name, ctype, rest = parts[0], parts[1], " ".join(parts[2:])
            default = rest if rest.upper().startswith("DEFAULT") else ""
            parsed.append((name, ctype, default))
        if parsed:
            out[table] = parsed
    return out


def _actual_columns(client, database):
    rows = client.query(
        "SELECT table, name, type, position FROM system.columns "
        f"WHERE database = '{database}' ORDER BY table, position"
    ).result_rows
    out = {}
    for table, name, ctype, position in rows:
        out.setdefault(table, {})[name] = (ctype, int(position))
    return out


def column_parity(client, database, apply_changes):
    """Reports (and optionally repairs) missing columns in the state tables.

    Returns True when every expected column is present with the expected type.
    A TYPE mismatch is never auto-fixed -- changing a column's type can lose
    data, so it is reported and fails the run for a human to resolve.
    """
    want = expected_columns(os.path.join(REPO, "clickhouse", "monitoring_state.sql"))
    have = _actual_columns(client, database)

    ok, repaired = True, 0
    for table in _STATE_TABLES:
        expected = want.get(table)
        if not expected:
            print(f"  {table:16s} NOT DECLARED in monitoring_state.sql -- cannot check")
            ok = False
            continue
        actual = have.get(table)
        if actual is None:
            print(f"  {table:16s} TABLE MISSING -- run `apply_monitoring.py ddl` first")
            ok = False
            continue

        missing = [(n, t, d) for (n, t, d) in expected if n not in actual]
        mistyped = [(n, t, actual[n][0]) for (n, t, _) in expected
                    if n in actual and actual[n][0] != t]
        extra = [n for n in actual if n not in {e[0] for e in expected}]

        for name, ctype, want_type in mistyped:
            print(f"  {table:16s} TYPE MISMATCH {name}: DDL says {ctype}, database has {want_type}")
            ok = False

        if missing and apply_changes:
            for name, ctype, default in missing:
                # Appended at the end, which is where an ALTER put the same column
                # in ad_events_main -- so this reproduces that database's ordinals
                # for sweep_runs/sweep_coverage exactly.
                sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ctype}"
                if default:
                    sql += f" {default}"
                client.command(sql)
                repaired += 1
                print(f"  {table:16s} ADDED {name} {ctype} {default}".rstrip())
        elif missing:
            for name, ctype, default in missing:
                print(f"  {table:16s} MISSING {name} {ctype} {default}".rstrip()
                      + "   (run `apply_monitoring.py columns` to add)")
            ok = False

        if not missing and not mistyped:
            note = ""
            if extra:
                # Not a failure: a column present in the database but absent from the
                # DDL is forward-compatible, and reporting it is how the reverse of
                # this bug (DDL behind the database) becomes visible next time.
                note = f"  [+{len(extra)} not in DDL: {', '.join(sorted(extra))}]"
            print(f"  {table:16s} OK ({len(expected)} column(s) match by name+type){note}")

    if apply_changes:
        print(f"\n{repaired} column(s) added." if repaired else "\nNo columns needed adding.")
    return ok


def state_tables_report(client):
    """The monitoring state tables start empty; report that plainly rather than
    letting an empty read later look like 'nothing was wrong'."""
    for t in ("baselines", "contribution", "metric_events", "incidents", "sweep_runs", "sweep_coverage"):
        try:
            n = int(client.command(f"SELECT count() FROM {t}"))
            print(f"  {t:16s} {n} row(s)")
        except Exception as e:
            print(f"  {t:16s} MISSING ({str(e)[:60]})")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step == "verify":
        step = "reconcile"
    client = get_client()
    database = str(client.command("SELECT currentDatabase()"))
    print("Connected. Server:", client.server_version)
    # Named on every run: every statement below is unqualified, so the database is
    # the only thing deciding what gets altered. Printing it is what makes running
    # this against the wrong dataset a visible mistake rather than a silent one.
    print("Database:", database)

    if step in ("ddl", "all"):
        print("\n=== monitoring_rollups.sql ===")
        run_file(client, os.path.join(REPO, "clickhouse", "monitoring_rollups.sql"))
        print("\n=== monitoring_state.sql ===")
        run_file(client, os.path.join(REPO, "clickhouse", "monitoring_state.sql"))

    # Immediately after ddl and BEFORE backfill: CREATE TABLE IF NOT EXISTS cannot
    # add a column to a table that already exists, so this is the only step that
    # can bring an older database up to the current schema -- and it has to happen
    # before anything tries to write those columns.
    if step in ("columns", "all"):
        print("\n=== column parity (repair) ===")
        if not column_parity(client, database, apply_changes=True):
            sys.exit(1)

    if step in ("backfill", "all"):
        print("\n=== backfill (per-day repair) ===")
        backfill(client)

    if step in ("reconcile", "all"):
        print("\n=== column parity (report only) ===")
        columns_ok = column_parity(client, database, apply_changes=False)
        print("\n=== reconcile ===")
        reconciled = reconcile(client)
        print("\n=== monitoring state tables ===")
        state_tables_report(client)
        if not (reconciled and columns_ok):
            sys.exit(1)

    print("\nDone.")
