"""Shared trailing-same-weekday baseline window, used by every detection
query. Robust (median) baseline, not mean - see EDGE_CASES.md for why."""

_WINDOW = "PARTITION BY {partition} ORDER BY day ROWS BETWEEN {trailing} PRECEDING AND 1 PRECEDING"


def window_clause(partition: str, trailing: int) -> str:
    return _WINDOW.format(partition=partition, trailing=trailing)


def baseline_select(metric_expr: str, partition: str, trailing: int) -> str:
    w = window_clause(partition, trailing)
    return f"""
        quantileExact(0.5)({metric_expr}) OVER ({w}) AS baseline_avg,
        avg({metric_expr}) OVER ({w}) AS baseline_mean,
        stddevPop({metric_expr}) OVER ({w}) AS baseline_stddev,
        count({metric_expr}) OVER ({w}) AS baseline_n
    """.strip()
