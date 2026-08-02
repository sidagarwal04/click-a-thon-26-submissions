import os

# Force the stub LLM provider for the whole test suite, regardless of what's
# in utils/.env, so tests never make a real (paid, network-dependent) LLM
# call. Must run before anything imports engine.config, since Settings() is
# a module-level singleton read once at import time.
os.environ.setdefault("LLM_PROVIDER", "stub")

import pytest  # noqa: E402  (must come after the env var above)

# Cached across the session: [] = not probed yet, [None] = reachable,
# [str] = the reason it is not.
_CH_STATUS: list = []


def _clickhouse_unavailable_reason():
    """Why the live-ClickHouse tests cannot run, or None if they can.

    Probed once per session with a trivial query. The point is a HONEST skip: without this,
    a machine with no credentials sees `integration`-marked tests fail with a connection
    traceback, which reads as "the code is broken" rather than "this test needs a database".

    Deliberately fails CLOSED in only one direction: if the probe succeeds, nothing is
    skipped. A skip must never be able to hide a genuine failure, so the probe has to
    actually connect rather than just check that env vars are present.
    """
    # No env-var pre-check: credentials live in utils/.env and are read by engine.config,
    # NOT exported into os.environ. A first version of this probe checked
    # os.environ["CLICKHOUSE_HOST"] and skipped both integration tests on a machine where
    # ClickHouse was perfectly reachable -- the suite went from "33 passed" to "31 passed,
    # 2 skipped" and still looked green. Connecting is the only check that cannot lie.
    if not _CH_STATUS:
        try:
            from engine.ch_client import Trace, get_client

            get_client().query("SELECT 1 AS ok", step="conftest:probe", trace=Trace())
            _CH_STATUS.append(None)
        except Exception as e:
            _CH_STATUS.append(f"{type(e).__name__}: {e}")
    return _CH_STATUS[0]


def pytest_collection_modifyitems(config, items):
    """Skip `integration` tests when there is no live ClickHouse, with the reason attached.

    Only probes if something is actually marked `integration`, so the unit-only suite stays
    offline and fast.
    """
    marked = [i for i in items if i.get_closest_marker("integration")]
    if not marked:
        return
    reason = _clickhouse_unavailable_reason()
    if reason is None:
        return
    skip = pytest.mark.skip(reason=f"needs live ClickHouse -- {reason}")
    for item in marked:
        item.add_marker(skip)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Say whether the integration tests really ran.

    A suite that reports "42 passed" while silently skipping every test that touches the
    database is the kind of green that costs trust later.

    Reported here rather than in `pytest_report_header` because the header hook runs BEFORE
    collection, so the probe has not happened yet and the line came out blank -- which is
    exactly the sort of reassuring-but-empty output this is meant to prevent. Emitting it at
    the end also keeps the probe lazy: a unit-only run never pays for a network round-trip.
    """
    if not _CH_STATUS:
        return
    reason = _CH_STATUS[0]
    terminalreporter.write_line(
        "clickhouse: reachable -- integration tests ran" if reason is None
        else f"clickhouse: UNAVAILABLE -- integration tests SKIPPED ({reason})"
    )
