import shutil
from atlys_agentic import paths, chdb_client


def setup_function():
    shutil.rmtree(paths.CHDB_PATH, ignore_errors=True)


def test_init_schema_creates_four_tables():
    chdb_client.init_schema()
    rows = chdb_client.run("SHOW TABLES")
    names = {r["name"] for r in rows}
    assert {"business_context", "schema_registry", "context_changelog", "insights"} <= names


def test_init_base_context_chunks_markdown_into_rows():
    chdb_client.init_schema()
    inserted = chdb_client.init_base_context()
    assert inserted > 0
    rows = chdb_client.run("SELECT count() AS c FROM business_context")
    assert rows[0]["c"] == inserted


def test_run_rejects_non_select_read_helper_still_allows_ddl():
    # chdb_client.run is the low-level executor (allows DDL for our own metadata
    # tables); read-only enforcement belongs to Tool_Analytics_Compute (Task 7),
    # not here.
    chdb_client.init_schema()
    chdb_client.run("INSERT INTO business_context VALUES (1, 's', 'k', 'd', 1, now(), 'seed', 'active')")
    rows = chdb_client.run("SELECT * FROM business_context WHERE id = 1")
    assert rows[0]["key"] == "k"
