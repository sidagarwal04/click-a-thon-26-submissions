"""Small statistical helpers shared by the investigation stages."""


def median(values: list[float]) -> float:
    """Median of a small sample.

    Used instead of the mean everywhere a baseline is estimated, because
    baselines are drawn from the recent past and the recent past contains the
    previous anomalies. Averaging the trailing weeks lets one bad week set the
    expectation for the next: with 2026-06-21 down 44%, the mean baseline for
    2026-06-28 was dragged far enough down that an entirely ordinary day was
    reported as a +9% spike. The median of the same samples ignores it.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0
