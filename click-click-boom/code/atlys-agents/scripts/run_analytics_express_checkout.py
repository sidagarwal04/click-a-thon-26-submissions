"""Smoke test: run the analytics agent on express_checkout end-to-end.

Asserts:
  1. An insights row is written to agent_meta.insights
  2. Evidence contains at least one query with returned numbers
  3. Confidence is LOW given ~150 rows (> 0.85 on 150 rows = broken small-n gate)
  4. A Langfuse trace exists (trace_url is non-empty)
  5. title and summary are non-empty strings

Usage:
  .venv/bin/python scripts/run_analytics_express_checkout.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from agent_meta.db import get_client
from analytics.analytics_agent import run_analytics
from tracing import traced_run

# ── load the express_checkout spec ──────────────────────────────────────────

SPEC_PATH = pathlib.Path(__file__).resolve().parents[3] / "click-a-thon-2026" / "Atlys" / "specs" / "01_express_checkout" / "spec.md"

if not SPEC_PATH.exists():
    # Fallback inline spec summary for environments without the problem repo
    SPEC_MARKDOWN = """# Feature spec — Express Checkout
A one-tap checkout for returning travellers. Returning users with a saved payment
method see an Express button that skips the full form. Goal: cut time-to-pay and
lift the checkout → success conversion.

## Questions the PM will ask
- Does Express lift checkout → success conversion vs standard checkout?
- Is there a platform where OTP / payment fails more (iOS)? Cut by device_type / os.
- How much faster is Express (payment.latency_ms, shown→confirmed duration)?
- Which segments adopt Express most (device, geo, saved_method_type)?
"""
    TABLE_NAME = "express_checkout_events"
else:
    SPEC_MARKDOWN = SPEC_PATH.read_text()
    TABLE_NAME = "express_checkout_events"

# ── run ──────────────────────────────────────────────────────────────────────

print(f"Running analytics for spec=express_checkout, table={TABLE_NAME}")

meta_client = get_client(database="agent_meta")

with traced_run(agent="analytics_smoke", spec="express_checkout", run="smoke_test") as run:
    result = run_analytics(
        run=run,
        spec_name="express_checkout",
        table_name=TABLE_NAME,
        spec_markdown=SPEC_MARKDOWN,
        meta_client=meta_client,
    )

# ── assertions ───────────────────────────────────────────────────────────────

if result is None:
    print("SKIP — analytics agent not configured (LIBRECHAT_AGENT_ANALYTICS not set)")
    sys.exit(0)

failures = []

# 1. insight row written
insight_id = result.get("insight_id")
if not insight_id:
    failures.append("FAIL: insight_id missing — row was not written")
else:
    row = meta_client.query(
        "SELECT insight_id, confidence FROM agent_meta.insights WHERE insight_id = %(id)s",
        parameters={"id": insight_id},
    ).result_rows
    if not row:
        failures.append(f"FAIL: insight_id {insight_id} not found in agent_meta.insights")

# 2. report_html is a real, non-trivial standalone document (the agent now
#    explores and writes its own report instead of returning a seed-query
#    evidence blob — see analytics/analytics_agent.py's module docstring)
report_html = result.get("report_html", "")
if not report_html or len(report_html) < 200:
    failures.append("FAIL: report_html is empty or suspiciously short")
elif "<html" not in report_html.lower():
    failures.append("FAIL: report_html doesn't look like a standalone HTML document")

# 3. confidence is low given sparse data (< 0.85 expected)
confidence = result.get("confidence", 0.0)
if confidence > 0.85:
    failures.append(
        f"FAIL: confidence={confidence} > 0.85 on ~150 rows — small-n gate is broken"
    )

# 4. trace_url is set
trace_url = result.get("trace_url", "")
# trace_url is on the run, accessed via insight_id row
if insight_id:
    trow = meta_client.query(
        "SELECT trace_url FROM agent_meta.insights WHERE insight_id = %(id)s LIMIT 1",
        parameters={"id": insight_id},
    ).result_rows
    if not trow or not trow[0][0]:
        failures.append("FAIL: trace_url is empty in agent_meta.insights")

# 5. title and summary non-empty
if not result.get("title", "").strip():
    failures.append("FAIL: title is empty")
if not result.get("summary", "").strip():
    failures.append("FAIL: summary is empty")

# ── report ────────────────────────────────────────────────────────────────────

print("\n── Result ──────────────────────────────────────────────────────────")
print(f"  title:      {result.get('title','')}")
print(f"  confidence: {result.get('confidence')}")
print(f"  drivers:    {result.get('confidence_drivers','')}")
print(f"  segments:   {result.get('segment_cuts','')}")
print(f"  known_issues: {[ki.get('issue') for ki in result.get('related_known_issues',[]) if isinstance(ki,dict)]}")
print(f"  insight_id: {result.get('insight_id')}")
print(f"\n  summary:\n  {result.get('summary','')}")

if failures:
    print("\n── FAILURES ────────────────────────────────────────────────────────")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("\n── ALL ASSERTIONS PASSED ───────────────────────────────────────────")
    sys.exit(0)
