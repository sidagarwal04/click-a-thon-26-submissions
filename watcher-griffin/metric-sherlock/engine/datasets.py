"""The dataset registry: which ClickHouse databases this deployment can serve,
and which one the current unit of work is talking to.

WHY A DATABASE IS THE UNIT OF ISOLATION
---------------------------------------
The unseen-incident dataset is not more rows of the same world -- it is a
different world that happens to reuse the same identifiers. Measured on the two
drops: all 2,000 app_ids, 500 advertiser_ids and 5,000 geo_device_ids overlap,
but 1,854 apps, 475 advertisers and 4,983 geo profiles carry DIFFERENT
attributes. `gd_00000` is NAM/US/Galaxy A54/Android 12 in one and
APAC/ID/iPhone 14/iOS 17.5 in the other.

The dimension tables are ReplacingMergeTree keyed on the id alone, so loading one
drop's dimensions next to the other's would overwrite them and silently
invalidate every dimensional rollup and every band built from them. The two
datasets therefore cannot share a database, cannot share dimension tables, and
cannot be joined. One database each is the only correct arrangement -- and it is
cheap, because NO SQL ANYWHERE IN THIS REPO IS DATABASE-QUALIFIED: every query
uses bare table names against the connection's default database, so pointing the
connection at a different database repoints the entire system with no SQL change.

WHY A ContextVar AND NOT A PARAMETER
------------------------------------
The alternative is threading a `database` argument through ~40 call sites across
graph/rank/drilldown/sweep/cluster/ops_view/store/monitor_store. A ContextVar
carries it instead, which works because of one property of this codebase: every
ThreadPoolExecutor fan-out already funnels through tracing.in_parent_context()
(rank.py, drilldown.py, ops_view.py, sweep.py all call it, because OTel context
has the same problem). Teaching that ONE wrapper to carry the dataset covers
every worker thread in the system.

Do NOT be tempted to replace that with contextvars.copy_context(): a single
captured Context cannot be entered by two threads at once
("cannot enter context: is already entered"), and entering one per fan-out
worker concurrently is exactly what these call sites do.

FALLBACK IS THE WHOLE COMPATIBILITY STORY
-----------------------------------------
current_database() falls back to settings.clickhouse_database whenever nothing
has been set. That is what keeps every existing entry point -- the scanner
service, all three apply_* scripts, the CLIs, the test suite, and any API request
that does not name a dataset -- behaving exactly as it did before this module
existed. Selecting a dataset is additive; it is never required.
"""

import contextlib
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional

from engine.config import settings

# The primary dataset's key. Chosen when a request names nothing, so the
# pre-existing behaviour is the default behaviour.
DEFAULT_KEY = "main"


@dataclass(frozen=True)
class DatasetSpec:
    key: str          # stable API/URL token -- 'main' | 'unseen'
    label: str        # what a human sees in the switcher
    database: str     # the ClickHouse database this key resolves to
    note: str = ""    # why this dataset exists / what is different about it


# Built from config, never from literals, so a deployment can repoint either
# entry with an env var (CLICKHOUSE_DATABASE / CLICKHOUSE_UNSEEN_DATABASE).
#
# One honest caveat: in a process that overrides CLICKHOUSE_DATABASE -- the
# scanner-unseen service does exactly this -- 'main' resolves to that override.
# That is harmless because such a process works on a single dataset and never
# consults the registry; it takes the current_database() fallback instead. The
# API, which is the only consumer of the registry, does not override it.
DATASETS = {
    "main": DatasetSpec(
        key="main",
        label="Primary",
        database=settings.clickhouse_database,
        note="The full history the detector was calibrated on.",
    ),
    "unseen": DatasetSpec(
        key="unseen",
        label="Unseen incidents",
        database=settings.clickhouse_unseen_database,
        note=(
            "A separate world reusing the same ids with different attributes. "
            "Shorter history, so coarse grains legitimately report no band."
        ),
    ),
}


# Holds the KEY, not the database name: the key is what an API request carries and
# what an error message should quote back, and resolving late keeps the mapping in
# exactly one place.
_current: ContextVar[Optional[str]] = ContextVar("current_dataset", default=None)


