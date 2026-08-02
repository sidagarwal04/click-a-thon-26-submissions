"""Tests for the two-dataset switch.

Everything here exists because of a specific way this feature can fail SILENTLY. None of
these would raise on their own: an unkeyed client cache answers every query correctly,
just from the wrong database; a ContextVar that does not cross a thread boundary makes a
fan-out worker read the process default; a column missing from the DDL only surfaces as a
runtime insert error in a completely different module.
"""

import importlib.util
import os
import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from engine import datasets
from engine.config import settings

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# The registry and the ContextVar (no database needed)
# ---------------------------------------------------------------------------


def test_registry_maps_both_keys_to_distinct_databases():
    assert datasets.DATASETS["main"].database == settings.clickhouse_database
    assert datasets.DATASETS["unseen"].database == settings.clickhouse_unseen_database
    # If these ever collapse to one database the whole feature is a no-op that LOOKS like
    # it works -- both pills would show the same numbers under different labels.
    assert datasets.DATASETS["main"].database != datasets.DATASETS["unseen"].database


def test_unseen_database_env_var_is_actually_read():
    """CLICKHOUSE_UNSEEN_DATABASE sat in utils/.env with no reader for the whole build.

    Settings is declared extra="ignore", so pydantic discarded it in silence. This asserts
    the field exists and is non-empty, which is what makes the env var live.
    """
    assert getattr(settings, "clickhouse_unseen_database", "")


def test_no_selection_falls_back_to_the_process_default():
    """The compatibility guarantee: an unselected caller behaves exactly as before.

    current_key() is None rather than 'main' on purpose -- "nothing was selected" has to be
    distinguishable from "the primary was selected", or a scanner process pointed at another
    database by CLICKHOUSE_DATABASE would have its own configuration overridden.
    """
    assert datasets.current_key() is None
    assert datasets.current_database() == settings.clickhouse_database


def test_use_dataset_sets_and_restores():
    outer = datasets.current_database()
    with datasets.use_dataset("unseen"):
        assert datasets.current_database() == settings.clickhouse_unseen_database
        assert datasets.active_key() == "unseen"
    assert datasets.current_database() == outer
    assert datasets.current_key() is None


def test_use_dataset_restores_on_exception():
    """Exactly one yield on every path, including the error path -- the same contract the
    tracing context managers hold. A leaked selection would apply to whatever ran next."""
    with pytest.raises(ValueError):
        with datasets.use_dataset("unseen"):
            raise ValueError("boom")
    assert datasets.current_key() is None


def test_unknown_dataset_raises_rather_than_defaulting():
    """Falling back to the primary on an unrecognised key is the worst available failure:
    every number would be real, correctly computed, and about the wrong world."""
    with pytest.raises(datasets.UnknownDataset):
        datasets.resolve("nope")
    with pytest.raises(datasets.UnknownDataset):
        datasets.set_current("nope")
    # And the message has to name the valid options, since this reaches an HTTP 400.
    try:
        datasets.resolve("nope")
    except datasets.UnknownDataset as e:
        assert "main" in str(e) and "unseen" in str(e)


def test_empty_key_resolves_to_default():
    """An absent `?dataset=` must be the default, not an error -- this is what keeps every
    pre-existing request working unchanged."""
    assert datasets.resolve(None).key == datasets.DEFAULT_KEY
    assert datasets.resolve("").key == datasets.DEFAULT_KEY


def test_in_parent_context_carries_the_dataset_into_pool_workers():
    """A ContextVar does NOT cross a thread boundary.

    Every fan-out in the engine (rank, drilldown, ops_view, sweep) hands work to a
    ThreadPoolExecutor through this one wrapper. Without the dataset travelling with it, a
    worker resolves to the process default and queries the wrong database -- silently,
    because every query in this repo is unqualified and would answer perfectly well.
    """
    from engine.tracing import in_parent_context

    def observe(_):
        return datasets.current_database()

    for key in ("main", "unseen"):
        expected = datasets.resolve(key).database
        with datasets.use_dataset(key):
            worker = in_parent_context(observe)
            with ThreadPoolExecutor(max_workers=4) as pool:
                seen = set(pool.map(worker, range(8)))
        assert seen == {expected}, f"{key}: workers saw {seen}, expected {expected}"


