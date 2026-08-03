# One-Command Validated Load (`ingestion.cli load`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command — `python -m ingestion.cli load --db <name> <path>` — that auto-detects entities, validates rows through the existing ingestion pipeline, and inserts accepted rows into an explicitly named ClickHouse database with bootstrap/ordering/idempotency guards enforced by code.

**Architecture:** Four new focused modules plug into the existing `Source → normalize → schema → validate → Sink` pipeline without changing its shape: `detect.py` (entity/plan resolution), `sinks/clickhouse_sink.py` (the previously missing real sink), `bootstrap.py` (DDL, guards, dictionary reload), `loader.py` (orchestration; the CLI stays thin). Two small modifications to existing code: `_coerce_flag` rejects non-integral values, and the pipeline hands sinks Python-mode dicts.

**Tech Stack:** Python 3.12, pydantic v2, pandas/pyarrow (existing), `clickhouse-connect` + `python-dotenv` (new), pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-02-one-command-ingest-design.md` — read it before starting.
- **NEVER run `git commit` or `git push`** (user's standing rule). Leave all changes as uncommitted working-tree edits. Every "commit" step in a normal plan is replaced by "leave uncommitted" here.
- All module tests must pass offline: no live ClickHouse, no network. Live verification is one explicitly marked manual task at the end.
- `ingestion/` must not gain Python imports from `engine/`, `clickhouse/`, or `api/`. Reading `clickhouse/*.sql` as data files is allowed.
- Existing `batch`/`stream` CLI subcommands must keep working unchanged.
- Run tests with the scratch venv from the validation session, or any venv with `ingestion/requirements.txt` installed:
  `python -m venv .ingest-venv && .ingest-venv/bin/pip install -r ingestion/requirements.txt` (do Task 6's requirements edit first if creating a fresh venv).
- Test command base: `<venv>/bin/python -m pytest ingestion/tests -q` from the repo root `/home/sonupandit/Desktop/super-final-metics/metric-sherlock`.
- Env var names (from `utils/.env`, loaded via `python-dotenv`): `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DATABASE`, `CLICKHOUSE_SECURE`.

---

### Task 1: Reject non-integral funnel flags in `_coerce_flag`

**Files:**
- Modify: `ingestion/transformers.py:79-98` (`_coerce_flag`)
- Test: `ingestion/tests/test_transformers.py` (append)

**Interfaces:**
- Consumes: existing `_coerce_flag(v) -> Optional[int]` (None means "reject").
- Produces: same signature; new behavior: non-integral numerics return `None`. Existing callers (`normalize_ad_event`) need no change — they already treat `None` as a reject with the message `"{field}: could not parse {value!r} as 0/1"`.

- [ ] **Step 1: Write the failing tests**

Append to `ingestion/tests/test_transformers.py`:

```python
def test_fractional_flag_string_is_rejected_not_truncated():
    """'0.5' must NOT silently become 0 -- that is fabricated data."""
    raw = _valid_raw()
    raw["is_click"] = "0.5"
    row, errors, extra = normalize_ad_event(raw)
    assert row["is_click"] is None
    assert any("is_click" in e for e in errors)


def test_fractional_flag_float_is_rejected_not_truncated():
    raw = _valid_raw()
    raw["is_impression"] = 1.9
    row, errors, extra = normalize_ad_event(raw)
    assert row["is_impression"] is None
    assert any("is_impression" in e for e in errors)


def test_integral_float_flag_still_accepted():
    raw = _valid_raw()
    raw["is_filled"] = 1.0
    row, errors, extra = normalize_ad_event(raw)
    assert errors == []
    assert row["is_filled"] == 1
```

- [ ] **Step 2: Run tests to verify the two rejection tests fail**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_transformers.py -q -k fractional`
Expected: 2 FAIL (`row["is_click"] is None` — currently it is `0`).

- [ ] **Step 3: Implement**

In `ingestion/transformers.py`, replace the `float` and string-fallback branches of `_coerce_flag`:

```python
def _coerce_flag(v: Any) -> Optional[int]:
    if _is_null_token(v):
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        # 1.0 is a formatting artifact; 0.5 is garbled data, never truncate it.
        return int(v) if v.is_integer() else None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "yes", "y", "t"):
            return 1
        if s in ("0", "false", "no", "n", "f"):
            return 0
        try:
            f = float(s)
        except ValueError:
            return None
        return int(f) if f.is_integer() else None
    return None
```

- [ ] **Step 4: Run the whole suite**

Run: `<venv>/bin/python -m pytest ingestion/tests -q`
Expected: all pass (31 existing + 3 new).

- [ ] **Step 5: Leave changes uncommitted** (user commits themselves — never run `git commit`)

---

### Task 2: Pipeline hands sinks Python-mode dicts

**Files:**
- Modify: `ingestion/pipeline.py:137` (`_process` accepted branch)
- Test: `ingestion/tests/test_pipeline_batch.py` (append)

**Interfaces:**
- Consumes: `IngestionPipeline._process` currently returns `model.model_dump(mode="json")` for accepted rows.
- Produces: accepted payloads are now `model.model_dump()` (Python mode: `event_time` is a real `datetime`, `revenue` a `float`). `JsonlSink` already serializes datetimes via `json.dumps(..., default=str)`, so the dry-run path keeps working. Task 4's `ClickHouseSink` relies on receiving real `datetime` objects.

- [ ] **Step 1: Write the failing test**

Append to `ingestion/tests/test_pipeline_batch.py` (add `from datetime import datetime` at the top):

```python
def test_accepted_payloads_are_python_mode_for_sinks():
    """Sinks receive real datetime/float objects; JsonlSink stringifies at
    write time and ClickHouseSink inserts them natively."""
    rows = [
        {
            "event_time": "2026-06-01 12:00:00",
            "app_id": "app_1",
            "geo_device_id": "geo_1",
            "advertiser_id": "adv_1",
            "ad_format": "banner",
            "is_filled": 1,
            "is_impression": 1,
            "is_click": 0,
            "revenue": 1.0,
        }
    ]
    valid_sink = FakeSink()
    pipeline = IngestionPipeline(FakeSource(rows), valid_sink, FakeSink(), "ad_events", load_config())
    pipeline.run()
    payload = valid_sink.all_rows()[0]
    assert isinstance(payload["event_time"], datetime)
    assert isinstance(payload["revenue"], float)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_pipeline_batch.py -q -k python_mode`
Expected: FAIL — `event_time` is a `str` under `mode="json"`.

- [ ] **Step 3: Implement**

In `ingestion/pipeline.py` `_process`, change the accepted return:

```python
        return "accepted", model.model_dump(), extra_fields
```

- [ ] **Step 4: Run the whole suite + a JSONL round-trip sanity check**

Run: `<venv>/bin/python -m pytest ingestion/tests -q`
Expected: all pass (notably `test_jsonl_sink.py` and both pipeline tests — proving the dry-run JSONL path still emits valid JSON).

- [ ] **Step 5: Leave changes uncommitted**

---

### Task 3: Entity auto-detection (`ingestion/detect.py`)

**Files:**
- Create: `ingestion/detect.py`
- Test: `ingestion/tests/test_detect.py`

**Interfaces:**
- Consumes: `transformers._normalize_key`, `transformers.AD_EVENT_FIELDS/APP_FIELDS/ADVERTISER_FIELDS/GEO_DEVICE_FIELDS`.
- Produces (used by Task 6's loader):
  - `class EntityDetectionError(ValueError)`
  - `detect_entity_for_file(path: str) -> str` — returns one of `"ad_events" | "apps" | "advertisers" | "geo_device"`, raises `EntityDetectionError`.
  - `plan_path(path: str) -> List[Tuple[str, str]]` — `(entity, file_path)` pairs, **dimensions first, `ad_events` last**; works for a single file or a directory; raises `EntityDetectionError` when nothing is recognizable or one entity appears twice.

- [ ] **Step 1: Write the failing tests**

Create `ingestion/tests/test_detect.py`:

```python
import os

import pytest

from ingestion.detect import EntityDetectionError, detect_entity_for_file, plan_path


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_detects_by_filename_stem(tmp_path):
    p = str(tmp_path / "apps.txt")
    _write(p, "app_id,category,publisher_tier\n")
    assert detect_entity_for_file(p) == "apps"


def test_detects_ad_events_parquet_by_filename(tmp_path):
    p = str(tmp_path / "ad_events_v2.parquet")
    _write(p, "")  # filename wins; content never read
    assert detect_entity_for_file(p) == "ad_events"


def test_detects_by_csv_header_when_filename_unhelpful(tmp_path):
    p = str(tmp_path / "drop_2026_07.csv")
    _write(p, "GeoDeviceID,Region,Country,Device Model,OS Version\n")
    assert detect_entity_for_file(p) == "geo_device"


def test_unrecognizable_columns_raise_with_columns_listed(tmp_path):
    p = str(tmp_path / "mystery.csv")
    _write(p, "foo,bar\n")
    with pytest.raises(EntityDetectionError) as exc:
        detect_entity_for_file(p)
    assert "foo" in str(exc.value)


def test_plan_path_orders_dimensions_before_facts(tmp_path):
    _write(str(tmp_path / "ad_events.csv"), "event_time,app_id,geo_device_id,advertiser_id,ad_format,is_filled,is_impression,is_click,revenue\n")
    _write(str(tmp_path / "apps.txt"), "app_id,category,publisher_tier\n")
    _write(str(tmp_path / "geo_device.txt"), "geo_device_id,region,country,device_model,os_version\n")
    _write(str(tmp_path / "advertisers.txt"), "advertiser_id,vertical,campaign_type\n")
    _write(str(tmp_path / "notes.md"), "not data\n")
    plan = plan_path(str(tmp_path))
    entities = [e for e, _ in plan]
    assert entities == ["apps", "advertisers", "geo_device", "ad_events"]


def test_plan_path_single_file(tmp_path):
    p = str(tmp_path / "advertisers.txt")
    _write(p, "advertiser_id,vertical,campaign_type\n")
    assert plan_path(p) == [("advertisers", p)]


def test_plan_path_duplicate_entity_raises(tmp_path):
    _write(str(tmp_path / "apps.txt"), "app_id,category,publisher_tier\n")
    _write(str(tmp_path / "apps_old.csv"), "app_id,category,publisher_tier\n")
    with pytest.raises(EntityDetectionError):
        plan_path(str(tmp_path))


def test_plan_path_empty_dir_raises(tmp_path):
    with pytest.raises(EntityDetectionError):
        plan_path(str(tmp_path))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_detect.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.detect'`.

- [ ] **Step 3: Implement**

Create `ingestion/detect.py`:

```python
"""Entity auto-detection: filename stem first, column sniff as fallback.

`plan_path()` turns a file OR directory into an ordered ingestion plan --
dimensions before facts, because the rollup MVs enrich ad_events rows via
dictGet at insert time and must see fresh dimension labels.
"""

import os
from typing import List, Set, Tuple

from .transformers import (
    AD_EVENT_FIELDS,
    ADVERTISER_FIELDS,
    APP_FIELDS,
    GEO_DEVICE_FIELDS,
    _normalize_key,
)

# Dimensions first, facts last. Also the stem-match order: longer/more
# specific names checked before "apps" so "advertisers" never prefix-clashes.
INGEST_ORDER = ("apps", "advertisers", "geo_device", "ad_events")
_STEM_CHECK_ORDER = ("ad_events", "geo_device", "advertisers", "apps")

FIELDS_BY_ENTITY = {
    "ad_events": AD_EVENT_FIELDS,
    "apps": APP_FIELDS,
    "advertisers": ADVERTISER_FIELDS,
    "geo_device": GEO_DEVICE_FIELDS,
}


class EntityDetectionError(ValueError):
    pass


def _read_columns(path: str) -> Set[str]:
    if path.lower().endswith(".parquet"):
        import pyarrow.parquet as pq

        return set(pq.ParquetFile(path).schema_arrow.names)
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip("\r\n")
    return {c for c in header.split(",") if c.strip()}


def detect_entity_for_file(path: str) -> str:
    stem = os.path.basename(path).lower()
    for entity in _STEM_CHECK_ORDER:
        if stem.startswith(entity):
            return entity

    columns = {_normalize_key(c) for c in _read_columns(path)}
    matches = [e for e, fields in FIELDS_BY_ENTITY.items() if fields <= columns]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise EntityDetectionError(
            f"cannot detect entity for {path!r}: columns {sorted(columns)} "
            f"match no known entity"
        )
    raise EntityDetectionError(
        f"ambiguous entity for {path!r}: columns match {sorted(matches)}"
    )


def plan_path(path: str) -> List[Tuple[str, str]]:
    """(entity, file) pairs in ingestion order for a file or directory."""
    if os.path.isfile(path):
        return [(detect_entity_for_file(path), path)]
    if not os.path.isdir(path):
        raise EntityDetectionError(f"{path!r} is not a file or directory")

    found: dict = {}
    for fname in sorted(os.listdir(path)):
        if fname.startswith("."):
            continue
        fpath = os.path.join(path, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            entity = detect_entity_for_file(fpath)
        except EntityDetectionError:
            continue  # non-data file in the drop dir -- skip, don't fail the run
        if entity in found:
            raise EntityDetectionError(
                f"two files for entity '{entity}': {found[entity]!r} and {fpath!r}"
            )
        found[entity] = fpath
    if not found:
        raise EntityDetectionError(f"no recognizable data files in {path!r}")
    return [(e, found[e]) for e in INGEST_ORDER if e in found]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_detect.py -q`
Expected: 8 PASS. Then the whole suite: `<venv>/bin/python -m pytest ingestion/tests -q` — all pass.

- [ ] **Step 5: Leave changes uncommitted**

---

### Task 4: `ClickHouseSink` (`ingestion/sinks/clickhouse_sink.py`)

**Files:**
- Create: `ingestion/sinks/clickhouse_sink.py`
- Test: `ingestion/tests/test_clickhouse_sink.py`

**Interfaces:**
- Consumes: the `Sink` ABC (`ingestion/sinks/__init__.py`); Python-mode row dicts from Task 2.
- Produces (used by Task 6's loader):
  - `COLUMNS_BY_ENTITY: Dict[str, Tuple[str, ...]]`
  - `class ClickHouseSink(Sink)` — `__init__(self, client, max_retries: int = 3, backoff_seconds: float = 0.5, sleep=time.sleep)`; `write(entity, rows)` does one `client.insert(entity, data, column_names=...)` per call with bounded exponential-backoff retry. `client` is any object with `.insert(table, data, column_names=)` — `clickhouse_connect` client in production, a fake in tests.

- [ ] **Step 1: Write the failing tests**

Create `ingestion/tests/test_clickhouse_sink.py`:

```python
from datetime import datetime

import pytest

from ingestion.sinks.clickhouse_sink import COLUMNS_BY_ENTITY, ClickHouseSink


class FakeClient:
    def __init__(self, fail_times=0):
        self.fail_times = fail_times
        self.inserts = []

    def insert(self, table, data, column_names):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("transient")
        self.inserts.append((table, data, column_names))


def _row():
    return {
        "event_time": datetime(2026, 7, 6, 0, 0, 0),
        "app_id": "app_1",
        "geo_device_id": "gd_1",
        "advertiser_id": "adv_1",
        "ad_format": "banner",
        "is_filled": 1,
        "is_impression": 1,
        "is_click": 0,
        "revenue": 0.5,
    }


def test_writes_one_batched_insert_in_declared_column_order():
    client = FakeClient()
    ClickHouseSink(client).write("ad_events", [_row()])
    (table, data, column_names), = client.inserts
    assert table == "ad_events"
    assert tuple(column_names) == COLUMNS_BY_ENTITY["ad_events"]
    assert data == [[_row()[c] for c in column_names]]


def test_empty_rows_is_a_noop():
    client = FakeClient()
    ClickHouseSink(client).write("apps", [])
    assert client.inserts == []


def test_retries_transient_failure_then_succeeds():
    client = FakeClient(fail_times=2)
    slept = []
    sink = ClickHouseSink(client, max_retries=3, backoff_seconds=0.1, sleep=slept.append)
    sink.write("apps", [{"app_id": "a", "category": "gaming", "publisher_tier": "tier_1"}])
    assert len(client.inserts) == 1
    assert slept == [0.1, 0.2]  # exponential backoff


def test_raises_after_retries_exhausted():
    client = FakeClient(fail_times=3)
    sink = ClickHouseSink(client, max_retries=3, backoff_seconds=0.1, sleep=lambda s: None)
    with pytest.raises(ConnectionError):
        sink.write("apps", [{"app_id": "a", "category": "gaming", "publisher_tier": "tier_1"}])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_clickhouse_sink.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `ingestion/sinks/clickhouse_sink.py`:

```python
"""Real sink: batched INSERTs into ClickHouse via clickhouse-connect.

The pipeline already micro-batches (BATCH_MAX_ROWS/BATCH_MAX_SECONDS), so
each write() is one bounded, retried INSERT -- never a bare client call
(repo principle: bounded, resilient ClickHouse access).
"""

import time
from typing import Any, Dict, List

from . import Sink

COLUMNS_BY_ENTITY = {
    "ad_events": (
        "event_time", "app_id", "geo_device_id", "advertiser_id", "ad_format",
        "is_filled", "is_impression", "is_click", "revenue",
    ),
    "apps": ("app_id", "category", "publisher_tier"),
    "advertisers": ("advertiser_id", "vertical", "campaign_type"),
    "geo_device": ("geo_device_id", "region", "country", "device_model", "os_version"),
}


class ClickHouseSink(Sink):
    def __init__(self, client, max_retries: int = 3, backoff_seconds: float = 0.5, sleep=time.sleep):
        self.client = client
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep

    def write(self, entity: str, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        columns = COLUMNS_BY_ENTITY[entity]
        data = [[row[c] for c in columns] for row in rows]
        for attempt in range(self.max_retries):
            try:
                self.client.insert(entity, data, column_names=list(columns))
                return
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                self.sleep(self.backoff_seconds * (2 ** attempt))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_clickhouse_sink.py -q`
Expected: 4 PASS. Whole suite still green.

- [ ] **Step 5: Leave changes uncommitted**

---

### Task 5: Bootstrap, guards, and dictionary reload (`ingestion/bootstrap.py`)

**Files:**
- Create: `ingestion/bootstrap.py`
- Test: `ingestion/tests/test_bootstrap.py`

**Interfaces:**
- Consumes: a client object with `.command(sql)` (DDL/utility) and `.query(sql)` returning an object with `.result_rows` — matches `clickhouse_connect`; faked in tests.
- Produces (used by Task 6's loader):
  - `class LoadAbort(RuntimeError)` — human-actionable refusal (non-empty table, etc.).
  - `split_statements(sql_text: str) -> List[str]`
  - `ensure_schema(client, ddl_dir: str) -> bool` — creates tables/dictionaries/rollups if `ad_events` missing; returns True if it ran DDL.
  - `ensure_empty(client, entity: str, truncate: bool) -> None` — raises `LoadAbort` when non-empty and not truncating; truncating `ad_events` also truncates every MV target table discovered from `system.tables`.
  - `reload_dictionaries(client) -> None`
  - `dimensions_empty(client) -> bool`
  - Constants: `DDL_FILES = ("schema.sql", "dictionaries.sql", "rollups.sql")`, `DICTIONARIES = ("apps_dict", "advertisers_dict", "geo_device_dict")`, `DIMENSION_TABLES = ("apps", "advertisers", "geo_device")`.

- [ ] **Step 1: Write the failing tests**

Create `ingestion/tests/test_bootstrap.py`:

```python
import os

import pytest

from ingestion.bootstrap import (
    LoadAbort,
    dimensions_empty,
    ensure_empty,
    ensure_schema,
    reload_dictionaries,
    split_statements,
)


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    """Answers canned queries; records every command/query it receives."""

    def __init__(self, tables=(), counts=None, mv_targets=()):
        self.tables = list(tables)          # names in system.tables
        self.counts = dict(counts or {})    # table -> row count
        self.mv_targets = list(mv_targets)  # rollup target table names
        self.commands = []

    def command(self, sql):
        self.commands.append(sql)

    def query(self, sql):
        if "system.tables" in sql and "MaterializedView" in sql:
            return FakeResult([[t] for t in self.mv_targets])
        if "system.tables" in sql:
            return FakeResult([[t] for t in self.tables])
        if sql.startswith("SELECT count() FROM "):
            table = sql.rsplit(" ", 1)[1]
            return FakeResult([[self.counts.get(table, 0)]])
        raise AssertionError(f"unexpected query: {sql}")


def test_split_statements_strips_comments_and_empties():
    sql = """-- a comment
CREATE TABLE t (x Int32) ENGINE = MergeTree ORDER BY x;

-- another
SYSTEM RELOAD DICTIONARY foo;
"""
    stmts = split_statements(sql)
    assert len(stmts) == 2
    assert stmts[0].startswith("CREATE TABLE t")
    assert "comment" not in stmts[0]


def test_ensure_schema_runs_ddl_files_in_order_when_missing(tmp_path):
    for i, name in enumerate(("schema.sql", "dictionaries.sql", "rollups.sql")):
        (tmp_path / name).write_text(f"CREATE TABLE t{i} (x Int32) ENGINE = MergeTree ORDER BY x;")
    client = FakeClient(tables=[])
    assert ensure_schema(client, str(tmp_path)) is True
    assert [c for c in client.commands if c.startswith("CREATE")] == [
        "CREATE TABLE t0 (x Int32) ENGINE = MergeTree ORDER BY x",
        "CREATE TABLE t1 (x Int32) ENGINE = MergeTree ORDER BY x",
        "CREATE TABLE t2 (x Int32) ENGINE = MergeTree ORDER BY x",
    ]


def test_ensure_schema_noop_when_ad_events_exists(tmp_path):
    client = FakeClient(tables=["ad_events", "apps"])
    assert ensure_schema(client, str(tmp_path)) is False
    assert client.commands == []


def test_ensure_empty_passes_on_empty_table():
    ensure_empty(FakeClient(counts={"apps": 0}), "apps", truncate=False)


def test_ensure_empty_refuses_non_empty_without_truncate():
    with pytest.raises(LoadAbort) as exc:
        ensure_empty(FakeClient(counts={"apps": 2000}), "apps", truncate=False)
    assert "--truncate" in str(exc.value)


def test_truncate_dimension_truncates_only_itself():
    client = FakeClient(counts={"apps": 2000})
    ensure_empty(client, "apps", truncate=True)
    assert client.commands == ["TRUNCATE TABLE apps"]


def test_truncate_ad_events_also_truncates_discovered_rollup_targets():
    client = FakeClient(
        counts={"ad_events": 100},
        mv_targets=["hourly_overall", "hourly_by_region"],
    )
    ensure_empty(client, "ad_events", truncate=True)
    assert "TRUNCATE TABLE ad_events" in client.commands
    assert "TRUNCATE TABLE hourly_overall" in client.commands
    assert "TRUNCATE TABLE hourly_by_region" in client.commands


def test_reload_dictionaries_reloads_all_three():
    client = FakeClient()
    reload_dictionaries(client)
    assert client.commands == [
        "SYSTEM RELOAD DICTIONARY apps_dict",
        "SYSTEM RELOAD DICTIONARY advertisers_dict",
        "SYSTEM RELOAD DICTIONARY geo_device_dict",
    ]


def test_dimensions_empty_true_when_all_zero():
    assert dimensions_empty(FakeClient(counts={})) is True
    assert dimensions_empty(FakeClient(counts={"apps": 5})) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_bootstrap.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `ingestion/bootstrap.py`:

```python
"""Target-database preparation and safety guards for the `load` command.

Encodes the three ordering/idempotency rules that used to live in
operators' heads: DDL (with MVs) before facts, dimensions + dictionary
reload before facts, and never insert into a non-empty table without an
explicit --truncate (a second insert silently doubles all rollups).
"""

import os
from typing import List

DDL_FILES = ("schema.sql", "dictionaries.sql", "rollups.sql")
DICTIONARIES = ("apps_dict", "advertisers_dict", "geo_device_dict")
DIMENSION_TABLES = ("apps", "advertisers", "geo_device")


class LoadAbort(RuntimeError):
    """Refusal with a human-actionable message; not a crash."""


def split_statements(sql_text: str) -> List[str]:
    lines = [ln for ln in sql_text.splitlines() if not ln.lstrip().startswith("--")]
    statements = []
    for raw in "\n".join(lines).split(";"):
        stmt = raw.strip()
        if stmt:
            statements.append(stmt)
    return statements


def _existing_tables(client) -> set:
    res = client.query("SELECT name FROM system.tables WHERE database = currentDatabase()")
    return {row[0] for row in res.result_rows}


def ensure_schema(client, ddl_dir: str) -> bool:
    if "ad_events" in _existing_tables(client):
        return False
    for fname in DDL_FILES:
        path = os.path.join(ddl_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            for stmt in split_statements(f.read()):
                client.command(stmt)
    return True


def _rollup_targets(client) -> List[str]:
    # MV target tables ("TO <table>") -- the tables the fact insert repopulates.
    res = client.query(
        "SELECT extract(create_table_query, 'TO\\\\s+(?:\\\\S+\\\\.)?(\\\\w+)') AS target "
        "FROM system.tables "
        "WHERE database = currentDatabase() AND engine = 'MaterializedView'"
    )
    return sorted({row[0] for row in res.result_rows if row[0]})


def _row_count(client, table: str) -> int:
    return client.query(f"SELECT count() FROM {table}").result_rows[0][0]


def ensure_empty(client, entity: str, truncate: bool) -> None:
    count = _row_count(client, entity)
    if count == 0:
        return
    if not truncate:
        raise LoadAbort(
            f"table '{entity}' already has {count} rows -- inserting again would "
            f"double it (and, for ad_events, every rollup). Re-run with --truncate "
            f"to replace, or pick a fresh --db."
        )
    tables = [entity]
    if entity == "ad_events":
        tables += _rollup_targets(client)
    for table in tables:
        client.command(f"TRUNCATE TABLE {table}")


def reload_dictionaries(client) -> None:
    for name in DICTIONARIES:
        client.command(f"SYSTEM RELOAD DICTIONARY {name}")


def dimensions_empty(client) -> bool:
    return all(_row_count(client, t) == 0 for t in DIMENSION_TABLES)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_bootstrap.py -q`
Expected: 10 PASS. Whole suite still green.

Note on the `extract()` regex: it runs inside ClickHouse (RE2), not Python — the fake client matches on `"MaterializedView"` so the tests don't parse it. The live-verification task (Task 7) is what proves it against a real server.

- [ ] **Step 5: Leave changes uncommitted**

---

### Task 6: Loader orchestration + `load` subcommand + deps + README

**Files:**
- Create: `ingestion/loader.py`
- Modify: `ingestion/cli.py` (add `load` subparser + dispatch)
- Modify: `ingestion/requirements.txt` (add `clickhouse-connect`, `python-dotenv`)
- Modify: `ingestion/README.md` (document the command; drop the "dry-run only" claim)
- Test: `ingestion/tests/test_loader.py`

**Interfaces:**
- Consumes: `detect.plan_path`, `bootstrap.*` (Task 5 signatures), `ClickHouseSink`, `IngestionPipeline`, `FileSource`, `DeadLetterSink`, `load_config`.
- Produces:
  - `loader.run_load(path, db, truncate, force, out_dir, ddl_dir, cfg, client_factory, live_db) -> Dict[str, dict]` — per-entity stats dicts (the pipeline's `accepted/rejected/skipped/extra_fields_seen` plus nothing new). `client_factory(database: Optional[str])` returns a client; `live_db` is the engine's `CLICKHOUSE_DATABASE` value (or None).
  - CLI: `python -m ingestion.cli load --db NAME PATH [--truncate] [--force] [--out-dir DIR] [--ddl-dir DIR]`, exit 0 on success, exit 2 on `LoadAbort`/`EntityDetectionError` with the message on stderr.

- [ ] **Step 1: Write the failing tests**

Create `ingestion/tests/test_loader.py`:

```python
import pytest

from ingestion.bootstrap import LoadAbort
from ingestion.config import load_config
from ingestion.loader import run_load


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    def __init__(self, store):
        self.store = store  # shared dict: {"tables": set, "rows": {table: [..]}, "commands": []}

    def command(self, sql):
        self.store["commands"].append(sql)
        if sql.startswith("CREATE TABLE "):
            self.store["tables"].add(sql.split()[2])
        if sql.startswith("TRUNCATE TABLE "):
            self.store["rows"][sql.split()[-1]] = []

    def query(self, sql):
        if "system.tables" in sql and "MaterializedView" in sql:
            return FakeResult([])
        if "system.tables" in sql:
            return FakeResult([[t] for t in self.store["tables"]])
        if sql.startswith("SELECT count() FROM "):
            table = sql.rsplit(" ", 1)[1]
            return FakeResult([[len(self.store["rows"].get(table, []))]])
        raise AssertionError(f"unexpected query: {sql}")

    def insert(self, table, data, column_names):
        self.store["rows"].setdefault(table, []).extend(data)


@pytest.fixture()
def store():
    return {"tables": set(), "rows": {}, "commands": []}


@pytest.fixture()
def drop_dir(tmp_path):
    (tmp_path / "apps.txt").write_text(
        "app_id,category,publisher_tier\napp_1,gaming,tier_1\n"
    )
    (tmp_path / "advertisers.txt").write_text(
        "advertiser_id,vertical,campaign_type\nadv_1,gaming,CPM\n"
    )
    (tmp_path / "geo_device.txt").write_text(
        "geo_device_id,region,country,device_model,os_version\ngd_1,NAM,US,Pixel 9,15\n"
    )
    (tmp_path / "ad_events.csv").write_text(
        "event_time,app_id,geo_device_id,advertiser_id,ad_format,is_filled,is_impression,is_click,revenue\n"
        "2026-07-06 00:00:00,app_1,gd_1,adv_1,banner,1,1,0,0.002\n"
        "2026-07-06 00:00:01,app_1,gd_1,,popup,0,0,0,0\n"  # bad ad_format -> dead letter
    )
    return tmp_path


@pytest.fixture()
def ddl_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("ddl")
    (d / "schema.sql").write_text(
        "CREATE TABLE ad_events (x Int32) ENGINE = MergeTree ORDER BY x;\n"
        "CREATE TABLE apps (x Int32) ENGINE = MergeTree ORDER BY x;\n"
        "CREATE TABLE advertisers (x Int32) ENGINE = MergeTree ORDER BY x;\n"
        "CREATE TABLE geo_device (x Int32) ENGINE = MergeTree ORDER BY x;\n"
    )
    (d / "dictionaries.sql").write_text("-- none needed for fake\n")
    (d / "rollups.sql").write_text("-- none needed for fake\n")
    return d


def _run(drop_dir, ddl_dir, store, out_dir, **kw):
    return run_load(
        path=str(drop_dir),
        db="scratch_db",
        truncate=kw.get("truncate", False),
        force=kw.get("force", False),
        out_dir=str(out_dir),
        ddl_dir=str(ddl_dir),
        cfg=load_config(),
        client_factory=lambda database=None: FakeClient(store),
        live_db=kw.get("live_db", "ad_events_main"),
    )


def test_full_directory_load_orders_and_inserts(drop_dir, ddl_dir, store, tmp_path):
    stats = _run(drop_dir, ddl_dir, store, tmp_path / "out")
    assert stats["apps"]["accepted"] == 1
    assert stats["ad_events"]["accepted"] == 1
    assert stats["ad_events"]["rejected"] == 1
    assert len(store["rows"]["ad_events"]) == 1
    # dims inserted, dictionaries reloaded BEFORE facts inserted
    reload_idx = store["commands"].index("SYSTEM RELOAD DICTIONARY apps_dict")
    assert any(c.startswith("CREATE DATABASE IF NOT EXISTS") for c in store["commands"])
    assert reload_idx > 0
    # rejected row is dead-lettered to JSONL, never the DB
    assert (tmp_path / "out" / "ad_events.rejected.jsonl").exists()


def test_refuses_live_db_without_force(drop_dir, ddl_dir, store, tmp_path):
    with pytest.raises(LoadAbort) as exc:
        run_load(
            path=str(drop_dir), db="ad_events_main", truncate=False, force=False,
            out_dir=str(tmp_path / "out"), ddl_dir=str(ddl_dir), cfg=load_config(),
            client_factory=lambda database=None: FakeClient(store),
            live_db="ad_events_main",
        )
    assert "--force" in str(exc.value)


def test_second_run_refused_then_truncate_replaces(drop_dir, ddl_dir, store, tmp_path):
    _run(drop_dir, ddl_dir, store, tmp_path / "out")
    with pytest.raises(LoadAbort):
        _run(drop_dir, ddl_dir, store, tmp_path / "out")
    _run(drop_dir, ddl_dir, store, tmp_path / "out", truncate=True)
    assert len(store["rows"]["ad_events"]) == 1  # replaced, not doubled
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv>/bin/python -m pytest ingestion/tests/test_loader.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.loader'`.

- [ ] **Step 3: Implement the loader**

Create `ingestion/loader.py`:

```python
"""Orchestration for the `load` subcommand: bootstrap -> guards -> ordered
ingest through the standard pipeline with a ClickHouseSink.

Guards run for ALL planned entities before the first row is written, so a
mid-run abort can't leave a half-guarded state.
"""

import sys
from typing import Any, Callable, Dict, Optional

from . import bootstrap, detect
from .config import Config
from .pipeline import IngestionPipeline
from .sinks.clickhouse_sink import ClickHouseSink
from .sinks.dead_letter import DeadLetterSink
from .sources.file_source import FileSource


def run_load(
    path: str,
    db: str,
    truncate: bool,
    force: bool,
    out_dir: str,
    ddl_dir: str,
    cfg: Config,
    client_factory: Callable[..., Any],
    live_db: Optional[str],
) -> Dict[str, dict]:
    if live_db and db == live_db and not force:
        raise bootstrap.LoadAbort(
            f"--db {db!r} is the engine's live database (CLICKHOUSE_DATABASE). "
            f"Dimension files with reused IDs would silently relabel all "
            f"historical facts. Pass --force if you really mean it."
        )

    plan = detect.plan_path(path)

    admin = client_factory(database=None)
    admin.command(f"CREATE DATABASE IF NOT EXISTS `{db}`")
    client = client_factory(database=db)

    if bootstrap.ensure_schema(client, ddl_dir):
        print(f"bootstrapped schema + dictionaries + rollups in '{db}'")

    for entity, _ in plan:
        bootstrap.ensure_empty(client, entity, truncate)

    planned_entities = {entity for entity, _ in plan}
    stats: Dict[str, dict] = {}
    for entity, fpath in plan:  # plan is already dimensions-first
        if entity == "ad_events":
            bootstrap.reload_dictionaries(client)
            if planned_entities == {"ad_events"} and bootstrap.dimensions_empty(client):
                print(
                    "WARNING: dimension tables are empty -- ad_events rows will "
                    "enrich to '' labels in every hourly_by_* rollup",
                    file=sys.stderr,
                )
        pipeline = IngestionPipeline(
            source=FileSource(fpath, chunk_size=cfg.FILE_CHUNK_SIZE),
            valid_sink=ClickHouseSink(client),
            dead_letter_sink=DeadLetterSink(out_dir),
            entity=entity,
            cfg=cfg,
        )
        stats[entity] = pipeline.run()
    return stats
```

- [ ] **Step 4: Wire the CLI**

In `ingestion/cli.py`:

1. Add imports at the top:

```python
import os

from .bootstrap import LoadAbort
from .detect import EntityDetectionError
from .loader import run_load
```

2. In `build_parser()`, add after the `stream` subparser:

```python
    load_p = sub.add_parser("load", help="validate a file or directory and insert into ClickHouse")
    load_p.add_argument("path", help="data file or directory (entities auto-detected)")
    load_p.add_argument("--db", required=True, help="target ClickHouse database (always explicit)")
    load_p.add_argument("--truncate", action="store_true", help="empty target tables before inserting")
    load_p.add_argument("--force", action="store_true", help="allow --db to equal the live CLICKHOUSE_DATABASE")
    load_p.add_argument("--out-dir", default="./ingestion/_out", help="dead-letter destination")
    load_p.add_argument("--ddl-dir", default=None, help="directory holding schema.sql/dictionaries.sql/rollups.sql (default: <repo>/clickhouse)")
```

3. In `main()`, add a `load` branch before the batch/stream handling (early return):

```python
    if args.mode == "load":
        from dotenv import load_dotenv

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(repo_root, "utils", ".env"))
        ddl_dir = args.ddl_dir or os.path.join(repo_root, "clickhouse")

        def client_factory(database=None):
            import clickhouse_connect

            return clickhouse_connect.get_client(
                host=os.environ["CLICKHOUSE_HOST"],
                port=int(os.environ["CLICKHOUSE_PORT"]),
                username=os.environ["CLICKHOUSE_USER"],
                password=os.environ["CLICKHOUSE_PASSWORD"],
                secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
                **({"database": database} if database else {}),
            )

        try:
            stats = run_load(
                path=args.path,
                db=args.db,
                truncate=args.truncate,
                force=args.force,
                out_dir=args.out_dir,
                ddl_dir=ddl_dir,
                cfg=cfg,
                client_factory=client_factory,
                live_db=os.environ.get("CLICKHOUSE_DATABASE"),
            )
        except (LoadAbort, EntityDetectionError) as exc:
            print(f"aborted: {exc}", file=sys.stderr)
            return 2
        for entity, s in stats.items():
            line = f"{entity}: accepted={s['accepted']} rejected={s['rejected']} skipped={s['skipped']}"
            if s["extra_fields_seen"]:
                line += f" extra_fields={s['extra_fields_seen']}"
            print(line)
        return 0
```

- [ ] **Step 5: Update requirements and README**

`ingestion/requirements.txt` becomes:

```
pydantic>=2
pandas
pyarrow
pytest
clickhouse-connect
python-dotenv
```

`ingestion/README.md`: in the intro, replace the sentence claiming the sink is dry-run only with a sentence stating there are two sinks (JSONL dry-run for `batch`/`stream`, ClickHouse for `load`); add to the Usage section:

```bash
# One command: validate a whole drop (or one file) and insert into ClickHouse.
# --db is always explicit; refuses non-empty tables without --truncate;
# bootstraps schema/dictionaries/rollups in a fresh database automatically.
python -m ingestion.cli load --db unseen_v2 Unseen-data/
python -m ingestion.cli load --db unseen_v2 Unseen-data/ad_events.parquet --truncate
```

Also install the venv deps if the venv predates this task:
`<venv>/bin/pip install clickhouse-connect python-dotenv`

- [ ] **Step 6: Run the whole suite**

Run: `<venv>/bin/python -m pytest ingestion/tests -q`
Expected: all pass (existing + Tasks 1–6 tests). Also sanity-check the CLI parses:
`<venv>/bin/python -m ingestion.cli load --help` prints the new flags, and
`<venv>/bin/python -m ingestion.cli batch --help` still works.

- [ ] **Step 7: Leave changes uncommitted**

---

### Task 7: Live verification against ClickHouse Cloud (manual, destructive-scoped)

**Files:** none (operational verification only)

**Interfaces:** consumes the finished CLI from Task 6.

This is the only step that touches a real server. It writes ONLY to a scratch database `ingest_smoke`, verifies, then drops it. Do not target `ad_events_main` or `unseen_data`.

- [ ] **Step 1: Run the one command**

```bash
<venv>/bin/python -m ingestion.cli load --db ingest_smoke Unseen-data/
```

Expected output: a bootstrap line, then four stats lines ending with
`ad_events: accepted=1500000 rejected=0 skipped=0`.

- [ ] **Step 2: Reconcile against the numbers already verified in PROGRESS.md**

Run via a one-off python snippet with the same client factory (or `clickhouse-connect` shell): against database `ingest_smoke` —

```sql
SELECT count() FROM ad_events;                          -- expect 1500000
SELECT count() FROM apps;                               -- expect 2000
SELECT count() FROM advertisers;                        -- expect 500
SELECT count() FROM geo_device;                         -- expect 5000
SELECT round(sum(revenue), 4) FROM ad_events;           -- expect 2530.4381
SELECT count() FROM hourly_overall;                     -- expect 120 (5d x 24h)
SELECT sum(requests) FROM hourly_overall;               -- expect 1500000 (MV backfill worked)
```

- [ ] **Step 3: Verify the double-load guard live**

Re-run the same command **without** `--truncate`: expect exit code 2 and the
"already has ... rows" message; confirm `hourly_overall` still sums to 1,500,000
(nothing was doubled).

- [ ] **Step 4: Drop the scratch database**

```sql
DROP DATABASE ingest_smoke;
```

(Scratch DB created by this task; dropping it is in-scope. Nothing else is touched.)

- [ ] **Step 5: Report results to the user and leave all changes uncommitted**

---

## Self-Review (done at plan-writing time)

- **Spec coverage:** command surface + flags (Task 6), detection incl. directory ordering (Task 3), ClickHouseSink + python-mode payloads (Tasks 4, 2), bootstrap/guards/dict-reload/live-DB guard (Tasks 5, 6), `_coerce_flag` fix (Task 1), error handling (LoadAbort → exit 2, retries in sink, rejects dead-lettered — Tasks 4–6), offline tests + live reconciliation (every task + Task 7), deps + README (Task 6). No spec item without a task.
- **Placeholder scan:** all steps carry real code/commands; no TBDs.
- **Type consistency:** `client_factory(database=None)` used identically in loader and CLI; `LoadAbort`/`EntityDetectionError` raised where Task 6 catches them; `COLUMNS_BY_ENTITY` order matches `schemas.py` field order and `clickhouse/schema.sql` column order; fake clients implement exactly the `command/query/insert` surface the real `clickhouse_connect` client exposes.
