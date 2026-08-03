"""Run the analytics agent on the real, executed visa_status_sharing_events table.

Usage:
  .venv/bin/python scripts/run_analytics_status_sharing.py
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
    "/Users/anshmehta/Downloads/Clickhouse Hackathon/click-a-thon-2026-main/Atlys/specs/03_status_sharing/spec.md"
)
SPEC_MARKDOWN = SPEC_PATH.read_text()
TABLE_NAME = "visa_status_sharing_events"

print(f"Running analytics for spec=status_sharing, table={TABLE_NAME}")

meta_client = get_client(database="agent_meta")

with traced_run(agent="analytics", spec="status_sharing") as run:
    result = run_analytics(
        run=run,
        spec_name="status_sharing",
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
print(f"\n  summary:\n  {result.get('summary','')}")
print(json.dumps(result, indent=2, default=str))