def test_unwrapped_worker_does_not_inherit_the_dataset():
    """The negative control for the test above.

    If this ever starts inheriting the selection on its own, the wrapper has stopped being
    the thing that propagates it and the guarantee has moved somewhere untested.
    """
    def observe(_):
        return datasets.current_key()

    with datasets.use_dataset("unseen"):
        with ThreadPoolExecutor(max_workers=2) as pool:
            seen = set(pool.map(observe, range(4)))
    assert seen == {None}


def test_in_parent_context_resets_even_when_the_worker_raises():
    """Pool threads are reused, so a leaked selection would contaminate the next task."""
    from engine.tracing import in_parent_context

    def boom(_):
        raise RuntimeError("worker failed")

    with datasets.use_dataset("unseen"):
        worker = in_parent_context(boom)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(RuntimeError):
                list(pool.map(worker, [0]))
            # Same thread, fresh task: must not still be on 'unseen'.
            assert pool.submit(datasets.current_key).result() is None


# ---------------------------------------------------------------------------
# The schema drift that shipped (no database needed)
# ---------------------------------------------------------------------------


def _apply_monitoring():
    """Loads scripts/apply_monitoring.py without running it (it is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "apply_monitoring", os.path.join(REPO, "scripts", "apply_monitoring.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ddl_declares_every_column_monitor_store_writes():
    """THE TEST WHOSE ABSENCE LET THREE COLUMNS SHIP MISSING.

    `incidents.windows_spanned` and `sweep_{runs,coverage}.skipped_incomplete_window`
    existed in the primary database but not in clickhouse/monitoring_state.sql -- they had
    been applied out-of-band and never written back. Because engine/monitor_store.py names
    its columns explicitly, ANY database built from this repo's own DDL crashed on the first
    save_incidents: exactly the unseen-dataset path the project exists to serve. And
    `CREATE TABLE IF NOT EXISTS` cannot repair it, so re-running `ddl` reported success
    while changing nothing.

    Pure Python, no database: this compares the DDL file against the insert column lists,
    which is the invariant that actually matters and it holds on every machine.
    """
    from engine import monitor_store

    declared = _apply_monitoring().expected_columns(
        os.path.join(REPO, "clickhouse", "monitoring_state.sql")
    )
    for table, columns in (
        ("incidents", monitor_store._INCIDENT_COLUMNS),
        ("sweep_runs", monitor_store._RUN_COLUMNS),
        ("sweep_coverage", monitor_store._COVERAGE_COLUMNS),
        ("metric_events", monitor_store._EVENT_COLUMNS),
    ):
        assert table in declared, f"{table} is not declared in monitoring_state.sql"
        names = {c[0] for c in declared[table]}
        missing = [c for c in columns if c not in names]
        assert not missing, (
            f"{table}: monitor_store writes column(s) the DDL does not declare: {missing}. "
            "Add them to clickhouse/monitoring_state.sql AND run "
            "`python scripts/apply_monitoring.py columns` against every database -- "
            "CREATE TABLE IF NOT EXISTS will not add them."
        )


def test_ddl_parser_handles_the_types_this_repo_actually_uses():
    """The parser above is only trustworthy if it survives nested parens and defaults."""
    declared = _apply_monitoring().expected_columns(
        os.path.join(REPO, "clickhouse", "monitoring_state.sql")
    )
    incidents = dict((n, (t, d)) for n, t, d in declared["incidents"])
    assert incidents["breached_metrics"][0] == "Array(LowCardinality(String))"
    assert incidents["investigation_id"][0] == "Nullable(UUID)"
    assert incidents["windows_spanned"] == ("UInt16", "DEFAULT 1")
    events = dict((n, t) for n, t, _ in declared["metric_events"])
    assert events["incident_id"] == "Nullable(UUID)"


def test_no_sql_is_database_qualified():
    """The property the whole design rests on.

    Repointing the connection redirects every query only because no statement names a
    database. One `FROM ad_events_main.ad_events` anywhere would make that dataset's data
    leak into the other's console, and it would look completely correct.
    """
    offenders = []
    pattern = re.compile(
        r"\b(?:FROM|INTO|JOIN|TABLE)\s+(ad_events_main|unseen_data)\.", re.IGNORECASE
    )
    for folder in ("engine", "clickhouse", "api"):
        root = os.path.join(REPO, folder)
        for dirpath, _dirs, files in os.walk(root):
            if "__pycache__" in dirpath:
                continue
            for name in files:
                if not name.endswith((".py", ".sql")):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if pattern.search(line):
                            offenders.append(f"{os.path.relpath(path, REPO)}:{i}")
    assert not offenders, f"database-qualified table reference(s): {offenders}"


# ---------------------------------------------------------------------------
# Real isolation, against both live databases
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_get_client_is_keyed_by_database_on_one_thread():
    """The failure this feature could most easily have shipped.

    get_client() cached ONE client per thread with no database in the key. The API runs
    `uvicorn --workers 2` and FastAPI serves sync routes on a REUSED threadpool, so the
    second request on a given thread would have been served the first request's connection
    -- correct numbers, wrong dataset, no error.
    """
    from engine.ch_client import Trace, get_client

    def max_event_time(client):
        return client.query(
            "SELECT max(event_time) AS mx FROM ad_events", step="test:clock", trace=Trace()
        )[0]["mx"]

    with datasets.use_dataset("main"):
        main_client = get_client()
        main_clock = max_event_time(main_client)
    with datasets.use_dataset("unseen"):
        unseen_client = get_client()
        unseen_clock = max_event_time(unseen_client)

    assert main_client.database == settings.clickhouse_database
    assert unseen_client.database == settings.clickhouse_unseen_database
    assert main_client is not unseen_client
    # The datasets are non-overlapping in time, which is what makes the clock a reliable
    # fingerprint of which database answered.
    assert main_clock != unseen_clock

    # Re-entering must reuse the cached client rather than reconnecting -- the keying must
    # not have cost the per-thread caching that removed ~33 handshakes per investigation.
    with datasets.use_dataset("main"):
        assert get_client() is main_client


@pytest.mark.integration
def test_borrowed_client_pool_never_crosses_databases():
    """The idle pool was a flat list, so a borrower could be handed any database's
    connection. Alternating is what would have surfaced it."""
    from engine.ch_client import borrowed_client

    for key in ("main", "unseen", "main", "unseen"):
        expected = datasets.resolve(key).database
        with datasets.use_dataset(key):
            with borrowed_client() as client:
                assert client.database == expected


@pytest.mark.integration
def test_data_floor_is_cached_per_database():
    """sweep._DATA_FLOOR was a one-element process cache, described as "a property of the
    dataset" -- true, and exactly why two datasets need two entries.

    Unkeyed, the first sweep pins the floor for both. The unseen dataset starts later than
    the primary, so it would inherit an earlier floor and stop skipping windows that reach
    back before its own data -- reinstating the 67k-phantom-breach artefact the floor exists
    to prevent, through the floor's own cache.
    """
    from engine.sweep import data_floor

    with datasets.use_dataset("main"):
        main_floor = data_floor()
    with datasets.use_dataset("unseen"):
        unseen_floor = data_floor()

    assert main_floor is not None and unseen_floor is not None
    assert main_floor != unseen_floor
    # Cached value must still be per-database on a second call.
    with datasets.use_dataset("main"):
        assert data_floor() == main_floor


@pytest.mark.integration
def test_state_table_columns_match_the_ddl_in_both_databases():
    """Parity by NAME and TYPE, checked against the live databases.

    Not by ordinal: the primary carries impact_usd_per_day at position 27 because it arrived
    as an ALTER, where a database built from the file puts it at 15. That cannot be
    reconciled without recreating the table and does not matter, because every insert in
    engine/ passes explicit column_names.
    """
    from engine.ch_client import Trace, get_client

    declared = _apply_monitoring().expected_columns(
        os.path.join(REPO, "clickhouse", "monitoring_state.sql")
    )
    for key in ("main", "unseen"):
        database = datasets.resolve(key).database
        with datasets.use_dataset(key):
            rows = get_client().query(
                "SELECT table, name, type FROM system.columns "
                f"WHERE database = '{database}'",
                step="test:columns", trace=Trace(),
            )
        actual = {}
        for r in rows:
            actual.setdefault(r["table"], {})[r["name"]] = r["type"]
        for table in ("baselines", "metric_events", "incidents", "sweep_runs",
                      "sweep_coverage", "contribution"):
            have = actual.get(table)
            assert have is not None, f"{database}.{table} is missing"
            for name, ctype, _default in declared[table]:
                assert name in have, (
                    f"{database}.{table} is missing column {name} -- run "
                    f"`apply_monitoring.py columns` against it"
                )
                assert have[name] == ctype, (
                    f"{database}.{table}.{name} is {have[name]}, DDL says {ctype}"
                )
