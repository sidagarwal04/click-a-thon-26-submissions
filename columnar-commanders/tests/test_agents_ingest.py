"""Loading sampled events into the table the agent created (I9)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from prism_ch.agents.ingest import (
    build_rows,
    coerce,
    ingest_file,
    insertable_columns,
    resolve,
    unwrap,
)
from prism_ch.agents.types import ColumnSpec, TableSpec


def test_unwrap_strips_both_wrappers() -> None:
    assert unwrap("LowCardinality(String)") == ("String", False)
    assert unwrap("Nullable(DateTime64(3, 'UTC'))") == ("DateTime64(3, 'UTC')", True)
    assert unwrap("UInt8") == ("UInt8", False)


def test_dotted_paths_reach_flattened_fields() -> None:
    """The schema flattens `payment.amount` into `payment_amount`."""
    event = {"payment": {"amount": 49.5, "currency": "INR"}}
    assert resolve(event, "payment.amount") == 49.5
    assert resolve(event, "payment.missing") is None
    assert resolve(event, "absent.path") is None


def test_iso_timestamps_become_datetimes() -> None:
    got = coerce("2026-07-01T10:00:00Z", "DateTime64(3, 'UTC')")
    assert isinstance(got, datetime)
    assert got.tzinfo is not None and got.year == 2026


def test_absent_value_falls_back_to_the_columns_default() -> None:
    """A missing optional field is the common case, not an error."""
    assert coerce(None, "LowCardinality(String)") == ""
    assert coerce(None, "UInt8") == 0
    assert coerce(None, "Float64") == 0.0
    assert coerce(None, "Date") == date(1970, 1, 1)
    assert coerce(None, "DateTime") == datetime.fromtimestamp(0, tz=timezone.utc)


def test_nullable_keeps_none() -> None:
    assert coerce(None, "Nullable(String)") is None
    assert coerce(None, "Nullable(UInt32)") is None


def test_bad_numerics_do_not_fail_the_row() -> None:
    assert coerce("not-a-number", "UInt32") == 0
    assert coerce("nope", "Nullable(Float64)") is None


def test_booleans_and_nested_values_are_representable() -> None:
    assert coerce(True, "UInt8") == 1
    assert coerce({"a": 1}, "String") == '{"a": 1}'


def test_materialized_columns_are_excluded_from_inserts() -> None:
    """The server computes them; naming one in an INSERT is an error."""
    table = TableSpec(
        "t",
        [
            ColumnSpec("ts", "DateTime", source_field="ts"),
            ColumnSpec("event_date", "Date", materialized="toDate(ts)"),
            ColumnSpec("device", "LowCardinality(String)", source_field="device"),
        ],
        order_by=["device"],
    )
    assert [c.name for c in insertable_columns(table)] == ["ts", "device"]


def test_rows_map_flattened_and_missing_fields() -> None:
    table = TableSpec(
        "t",
        [
            ColumnSpec("ts", "DateTime64(3, 'UTC')", source_field="timestamp"),
            ColumnSpec("event_date", "Date", materialized="toDate(ts)"),
            ColumnSpec("device", "LowCardinality(String)", source_field="device"),
            ColumnSpec("payment_amount", "Float64", source_field="payment.amount"),
            ColumnSpec("coupon", "LowCardinality(String)", source_field="coupon"),
        ],
        order_by=["device"],
    )
    events = [
        {"timestamp": "2026-07-01T10:00:00Z", "device": "ios",
         "payment": {"amount": 49.5}, "coupon": "SAVE10"},
        {"timestamp": "2026-07-01T10:00:05Z", "device": "android"},
    ]
    names, rows = build_rows(events, table)

    assert names == ["ts", "device", "payment_amount", "coupon"]
    assert rows[0][2] == 49.5
    # Absent nested field and absent coupon fall back to the column defaults.
    assert rows[1][2] == 0.0
    assert rows[1][3] == ""


def test_event_mapping_is_used_when_no_source_field() -> None:
    table = TableSpec(
        "t", [ColumnSpec("device_type", "LowCardinality(String)")], order_by=["device_type"]
    )
    names, rows = build_rows(
        [{"device": "ios"}], table, mapping={"device": "device_type"}
    )
    assert names == ["device_type"]
    assert rows[0][0] == "ios"


def test_source_field_wins_over_the_mapping() -> None:
    """The column's own statement is the more specific one."""
    table = TableSpec(
        "t",
        [ColumnSpec("device_type", "LowCardinality(String)", source_field="platform")],
        order_by=["device_type"],
    )
    _, rows = build_rows(
        [{"platform": "ios", "device": "android"}], table, mapping={"device": "device_type"}
    )
    assert rows[0][0] == "ios"


def test_load_inserts_into_the_prefixed_table(make_settings) -> None:  # noqa: ANN001
    from prism_ch.agents.instrumentation import InstrumentationAgent
    from prism_ch.agents.types import SchemaProposal

    class Client:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def command(self, sql: str) -> None:
            self.commands.append(sql)

    client = Client()
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, client)

    proposal = SchemaProposal(
        tables=[
            TableSpec("demo_events", [ColumnSpec("device", "String", source_field="device")],
                      order_by=["device"], ttl="x")
        ]
    )
    events = [{"device": "ios"}, {"device": "web"}]

    results = agent.load_sample(proposal, events)
    assert len(results) == 1
    assert results[0].loaded == 2
    insert_sql = [s for s in client.commands if "INSERT INTO" in s]
    assert len(insert_sql) == 1
    assert "prism_demo_events" in insert_sql[0]


