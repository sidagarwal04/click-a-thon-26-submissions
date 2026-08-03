"""The UI's JSON handlers - thin wrappers, but `reset_local` is destructive
enough (drops tables) that its scoping deserves its own direct test."""

from __future__ import annotations

from prism_ch.ui import api


class FakeResult:
    def __init__(self, rows: list[tuple]) -> None:
        self.result_rows = rows


class FakeClient:
    """Records every DROP TABLE, and answers system.tables with a fixed set."""

    def __init__(self, tables: list[str]) -> None:
        self._tables = tables
        self.commands: list[str] = []

    def query(self, sql: str, parameters: dict | None = None):  # noqa: ANN201
        assert "system.tables" in sql
        return FakeResult([(t,) for t in self._tables])

    def command(self, sql: str) -> None:
        self.commands.append(sql)


_TABLES = [
    "destination_card_clicked",  # original event table - must survive
    "purchase_completed",  # original event table - must survive
    "prism_express_checkout_shown",  # agent-generated feature table
    "prism_otp_entered",  # agent-generated feature table
    "context_versions",  # context layer
    "context_entries",  # context layer
    "context_issues",  # context layer
    "context_embeddings",  # context layer
    "ui_schema_changes",  # UI history - out of scope, must survive
    "ui_agent_insights",  # UI history - out of scope, must survive
]


def test_reset_local_drops_only_prism_and_context_tables(make_settings, monkeypatch) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys")
    client = FakeClient(_TABLES)
    monkeypatch.setattr(api, "_client", lambda _settings: client)

    result = api.reset_local(settings, {})

    assert result["ok"] is True
    assert result["dropped"] == [
        "context_embeddings",
        "context_entries",
        "context_issues",
        "context_versions",
        "prism_express_checkout_shown",
        "prism_otp_entered",
    ]
    dropped_names = {cmd.split("`")[3] for cmd in client.commands}
    assert dropped_names == set(result["dropped"])
    # The original event tables and the UI's own history tables must never
    # appear in a DROP TABLE statement.
    for untouched in ("destination_card_clicked", "purchase_completed", "ui_schema_changes", "ui_agent_insights"):
        assert not any(untouched in cmd for cmd in client.commands)


def test_reset_local_reports_the_error_instead_of_raising(make_settings, monkeypatch) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys")

    class BrokenClient:
        def query(self, sql: str, parameters: dict | None = None):  # noqa: ANN201
            raise RuntimeError("connection refused")

    monkeypatch.setattr(api, "_client", lambda _settings: BrokenClient())

    result = api.reset_local(settings, {})

    assert result["ok"] is False
    assert "connection refused" in result["error"]
