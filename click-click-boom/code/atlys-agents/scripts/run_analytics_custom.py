"""Run the analytics agent on a free-text question, no specific spec/table in mind --
the counterpart to scripts/run_analytics_*.py (which are scoped to one already-executed
spec) for the standard-probe-style questions ("analyze the funnel", "where are we
losing conversions", ...). Same entry point the dashboard's "Custom question" tab uses
(analytics.analytics_agent.run_analytics_for_prompt).

Usage:
  .venv/bin/python scripts/run_analytics_custom.py "Where are we losing conversions, and for which segments (device / geo / destination)?"
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from analytics.analytics_agent import run_analytics_for_prompt

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} \"<question>\"")
        sys.exit(1)

    prompt = sys.argv[1]
    print(f"Running analytics agent on: {prompt!r}\n")
    result = run_analytics_for_prompt(prompt)

    print("\n── Result ──────────────────────────────────────────────────────────")
    print(f"  status:     {result.get('status')}")
    if result.get("status") == "failed":
        print(f"  error:      {result.get('error')}")
    else:
        print(f"  title:      {result.get('title')}")
        print(f"  confidence: {result.get('confidence')}")
        print(f"  insight_id: {result.get('insight_id')}")
    print(f"  trace_url:  {result.get('trace_url')}")
