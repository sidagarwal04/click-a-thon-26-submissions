"""Run the analytics agent on the real, executed forex_addon_events table.

Usage:
  .venv/bin/python scripts/run_analytics_forex.py
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

SPEC_PATH = pathlib.Path(
    "/Users/anshmehta/Downloads/Clickhouse Hackathon/click-a-thon-2026-main/Atlys/specs/05_instant_forex/spec.md"
)
SPEC_MARKDOWN = SPEC_PATH.read_text()
TABLE_NAME = "forex_addon_events"

print(f"Running analytics for spec=instant_forex, table={TABLE_NAME}")

meta_client = get_client(database="agent_meta")

with traced_run(agent="analytics", spec="instant_forex") as run:
    result = run_analytics(
        run=run,
        spec_name="instant_forex",
        table_name=TABLE_NAME,
        spec_markdown=SPEC_MARKDOWN,
        meta_client=meta_client,
    )

if result is None:
    print("SKIP — analytics agent not configured (LIBRECHAT_AGENT_ANALYTICS not set)")
    sys.exit(0)

print("\n── Result ──────────────────────────────────────────────────────────")
print(f"  title:      {result.get('title','')}")
print(f"  confidence: {result.get('confidence')}")
print(f"  segments:   {result.get('segment_cuts','')}")
print(f"  known_issues: {[ki.get('issue') for ki in result.get('related_known_issues',[]) if isinstance(ki,dict)]}")
print(f"  insight_id: {result.get('insight_id')}")
print(f"  report_html length: {len(result.get('report_html',''))}")
print(f"\n  summary:\n  {result.get('summary','')}")
