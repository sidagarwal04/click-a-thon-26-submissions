"""Run actual end-to-end pipeline for all 6 submission specs (01 to 06),
generate all submission deliverables in outputs/submission/{spec_id}/,
publish 100% public Langfuse traces, and output a validated trace index.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atlys_agentic import (
    ch_client,
    chdb_client,
    paths,
    tools,
    tracing,
)
from atlys_agentic.flows import analysis_flow, ingestion_flow


SPECS = [
    {
        "spec_id": "01_express_checkout",
        "table_name": "express_checkout",
        "question": "What is the checkout conversion rate for users who entered express checkout, broken down by device type and payment method?",
    },
    {
        "spec_id": "02_group_family",
        "table_name": "group_applications",
        "question": "How does application completion rate compare between solo applicants and group/family applications across destinations?",
    },
    {
        "spec_id": "03_status_sharing",
        "table_name": "status_sharing_events",
        "question": "What is the share rate and referral conversion of status sharing links by channel and destination?",
    },
    {
        "spec_id": "04_abandoned_checkout_recovery",
        "table_name": "abandoned_checkout_recovery",
        "question": "What is the recovery conversion rate of abandoned checkout reminders by notification channel and discount tier?",
    },
    {
        "spec_id": "05_instant_forex",
        "table_name": "instant_forex_orders",
        "question": "What is the attach rate and revenue impact of Instant Forex across different visa applicant destinations?",
    },
    {
        "spec_id": "06_unseen",
        "table_name": "promo_coupon_checkout",
        "question": "What is the coupon apply rate and valid versus rejected mix, and how does conversion compare to baseline?",
    },
]


def run_submission_for_spec(spec_info: dict[str, str]) -> dict[str, Any]:
    spec_id = spec_info["spec_id"]
    table_name = spec_info["table_name"]
    question = spec_info["question"]

    print(f"\n{'=' * 75}")
    print(f"🚀 RUNNING SUBMISSION PIPELINE FOR SPEC: {spec_id} (`{table_name}`)")
    print(f"{'=' * 75}")

    t_start = time.time()

    # 1. CUJ 1: Generate Proposal
    print(f"--- [CUJ 1] Generating Schema Proposal for {spec_id} ---")
    prop_state = ingestion_flow.generate_proposal(
        spec_id=spec_id,
        table_name=table_name,
        dry_run=False,
    )
    t_prop = time.time() - t_start
    cuj1_trace_id = prop_state.trace_id
    tracing.make_trace_public(cuj1_trace_id)
    cuj1_trace_url = prop_state.trace_url or f"https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/{cuj1_trace_id}"
    print(f"✅ Proposal Generated in {t_prop:.2f}s | Trace: {cuj1_trace_url}")

    # 2. CUJ 1: Deploy Approved Proposal
    print(f"--- [CUJ 1] Deploying Schema & Ingesting Events for {table_name} ---")
    deploy_state = ingestion_flow.deploy_approved_proposal(
        spec_id=spec_id,
        table_name=table_name,
        trace_id=cuj1_trace_id,
        dry_run=False,
    )
    tracing.make_trace_public(cuj1_trace_id)
    print(f"✅ Deployed: {deploy_state.ddl_result.get('status')} | Rows Verified: {deploy_state.load_result.get('verified_count')}")

    # Verify CUJ 1 Artifacts
    out_dir = paths.REPO_ROOT / "outputs" / "submission" / spec_id
    out_dir.mkdir(parents=True, exist_ok=True)
    schema_sql = out_dir / "schema.sql"
    run_report_md = out_dir / "run_report.md"
    run_report_json = out_dir / "run_report.json"

    assert schema_sql.exists(), f"Missing {schema_sql}"
    assert run_report_md.exists(), f"Missing {run_report_md}"
    assert run_report_json.exists(), f"Missing {run_report_json}"

    # 3. CUJ 2: Run Analytics Diagnostic
    print(f"--- [CUJ 2] Running Product Analyst on Question: '{question[:60]}...' ---")
    t_cuj2 = time.time()
    cuj2_res = analysis_flow.run(question=question, spec_id=spec_id)
    cuj2_latency = time.time() - t_cuj2
    cuj2_trace_id = cuj2_res.get("trace_id")
    tracing.make_trace_public(cuj2_trace_id)
    cuj2_trace_url = cuj2_res.get("trace_url") or f"https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/{cuj2_trace_id}"
    print(f"✅ CUJ 2 Complete in {cuj2_latency:.2f}s | Trace: {cuj2_trace_url}")

    # Emit CUJ 2 Artifacts
    insight_md_path = out_dir / "insight_report.md"
    insight_json_path = out_dir / "insight_report.json"

    insight_md_content = f"""# PM Insight Report — {table_name.replace('_', ' ').title()} (`{spec_id}`)

