"""Unit tests — known-issue correlation (Part 9: test_correlation.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.agents.correlation import correlate  # noqa: E402

KNOWN = [
    {"issue_id": "K1", "title": "iOS WebKit OTP autofill regression"},
    {"issue_id": "K2", "title": "Passport scan model update"},
    {"issue_id": "K4", "title": "Schengen summer slot scarcity"},
    {"issue_id": "K6", "title": "SUMMER20 coupon campaign"},
    {"issue_id": "K7", "title": "App 7.45 rollout"},
]


def test_k1_triggers_on_otp_evidence():
    # a real run's funnel SQL references the otp_entered event (otp context)
    evidence = [
        {"label": "funnel step-through", "kind": "funnel",
         "sql": "SELECT uniqIf(user_id, event = 'otp_entered') AS u3 FROM t",
         "rows": [[100, 90, 85, 80]]},
        {"label": "segment skew by os", "kind": "segment", "sql": "SELECT ...",
         "rows": [["iOS", 100, 91], ["Android", 100, 98]]},
        {"label": "segment skew by geoip_country_code", "kind": "segment",
         "sql": "SELECT ...", "rows": [["AE", 100, 70]]},
    ]
    matched = correlate(evidence, "express_checkout_events", "express_checkout", KNOWN)
    assert "K1" in [m["issue_id"] for m in matched]


def test_k1_does_not_trigger_without_otp_context():
    evidence = [
        {"label": "segment skew by os", "kind": "segment", "sql": "SELECT ...",
         "rows": [["iOS", 100, 91], ["Android", 100, 98]]},
    ]
    # no "otp" anywhere → K1 must NOT fire (no crying wolf)
    matched = correlate(evidence, "t", "f", KNOWN)
    assert "K1" not in [m["issue_id"] for m in matched]


def test_k4_triggers_on_schengen_destination():
    evidence = [
        {"label": "segment skew by destination", "kind": "segment", "sql": "...",
         "rows": [["DE", 500, 400], ["FR", 300, 200], ["US", 200, 100]]},
    ]
    matched = correlate(evidence, "t", "f", KNOWN)
    assert "K4" in [m["issue_id"] for m in matched]


def test_k6_triggers_on_summer20_coupon():
    evidence = [
        {"label": "event overview", "kind": "overview", "sql": "SELECT coupon_name ...",
         "rows": [["SUMMER20", 10]]},
    ]
    matched = correlate(evidence, "t", "f", KNOWN)
    assert "K6" in [m["issue_id"] for m in matched]


def test_unknown_issue_skipped():
    matched = correlate([], "t", "f", KNOWN)
    assert matched == []
