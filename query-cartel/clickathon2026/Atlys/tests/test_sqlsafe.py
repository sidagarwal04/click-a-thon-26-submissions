"""Tests for SQL literal / identifier escaping."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.sqlsafe import (  # noqa: E402
    require_safe_token,
    sanitize_identifier,
    sql_string_literal,
)


def test_sql_string_literal_doubles_quotes():
    assert sql_string_literal("shown") == "'shown'"
    assert sql_string_literal("o'brien") == "'o''brien'"
    assert sql_string_literal("a''b") == "'a''''b'"


def test_sql_string_literal_strips_nuls():
    assert sql_string_literal("a\x00b") == "'ab'"


def test_sanitize_identifier_accepts_dotted():
    assert sanitize_identifier("meta.pending_runs") == "meta.pending_runs"
    assert sanitize_identifier("express_checkout_events") == "express_checkout_events"


@pytest.mark.parametrize("bad", ["", "1abc", "a-b", "a;drop", "a b", "a'b"])
def test_sanitize_identifier_rejects(bad):
    with pytest.raises(ValueError):
        sanitize_identifier(bad)


def test_require_safe_token_uuid():
    rid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert require_safe_token(rid, what="run_id") == rid


@pytest.mark.parametrize("bad", ["", "not a uuid!", "'; DROP TABLE x;--", "a/b", "a b", "a'b"])
def test_require_safe_token_rejects(bad):
    with pytest.raises(ValueError):
        require_safe_token(bad, what="run_id")


def test_require_safe_token_allows_cli_and_e2e_prefixes():
    assert require_safe_token("cli-01_express_checkout")
    assert require_safe_token("e2e-01_express_checkout-abcd1234")