def test_mv_target_tables_are_not_loaded(make_settings) -> None:  # noqa: ANN001
    """MV targets are populated by their view, not by us."""
    from prism_ch.agents.instrumentation import InstrumentationAgent
    from prism_ch.agents.types import MaterializedViewSpec, SchemaProposal

    class Client:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def command(self, sql: str) -> None:
            self.commands.append(sql)

    client = Client()
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, client)

    proposal = SchemaProposal(
        tables=[
            TableSpec("agg", [ColumnSpec("a", "String")], order_by=["a"], ttl="x",
                      engine="AggregatingMergeTree"),
            TableSpec("raw_events", [ColumnSpec("a", "String", source_field="a")],
                      order_by=["a"], ttl="x"),
        ],
        materialized_views=[MaterializedViewSpec("mv", "agg", "SELECT a FROM raw_events", "w")],
    )
    results = agent.load_sample(proposal, [{"a": "x"}])
    assert len(results) == 1
    insert_sql = [s for s in client.commands if "INSERT INTO" in s]
    assert "prism_raw_events" in insert_sql[0]


def test_a_failed_load_does_not_abort_the_run(make_settings) -> None:  # noqa: ANN001
    """The tables exist; a load failure is reported, not fatal."""
    from prism_ch.agents.instrumentation import InstrumentationAgent
    from prism_ch.agents.types import SchemaProposal

    class Client:
        def command(self, sql: str) -> None:
            if "INSERT INTO" in sql:
                raise RuntimeError("Code: 53. Type mismatch")

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, Client())
    proposal = SchemaProposal(
        tables=[TableSpec("t", [ColumnSpec("a", "String", source_field="a")],
                          order_by=["a"], ttl="x")]
    )
    results = agent.load_sample(proposal, [{"a": "x"}])
    assert len(results) == 1
    assert results[0].loaded == 0
    assert results[0].error


# --- bulk file ingest ---------------------------------------------------------


def test_ingest_file_reads_ndjson(tmp_path) -> None:  # noqa: ANN001
    """NDJSON file is read line by line and inserted in batches."""
    f = tmp_path / "events.ndjson"
    f.write_text('{"device":"ios","ts":"2026-07-01"}\n{"device":"android","ts":"2026-07-02"}\n')

    table = TableSpec(
        "t",
        [ColumnSpec("device", "LowCardinality(String)", source_field="device"),
         ColumnSpec("ts", "String", source_field="ts")],
        order_by=["device"],
    )

    class Client:
        def __init__(self) -> None:
            self.inserts: list[dict] = []

        def insert(self, **kwargs: object) -> None:
            self.inserts.append(kwargs)

    client = Client()
    rows = ingest_file(client, database="db", physical_table="t", table=table,
                       data_path=str(f))
    assert rows == 2
    assert client.inserts[0]["data"] == [["ios", "2026-07-01"], ["android", "2026-07-02"]]


def test_ingest_file_reads_json_array(tmp_path) -> None:  # noqa: ANN001
    """A JSON array file is parsed as a single list."""
    f = tmp_path / "events.json"
    f.write_text('[{"a":"x"},{"a":"y"},{"a":"z"}]')

    table = TableSpec("t", [ColumnSpec("a", "String", source_field="a")], order_by=["a"])

    class Client:
        def __init__(self) -> None:
            self.inserts: list[dict] = []

        def insert(self, **kwargs: object) -> None:
            self.inserts.append(kwargs)

    client = Client()
    rows = ingest_file(client, database="db", physical_table="t", table=table,
                       data_path=str(f))
    assert rows == 3


def test_ingest_file_missing_raises() -> None:
    import pytest

    table = TableSpec("t", [ColumnSpec("a", "String")], order_by=["a"])

    class Client:
        def insert(self, **kwargs: object) -> None: ...

    with pytest.raises(FileNotFoundError):
        ingest_file(Client(), database="db", physical_table="t", table=table,
                    data_path="/nonexistent/file.ndjson")


def test_full_file_ingest_loads_all_rows(tmp_path) -> None:  # noqa: ANN001
    """ingest_file reads the full file and inserts all rows, not a sample."""
    f = tmp_path / "full.ndjson"
    f.write_text('{"device":"ios"}\n{"device":"web"}\n{"device":"android"}\n')

    table = TableSpec(
        "demo_events",
        [ColumnSpec("device", "String", source_field="device")],
        order_by=["device"],
    )

    class Client:
        def __init__(self) -> None:
            self.inserts: list[dict] = []

        def insert(self, **kwargs: object) -> None:
            self.inserts.append(kwargs)

    client = Client()
    loaded = ingest_file(client, database="atlys", physical_table="prism_demo_events",
                         table=table, data_path=str(f))
    assert loaded == 3
    assert client.inserts[0]["table"] == "prism_demo_events"
    assert len(client.inserts[0]["data"]) == 3