**Diagnostic Question:** {question}  
**Target Table:** `{cuj2_res.get('resolved_table')}`  
**Evaluation Timestamp:** {datetime.now(timezone.utc).isoformat()}  
**Public Langfuse Trace URL:** {cuj2_trace_url}  
**Calibrated Confidence Score:** {cuj2_res.get('confidence_score')}

---

## Executive Summary & Diagnostic Breakdown

{cuj2_res.get('answer_md') or cuj2_res.get('insight_report_md')}

---

### ClickHouse Query Execution & Signal Derivation
- **Resolved Table Engine:** `{cuj2_res.get('resolved_table')}` (Classification: `raw`)
- **Queries Executed:** {len(cuj2_res.get('planned_queries', []))} ClickHouse Cloud SQL statements
- **Anomalies / Signals Derived:** {len(cuj2_res.get('signals', []))}
- **Context Governance:** Synchronized with living `chDB` metadata and registered table semantics.

---
*Generated autonomously by Atlys Product Analyst Agent (CUJ 2) via ClickHouse Cloud.*
"""
    insight_md_path.write_text(insight_md_content, encoding="utf-8")

    insight_json_data = {
        "spec_id": spec_id,
        "table_name": cuj2_res.get("resolved_table"),
        "question": question,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": cuj2_trace_id,
        "trace_url": cuj2_trace_url,
        "confidence_score": cuj2_res.get("confidence_score"),
        "answerability": cuj2_res.get("answerability"),
        "signals": cuj2_res.get("signals", []),
        "planned_queries": cuj2_res.get("planned_queries", []),
    }
    insight_json_path.write_text(json.dumps(insight_json_data, indent=2), encoding="utf-8")

    total_time = time.time() - t_start

    return {
        "spec_id": spec_id,
        "table_name": table_name,
        "cuj1_trace_id": cuj1_trace_id,
        "cuj1_trace_url": cuj1_trace_url,
        "cuj2_trace_id": cuj2_trace_id,
        "cuj2_trace_url": cuj2_trace_url,
        "total_latency_s": round(total_time, 2),
        "verified_count": deploy_state.load_result.get("verified_count", 0),
        "confidence_score": cuj2_res.get("confidence_score"),
        "schema_sql": str(schema_sql),
        "run_report_md": str(run_report_md),
        "insight_report_md": str(insight_md_path),
    }


def main():
    print("=" * 80)
    print("🌟 EXECUTING LIVE SUBMISSION RUNS FOR ALL 6 SPECS (01 to 06)")
    print(f"   Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # Initialize local chDB schema and context
    chdb_client.init_schema()
    chdb_client.init_base_context()
    tools.Tool_Bootstrap_Base_Semantics(force=True)

    summaries = []
    for s in SPECS:
        try:
            res = run_submission_for_spec(s)
            summaries.append(res)
        except Exception as e:
            print(f"❌ Error on {s['spec_id']}: {e}")
            import traceback
            traceback.print_exc()

    # Flush all traces to Langfuse
    tracing.flush()
    tracing.publish_all_project_traces()

    print("\n" + "=" * 80)
    print("📊 CONSOLIDATED SUBMISSION DELIVERABLES & TRACE INDEX")
    print("=" * 80)
    print(f"{'Spec ID':<30} | {'Ingestion Trace (CUJ 1)':<45} | {'Analytics Trace (CUJ 2)'}")
    print("-" * 120)
    for res in summaries:
        print(f"{res['spec_id']:<30} | {res['cuj1_trace_url']:<45} | {res['cuj2_trace_url']}")

    summary_file = paths.REPO_ROOT / "outputs" / "submission_summary.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\n✅ Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
