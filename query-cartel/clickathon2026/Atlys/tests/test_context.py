"""Unit tests — context agent helpers (Part 9: test_context.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.agents.context import _clean_title, parse_known_issues  # noqa: E402
from service.reconcile import detect_contradictions  # noqa: E402

BASE_CONTEXT = """# Atlys Analytics — Base Context Layer

## 1. Business overview
...conversion...

## 4. Metric definitions

**Conversion rate** = completed purchases ÷ **sessions**. A session is a single
app-open / web visit.

**On-time delivery rate** = applications issued on or before `visa_issuance_eta_days`
÷ applications issued. (Reported by the fulfilment team from post-purchase systems;
not computable from the funnel tables here.)

## 5. Known-issues log

1. **K1 — iOS WebKit OTP autofill regression.** On recent iOS builds the payment OTP
   field fails to autofill, and some users abandon at the pay step.
2. **K2 — Passport scan model update (Apr 2026).** The on-device passport model was
   updated in early April.
3. **K6 — SUMMER20 coupon campaign.** A `SUMMER20` promo ran in Q2; expect elevated
   `coupon_applied` and lower realised `value`.
"""


def test_parse_known_issues():
    issues = parse_known_issues(BASE_CONTEXT)
    ids = [i["issue_id"] for i in issues]
    assert "K1" in ids and "K2" in ids and "K6" in ids
    k1 = next(i for i in issues if i["issue_id"] == "K1")
    assert "OTP autofill" in k1["title"]
    assert k1["evidence"]  # evidence hint populated


def test_clean_title():
    assert _clean_title("iOS WebKit OTP autofill regression.") == "iOS WebKit OTP autofill regression"
    assert _clean_title("  padded  text  ") == "padded text"


def test_detect_contradictions_t8_naming_drift():
    md = "the application carries `visa_issuance_eta_days` ... the DDL says `eta_shown`"
    findings = detect_contradictions(md)
    assert any("visa_issuance_eta_days" in f.object for f in findings)


def test_detect_contradictions_t1_denominators():
    md = "conversion ÷ destination_card_clicked ... conversion ÷ application_started ... ÷ sessions"
    findings = detect_contradictions(md)
    assert any("denominators" in f.object for f in findings)


def test_detect_contradictions_t7_out_of_scope():
    md = "On-time delivery rate: not computable from the funnel tables here."
    findings = detect_contradictions(md)
    assert any("on-time delivery rate" in f.object for f in findings)
