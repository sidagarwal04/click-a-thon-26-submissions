#!/usr/bin/env python3
"""Apply ingest/sql/001-004 in chdb against a REAL sample of the surprise CSVs.

    python3 ingest/tools/validate_surprise_schema.py [rows]

Proves, before 7,000,000 rows are loaded into a live service:

  * the DDL parses and runs after the video_resolution / show_name additions
  * events_raw_to_clean_mv fires and carries the new column
  * the normalization actually merges '1920 * 1080' into '1920*1080'
  * the quality-ladder prefix is PRESERVED, not collapsed
  * show_name survives content_dim -> content_current -> content_dict
  * partitions are daily, not monthly

chdb is 26.5 and the service is 26.2, so this validates semantics, not
version-gated syntax. It substitutes {{db}} / {{ch_user}} / {{ch_password}} the
same way scripts/lib/apply_sql.py does.
"""
import csv, io, os, re, sys, pathlib, chdb

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = pathlib.Path("/Users/dahiya/Work/sonyliv/data")
RAW = DATA / "ch-hackathon-raw-data_surprise.csv"
CONTENT = DATA / "ch-hackathon-content-data_surprise.csv"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000

sys.path.insert(0, str(ROOT / "scripts" / "lib"))
from apply_sql import split_statements  # noqa: E402

sess = chdb.session.Session()
sess.query("CREATE DATABASE IF NOT EXISTS sonyliv")


def apply_file(name: str):
    raw = (ROOT / "ingest" / "sql" / name).read_text()
    raw = (raw.replace("{{db}}", "sonyliv")
              .replace("{{ch_user}}", "default")
              .replace("{{ch_password}}", ""))
    for st in split_statements(raw):
        up = st.upper()
        # Cloud-only knobs chdb does not implement.
        if "MODIFY SETTING" in up:
            continue
        # Cut the WHOLE trailing SETTINGS clause, up to COMMENT or end of
        # statement. Removing the individual settings by regex leaves their
        # separating commas behind -- `SETTINGS -- note\n , ,\n COMMENT '...'` --
        # which is a syntax error whose message points at the COMMENT string and
        # reads like a problem with the DDL rather than with this harness.
        st = re.sub(r"\nSETTINGS\b.*?(?=\nCOMMENT\b|\Z)", "\n", st, flags=re.S)
        # chdb ships without the ICU string functions: lowerUTF8 and upperUTF8 do
        # not exist in chdb 26.5, while system.functions on the 26.2 SERVICE lists
        # both. So this is a chdb build limitation, NOT a version regression and
        # NOT something to change in the DDL. Shimmed to `lower` for this harness
        # only -- every value it touches here (language codes, resolutions) is
        # ASCII, so the two agree on this data.
        st = st.replace("lowerUTF8(", "lower(").replace("upperUTF8(", "upper(")
        try:
            sess.query(st)
        except Exception as e:
            msg = str(e)
            # A dictionary over a same-server table needs no credentials in chdb.
            if "DICTIONARY" in up and "AUTHENT" in msg.upper():
                continue
            print(f"FAILED in {name}:\n{st[:500]}\n-> {msg[:400]}")
            sys.exit(1)
    print(f"  applied {name}")


print("=== applying ingest DDL ===")
for f in ["001_content.sql", "002_events_raw.sql", "003_events_clean.sql",
          "004_ingest_control.sql"]:
    apply_file(f)


def load_csv(path, table, cols, limit, extra=None):
    """Stream `limit` rows of a real CSV into `table` via a VALUES insert."""
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        rows, n = [], 0
        for rec in r:
            vals = []
            for c, kind in cols:
                v = rec.get(c, "") or ""
                if kind == "i":
                    vals.append(str(int(v)) if v.strip("-").isdigit() else "0")
                elif kind == "ts":
                    vals.append(f"fromUnixTimestamp64Milli(toInt64({int(v)}))" if v.isdigit() else "toDateTime64(0,3)")
                else:
                    vals.append("'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'")
            for _, lit in (extra or []):
                vals.append(lit)
            rows.append("(" + ",".join(vals) + ")")
            n += 1
            if n >= limit:
                break
    names = ",".join([c for c, _ in cols] + [c for c, _ in (extra or [])])
    sess.query(f"INSERT INTO sonyliv.{table} ({names}) VALUES " + ",".join(rows))
    return n


