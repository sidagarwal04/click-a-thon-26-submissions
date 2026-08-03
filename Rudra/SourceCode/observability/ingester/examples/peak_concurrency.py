"""
Example: drop-in traced analysis. No setup, no boilerplate — just import the toolkit.
Every query below is automatically traced and timed into ClickStack, so running the
benchmark set through this produces the query-latency evidence in HyperDX.

    uv run python examples/peak_concurrency.py
"""

from ingester import get_clickhouse


def main():
    ch = get_clickhouse()

    total = ch.query_rows(
        "SELECT count() AS events, uniqExact(video_session_id) AS sessions "
        "FROM sonyliv.raw_events",
        table="raw_events",
    )
    events, sessions = total[0]
    print(f"events={events}  distinct_sessions={sessions}")

    # Peak foreground concurrency from the serving table: per-minute sum, then max.
    peak = ch.query_rows(
        "SELECT max(c), argMax(minute, c) FROM ("
        "  SELECT minute, sum(cnt) AS c "
        "  FROM sonyliv.hist_minute_full GROUP BY minute"
        ")",
        table="hist_minute_full",
    )
    if peak:
        print(f"peak_foreground_concurrency={peak[0][0]}  at_minute={peak[0][1]} UTC")

    # Filtered example: peak on Android for live content (filter first, peak last).
    android_live = ch.query_rows(
        "SELECT max(c) FROM ("
        "  SELECT minute, sum(cnt) AS c FROM sonyliv.hist_minute_full "
        "  WHERE platform = 'android_phone' AND video_type = 'live' "
        "  GROUP BY minute"
        ")",
        table="hist_minute_full",
    )
    print(f"peak_android_live={android_live[0][0] if android_live else 0}")


if __name__ == "__main__":
    main()