class UnknownDataset(ValueError):
    """Raised for a dataset key that is not in the registry.

    A distinct type because the API turns this into a 400. Falling back to the
    default on an unrecognised key would silently show one dataset's numbers
    under another's name, which is the "fails silent-wrong" failure this whole
    module is built to avoid.
    """


def resolve(key: Optional[str]) -> DatasetSpec:
    """The spec for `key`, or the default dataset when key is None/empty."""
    if key is None or key == "":
        return DATASETS[DEFAULT_KEY]
    try:
        return DATASETS[key]
    except KeyError:
        raise UnknownDataset(
            f"unknown dataset {key!r}; valid keys are {sorted(DATASETS)}"
        ) from None


def all_datasets() -> list:
    """Registry order, primary first -- the order the switcher renders."""
    return [DATASETS[DEFAULT_KEY]] + [d for k, d in DATASETS.items() if k != DEFAULT_KEY]


def current_key() -> Optional[str]:
    """The key explicitly in force, or None when nothing was selected.

    None is meaningfully different from DEFAULT_KEY: it means "no selection
    happened", which is what makes the fallback in current_database() honour a
    process-level CLICKHOUSE_DATABASE override instead of overriding it back.
    """
    return _current.get()


def active_key() -> str:
    """The key to REPORT as active, for a response body or a log line.

    Falls back to whichever registry entry matches settings.clickhouse_database
    so an unselected request still names its dataset correctly, rather than
    claiming 'main' on a process pointed elsewhere.
    """
    key = _current.get()
    if key is not None:
        return key
    for k, spec in DATASETS.items():
        if spec.database == settings.clickhouse_database:
            return k
    return DEFAULT_KEY


def current_database() -> str:
    """The database every ClickHouse connection should be opened against.

    This is the single function ch_client.py asks, and the single reason no other
    module needs to know a dataset exists.
    """
    key = _current.get()
    if key is None:
        return settings.clickhouse_database
    return resolve(key).database


def set_current(key: Optional[str]) -> Token:
    """Sets the active dataset, returning a token for reset_current().

    Validates eagerly: a bad key must fail where it was supplied (an HTTP
    request, a --dataset flag), not later as a confusing query against the wrong
    database. Passing None is allowed and means "no selection", which is what
    in_parent_context replays into a worker thread that had none.
    """
    if key is not None:
        resolve(key)
    return _current.set(key)


def reset_current(token: Token) -> None:
    _current.reset(token)


def add_dataset_arg(parser) -> None:
    """Adds `--dataset` to a CLI, worded identically everywhere it appears.

    Preferred over exporting CLICKHOUSE_DATABASE around a command for two reasons.
    It is cross-platform (the env-var syntax differs between bash and PowerShell,
    and this repo ships deploy scripts for both), and it is what lets
    baselines_job assert the database it is about to TRUNCATE is the one that was
    asked for -- an ambient env var cannot be distinguished from a forgotten one.
    """
    parser.add_argument(
        "--dataset", type=str, default=None, choices=sorted(DATASETS),
        help="which dataset to run against (default: whatever CLICKHOUSE_DATABASE names)",
    )


def apply_dataset_arg(args) -> Optional[DatasetSpec]:
    """Activates `args.dataset` for the rest of the process, returning its spec.

    Returns None when the flag was absent, which the caller can distinguish from
    'main' -- absent means "use the process default", and that is not the same
    statement as "use the primary dataset".
    """
    key = getattr(args, "dataset", None)
    if key is None:
        return None
    spec = resolve(key)
    set_current(key)  # process-lifetime: never reset, this is a CLI entry point
    return spec


@contextlib.contextmanager
def use_dataset(key: Optional[str]):
    """Runs a block against `key`, restoring the previous selection afterwards.

    Exactly one yield on every path, including the error path -- the same rule
    engine/tracing.py's context managers follow, and for the same reason: a
    helper that swallows or duplicates the caller's exception turns a real error
    into an unrelated one.
    """
    token = set_current(key)
    try:
        yield resolve(key)
    finally:
        reset_current(token)
