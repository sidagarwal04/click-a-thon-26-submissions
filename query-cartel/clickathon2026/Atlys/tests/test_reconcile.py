"""Unit tests — reconciliation (Part 9: test_reconcile.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.reconcile import (  # noqa: E402
    diff_documented_vs_actual,
    parse_documented_tables,
    parse_metric_references,
    reconcile,
)

DOC = """## 3. The eight raw event tables

| Table | Kind | Emitted when | Key event-specific columns |
|-------|------|--------------|----------------------------|
| `destination_card_clicked` | funnel | user taps a destination card | `destination`, `visa_type`, `card_type`, `flow` |
| `document_uploaded` | funnel | passport image submitted | `doc_type`, `capture_mode`, `retry_count`, `is_crossed_failed_attempt_threshold` |
| `purchase_completed` | funnel | payment succeeds | `value`, `currency`, `coupon_applied` |

## 4. Metric definitions

**On-time delivery rate** = applications issued on or before `visa_issuance_eta_days`
÷ applications issued. (not computable from the funnel tables here.)
"""


def test_parse_documented_tables_excludes_table_name():
    tables = parse_documented_tables(DOC)
    assert "destination_card_clicked" in tables
    assert "destination" in tables["destination_card_clicked"]
    # the table's own name must NOT be counted as one of its columns
    assert "destination_card_clicked" not in tables["destination_card_clicked"]


def test_undocumented_and_phantom_columns():
    documented = {
        "destination_card_clicked": {"destination", "visa_type"},
        "purchase_completed": {"value", "currency"},
    }
    actual = {
        "destination_card_clicked": {"destination", "visa_type", "new_col"},
        "purchase_completed": {"value"},  # phantom: currency documented but missing
    }
    findings = diff_documented_vs_actual(documented, actual, [])
    kinds = {f.kind for f in findings}
    assert "undocumented_column" in kinds
    assert "phantom_column" in kinds
    assert any(f.object == "destination_card_clicked.new_col" for f in findings)
    assert any(f.object == "purchase_completed.currency" for f in findings)


def test_definition_gap():
    findings = diff_documented_vs_actual(
        {"x": {"a"}}, {"x": {"a"}}, ["visa_issuance_eta_days"]
    )
    assert any(f.kind == "definition_gap" for f in findings)


def test_known_issue_column_gap_t3_t4():
    # T3/T4: K2 needs scan_mode/failed_attempt_threshold, K6 needs
    # coupon_name/discount_amount — none present in the actual schema.
    findings = diff_documented_vs_actual({}, {}, [])
    gap_objects = {f.object for f in findings if f.kind == "known_issue_column_gap"}
    assert "K2→scan_mode" in gap_objects
    assert "K6→discount_amount" in gap_objects


def test_envelope_not_flagged_as_undocumented():
    # The 30-column common envelope is documented once in prose — never flagged.
    documented = {"x": {"a"}}
    actual = {"x": {"a", "id", "timestamp", "user_id", "os", "gclid", "duplicate_id"}}
    findings = diff_documented_vs_actual(documented, actual, [])
    assert all(f.object.split(".")[-1] not in {"id", "timestamp", "user_id", "os", "gclid"}
               for f in findings)


def test_metric_refs_parsed():
    refs = parse_metric_references(DOC)
    assert "visa_issuance_eta_days" in refs


def test_reconcile_merges_findings():
    actual = {"destination_card_clicked": {"destination", "visa_type", "brand_new_col"}}
    findings = reconcile(actual, DOC)
    kinds = {f.kind for f in findings}
    # documented-vs-actual diff + prose contradictions both present
    assert "undocumented_column" in kinds
    assert "contradiction" in kinds
