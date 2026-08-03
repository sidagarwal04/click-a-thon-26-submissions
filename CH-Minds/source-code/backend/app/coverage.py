"""Day/hour completeness for the rollup - a partial day must be compared
against the same hour window on its baselines, not their full 24 hours.
See EDGE_CASES.md for the measured partial-day sign-flip this fixes."""
from typing import Optional

HOURS_IN_FULL_DAY = 24

_COVERAGE_QUERY = """
    SELECT toDate(hour) AS day, uniqExact(toHour(hour)) AS hours_present, max(toHour(hour)) AS max_hour
    FROM inmobi_rca.hourly_segment_metrics
    GROUP BY day
    ORDER BY day
"""


def day_coverage(client) -> dict:
    out = {}
    for day, hours_present, max_hour in client.query(_COVERAGE_QUERY).result_rows:
        out[day] = {
            "hours_present": int(hours_present),
            "max_hour": int(max_hour),
            "complete": int(hours_present) == HOURS_IN_FULL_DAY,
        }
    return out


def hour_cutoff_for(coverage: dict, day) -> Optional[int]:
    info = coverage.get(day)
    if info is None or info["complete"]:
        return None
    return info["max_hour"]


def hour_filter_sql(hour_cutoff: Optional[int]) -> str:
    if hour_cutoff is None:
        return ""
    return f"toHour(hour) <= {int(hour_cutoff)}"


def partial_days(coverage: dict) -> list:
    return [d for d, info in coverage.items() if not info["complete"]]


def describe(coverage: dict, day) -> Optional[str]:
    info = coverage.get(day)
    if info is None or info["complete"]:
        return None
    return (
        f"{day} is only partially loaded ({info['hours_present']}/24 hours, up to "
        f"{info['max_hour']:02d}:59). Compared against the same 00:00-{info['max_hour']:02d}:59 "
        "window on the trailing same-weekday baselines, not against their full days."
    )
