"""CLI — run the Atlys pipeline from the terminal.

Useful for the Day-2 runbook (no chat needed), for regression, and for CI:

    # full run against ClickHouse (CH_HOST set) with auto-approval
    python -m service.cli run 01_express_checkout --approve

    # same, but with no ClickHouse (in-memory DryRunStore)
    ATLYS_DRY_RUN=1 python -m service.cli run 01_express_checkout --approve

    # just interrogate a spec (no writes)
    python -m service.cli interrogate 01_express_checkout

Exit code is 0 on success, 1 on failure — CI-friendly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.app import create_app  # noqa: E402
from service.events import new_event  # noqa: E402


def _run(spec_dir: str, approve: bool) -> int:
    from service.app import _bootstrap

    app = create_app()
    state = app.state
    _bootstrap(state.settings, state.store, state.context)  # lifespan doesn't run in CLI
    run_id = f"cli-{spec_dir}"
    # one trace per run (session_id = run_id) — same contract as the MCP path
    trace_id = state.tracer.start(f"spec:{spec_dir}", session_id=run_id)

    state.bus.emit(new_event(
        "spec.run.requested", f"spec/{spec_dir}", "cli",
        payload={"spec_dir": spec_dir, "run_id": run_id},
        trace_id=trace_id,
    ))

    pending = state.store.query_rows(
        "SELECT run_id, state, schema_card FROM meta.pending_runs WHERE run_id = {r:String} "
        "ORDER BY created_at DESC LIMIT 1",
        {"r": run_id})
    if not pending:
        print(f"ERROR: no pending schema for {spec_dir}", file=sys.stderr)
        return 1

    print("== schema proposed (pending approval, D10) ==")
    print(pending[0]["schema_card"][:800] + ("..." if len(pending[0]["schema_card"]) > 800 else ""))

    if not approve:
        print("\nuse --approve to continue past the approval gate")
        return 0

    state.bus.emit(new_event(
        "schema.approved", f"run/{run_id}", "cli",
        payload={"run_id": run_id}, trace_id=trace_id,
    ))

    insight_rows = state.store.query_rows(
        "SELECT spec, title, summary, confidence, evidence, trace_id FROM meta.insights "
        "ORDER BY created_at DESC LIMIT 1")
    if not insight_rows:
        print("ERROR: no insight produced after approval", file=sys.stderr)
        return 1

    r = insight_rows[0]
    print("\n== insight card ==")
    print(f"title:      {r['title']}")
    print(f"confidence: {r['confidence']}")
    print(f"trace_id:   {r['trace_id']}")
    print(f"summary:    {r['summary']}")
    try:
        evidence = json.loads(r["evidence"])
        print(f"evidence:   {len(evidence)} rows")
        for e in evidence[:3]:
            print(f"  - [{e['kind']}] {e['label']}: {'OK' if 'rows' in e else 'ERROR'}")
    except Exception:  # noqa: BLE001
        pass
    return 0


def _interrogate(spec_dir: str) -> int:
    app = create_app()
    gaps = app.state.instrumentation.interrogate(spec_dir)
    print(json.dumps(gaps, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Atlys Copilot pipeline CLI")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run a spec end-to-end")
    r.add_argument("spec_dir")
    r.add_argument("--approve", action="store_true", help="auto-approve the schema (D10 gate)")

    i = sub.add_parser("interrogate", help="interrogate a spec (no writes)")
    i.add_argument("spec_dir")

    args = p.parse_args()
    if args.command == "run":
        return _run(args.spec_dir, args.approve)
    if args.command == "interrogate":
        return _interrogate(args.spec_dir)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
