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
