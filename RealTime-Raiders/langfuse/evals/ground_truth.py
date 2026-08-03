"""
ground_truth.py
---------------
Computes the correct answer for each eval question directly from ClickHouse.

This is what makes the concurrency pipeline stronger than a generic prompt-ops
loop. Most LLM evaluation asks a judge whether an answer "seems faithful".
Concurrency has a right answer: the peak IS a number, it DID occur at a
specific minute, and ClickHouse can tell us both. So correctness gets scored
deterministically and the judge is left to score only what is genuinely
subjective — tone, concision, usefulness.

Every query here follows the same three rules the agents are told to follow, so
the ground truth and the agent are held to one standard:
  1. collapse max-semantics rows before aggregating
  2. sum across dimensions, then max over minutes
  3. average divides by every minute in the range
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from langfuse_client import ch_client

_BASE = """
WITH base AS (
    SELECT minute, platform, country, video_type, content_id, max(sessions) AS sessions
    FROM conc_minute
    {where}
    GROUP BY minute, platform, country, video_type, content_id
),
per_minute AS (SELECT minute, sum(sessions) AS c FROM base GROUP BY minute)
"""


def _where(**filters) -> str:
    parts = [f"{k} = '{v}'" for k, v in filters.items() if v]
    return f"WHERE {' AND '.join(parts)}" if parts else ""


def data_range(ch) -> tuple[str, str]:
    r = ch.query("SELECT min(minute), max(minute) FROM conc_minute").result_rows[0]
    return str(r[0]), str(r[1])


def peak(ch, **filters) -> dict:
    """Peak concurrency, the minute it occurred, and the average over the span."""
    sql = _BASE.format(where=_where(**filters)) + """
        SELECT
            max(c)            AS peak,
            argMax(minute, c) AS peak_minute,
            round(sum(c) / greatest(1, dateDiff('minute', min(minute), max(minute)) + 1), 2) AS avg
        FROM per_minute
    """
    row = ch.query(sql).result_rows[0]
    return {"peak": int(row[0] or 0), "peak_minute": str(row[1]), "avg": float(row[2] or 0)}


def peak_by(ch, dimension: str, limit: int = 8) -> list[dict]:
    """Per-segment peak and peak minute — the evidence that peaks do not align."""
    col = {"platform": "platform", "country": "country", "video_type": "video_type"}[dimension]
    sql = f"""
    WITH base AS (
        SELECT minute, platform, country, video_type, content_id, max(sessions) AS sessions
        FROM conc_minute
        GROUP BY minute, platform, country, video_type, content_id
    ),
    per_seg AS (SELECT {col} AS seg, minute, sum(sessions) AS c FROM base GROUP BY seg, minute)
    SELECT seg, max(c) AS peak, argMax(minute, c) AS peak_minute
    FROM per_seg GROUP BY seg ORDER BY peak DESC LIMIT {int(limit)}
    """
    return [
        {"segment": str(s), "peak": int(p), "peak_minute": str(m)}
        for s, p, m in ch.query(sql).result_rows
    ]


def peak_users(ch, **filters) -> dict:
    where = _where(**filters)
    sql = f"""
        SELECT max(u) AS peak_users, argMax(minute, u) AS peak_minute
        FROM (
            SELECT minute, uniqExactMerge(users) AS u
            FROM conc_minute {where}
            GROUP BY minute
        )
    """
    row = ch.query(sql).result_rows[0]
    return {"peak_users": int(row[0] or 0), "peak_minute": str(row[1])}


def dimension_values(ch, column: str, limit: int = 5) -> list[str]:
    sql = f"""
        SELECT {column}, sum(sessions) AS sm
        FROM conc_minute GROUP BY {column} ORDER BY sm DESC LIMIT {int(limit)}
    """
    return [str(r[0]) for r in ch.query(sql).result_rows]


def top_content(ch, limit: int = 5) -> list[dict]:
    sql = f"""
    WITH base AS (
        SELECT minute, content_id, max(sessions) AS sessions
        FROM conc_minute GROUP BY minute, content_id
    ),
    per AS (SELECT content_id, minute, sum(sessions) AS c FROM base GROUP BY content_id, minute)
    SELECT content_id,
           joinGet('liv.content_join', 'title', content_id) AS title,
           max(c) AS peak, argMax(minute, c) AS peak_minute
    FROM per GROUP BY content_id ORDER BY peak DESC LIMIT {int(limit)}
    """
    return [
        {"content_id": int(c), "title": str(t), "peak": int(p), "peak_minute": str(m)}
        for c, t, p, m in ch.query(sql).result_rows
    ]


if __name__ == "__main__":
    ch = ch_client()
    lo, hi = data_range(ch)
    print(f"range: {lo} -> {hi}")
    print("overall:", peak(ch))
    print("by platform:", peak_by(ch, "platform"))
    print("users:", peak_users(ch))