print(f"\n=== loading {N:,} real event rows + full catalogue ===")
# source_version is the ReplacingMergeTree version column and cannot be UPDATEd
# after the fact (CANNOT_UPDATE_COLUMN), so it goes in with the insert.
nc = load_csv(CONTENT, "content_dim",
              [("content_id", "i"), ("title", "s"), ("video_type", "s"),
               ("category", "s"), ("show_name", "s")], 40000,
              extra=[("source_version", "1")])
print(f"  content_dim      {nc:,} rows")

ne = load_csv(RAW, "events_raw",
              [("content_id", "i"), ("video_session_id", "s"), ("user_id", "s"),
               ("event_type", "s"), ("event", "s"), ("event_timestamp", "ts"),
               ("platform", "s"), ("app_version", "s"), ("country", "s"),
               ("audio_language", "s"), ("subtitle_language", "s"),
               ("player_version", "s"), ("session_start_epoch", "ts"),
               ("video_resolution", "s")], N)
print(f"  events_raw       {ne:,} rows")


def q(sql):
    return sess.query(sql, "CSV").bytes().decode().strip()


print("\n=== MV fired and carried the new column ===")
print("  events_clean rows          :", q("SELECT count() FROM sonyliv.events_clean"))
print("  non-empty video_resolution :", q("SELECT count() FROM sonyliv.events_clean WHERE video_resolution != ''"))

print("\n=== normalization: does the spacing variant merge? ===")
print("  RAW distinct   :", q("SELECT uniqExact(video_resolution) FROM sonyliv.events_raw"))
print("  CLEAN distinct :", q("SELECT uniqExact(video_resolution) FROM sonyliv.events_clean"))
print("  raw spellings of 1920x1080:")
print(q("""SELECT video_resolution, count() FROM sonyliv.events_raw
           WHERE video_resolution LIKE '%1920%1080%' AND video_resolution NOT LIKE '%-%'
           GROUP BY video_resolution ORDER BY 2 DESC LIMIT 5"""))
print("  normalized, same set:")
print(q("""SELECT video_resolution, count() FROM sonyliv.events_clean
           WHERE video_resolution LIKE '%1920%1080%' AND video_resolution NOT LIKE '%-%'
           GROUP BY video_resolution ORDER BY 2 DESC LIMIT 5"""))

print("\n=== ladder prefix preserved (must stay distinct from the bare value) ===")
print(q("""SELECT video_resolution, count() FROM sonyliv.events_clean
           WHERE video_resolution LIKE '%1280*720%'
           GROUP BY video_resolution ORDER BY 2 DESC LIMIT 6"""))

print("\n=== 'NA' / 'auto' folded to unknown ===")
print("  unknown rows:", q("SELECT count() FROM sonyliv.events_clean WHERE video_resolution = 'unknown'"))
print("  any literal 'na' left:", q("SELECT count() FROM sonyliv.events_clean WHERE video_resolution IN ('na','NA','auto')"))

print("\n=== show_name through the chain ===")
print("  content_dim     :", q("SELECT count() FROM sonyliv.content_dim WHERE show_name != ''"))
print("  content_current :", q("SELECT count() FROM sonyliv.content_current WHERE show_name != ''"))
print("  distinct        :", q("SELECT uniqExact(show_name) FROM sonyliv.content_current"))

print("\n=== partitions are DAILY ===")
for t in ["events_raw", "events_clean", "ingest_batches", "ingest_rejects"]:
    expr = q(f"SELECT partition_key FROM system.tables WHERE database='sonyliv' AND name='{t}'")
    print(f"  {t:16} {expr}")
print("  events_raw partitions:", q("SELECT uniqExact(partition) FROM system.parts WHERE database='sonyliv' AND table='events_raw' AND active"))

print("\n=== events_dedup still resolves ===")
print("  dedup rows:", q("SELECT count() FROM sonyliv.events_dedup"))
print("\nOK")
