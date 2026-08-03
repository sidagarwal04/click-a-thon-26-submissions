"""Tests for MCP payload truncation."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.payloads import DEFAULT_LIST_LIMIT, truncate_for_mcp  # noqa: E402


def test_truncate_short_payload_unchanged():
    payload = {"run_id": "abc", "summary": "ok"}
    assert truncate_for_mcp(payload) == payload


def test_truncate_long_rows_list():
    payload = {
        "insight": {
            "summary": "fine",
            "evidence": [
                {"kind": "funnel_timing", "rows": [[f"u{i}", i, i + 1] for i in range(200)]}
            ],
        }
    }
    out = truncate_for_mcp(payload, list_limit=30)
    assert out["truncated"] is True
    rows = out["insight"]["evidence"][0]["rows"]
    assert len(rows) == 30
    assert out["insight"]["evidence"][0]["rows_total"] == 200


def test_default_list_limit_matches_aggregate_max():
    """MCP must not re-clip aggregate rows that CH already capped at 100."""
    assert DEFAULT_LIST_LIMIT == 100
    payload = {"rows": [{"destination": f"D{i}", "users": i} for i in range(100)]}
    out = truncate_for_mcp(payload)
    assert out.get("truncated") is not True
    assert len(out["rows"]) == 100


def test_truncate_hard_byte_cap():
    # nested evidence still too big after list slim → preview envelope
    huge = {"blob": "x" * 200_000}
    out = truncate_for_mcp(huge, max_bytes=2048, str_limit=500)
    assert out["truncated"] is True
    assert "preview" in out or len(json.dumps(out).encode()) <= 2048
    encoded = json.dumps(out, default=str).encode()
    assert len(encoded) <= 2048 or "preview" in out


def test_context_content_survives_default_str_limit():
    """Regression: 4k str_limit used to cut known-issues out of get_context."""
    body = ("A" * 4500) + "\n## 5. Known-issues log\nK1 — iOS WebKit OTP autofill\n"
    out = truncate_for_mcp({"version": 14, "content": body}, max_bytes=200_000)
    assert out.get("truncated") is not True
    assert "Known-issues" in out["content"]
    assert "OTP" in out["content"]
