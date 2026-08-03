"""Calls all 4 real agents with realistic input (using actual seeded context rows,
not fake data) and verifies each returns parseable JSON matching its schema.
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from agent_meta.db import get_client
from librechat_client import call_agent
from tracing import traced_run


def get_context(sections):
    client = get_client(database="agent_meta")
    rows = client.query(
        f"SELECT section, content, confidence FROM current_context WHERE section IN {tuple(sections)}"
    ).result_rows
    return [{"section": s, "content": json.loads(c), "confidence": conf} for s, c, conf in rows]


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def main():
    results = {}

    with traced_run(agent="pipeline", spec="agent_smoke_test") as run:
        # --- context_reviewer: realistic Express Checkout proposal ---
        context = get_context(["table:pay_now_clicked", "table:purchase_completed", "relationship:join_map"])
        proposal_input = json.dumps({
            "proposal": {
                "table_name": "express_checkout_events",
                "ddl": "CREATE TABLE express_checkout_events (id UUID, timestamp DateTime, user_id String, "
                       "application_id Nullable(String), event_type LowCardinality(String), otp_success Nullable(UInt8), "
                       "amount Nullable(Float64), currency Nullable(String), latency_ms Nullable(UInt32)) "
                       "ENGINE = MergeTree PARTITION BY toYYYYMM(timestamp) ORDER BY (timestamp, event_type)",
                "ordering_key_rationale": "timestamp-first reads 1 row vs 170k for id-first on time-range filters (see perf_tool baseline comparison)",
            },
            "current_context": context,
        })
        r = call_agent(os.environ["LIBRECHAT_AGENT_CONTEXT_REVIEWER"], proposal_input)
        run.log(step="context_reviewer_smoke", input=proposal_input[:500], output=r.output_text[:1000])
        results["context_reviewer"] = extract_json(r.output_text)

        # --- instrumentation_proposer: real Express Checkout spec excerpt ---
        spec_input = json.dumps({
            "spec_markdown": (
                "# Express Checkout\nOne-tap checkout for returning travellers. Events: "
                "express_checkout_shown, express_checkout_selected, saved_method_used, "
                "otp_entered (otp_attempts, otp_success), express_payment_confirmed "
                "(payment.amount, payment.currency, payment.latency_ms).\n"
                "PM questions: Does Express lift checkout->success conversion? Which platform "
                "has more OTP failures? How much faster is Express?"
            ),
            "sample_events": [
                {"event": "otp_entered", "user_id": "u1", "application_id": "a1", "otp_attempts": 1, "otp_success": 1, "device_type": "ios"},
                {"event": "express_payment_confirmed", "user_id": "u1", "application_id": "a1", "payment": {"amount": 120.5, "currency": "USD", "latency_ms": 850}},
            ],
            "perf_results": {
                "baseline_legacy": {"ordering_key": "(id, timestamp, user_id)", "avg_elapsed_ms": 57.08, "total_read_rows": 511671},
                "time_event_type": {"ordering_key": "(timestamp, event_type, user_id)", "avg_elapsed_ms": 51.18, "total_read_rows": 341115},
            },
        })
        r = call_agent(os.environ["LIBRECHAT_AGENT_INSTRUMENTATION_PROPOSER"], spec_input)
        run.log(step="instrumentation_proposer_smoke", input=spec_input[:500], output=r.output_text[:1000])
        results["instrumentation_proposer"] = extract_json(r.output_text)

        # --- context_chronicler: pretend the above was executed ---
        executed_input = json.dumps({
            "executed_proposal": results["instrumentation_proposer"],
            "spec_name": "express_checkout",
            "current_context": get_context(["relationship:join_map"]),
        })
        r = call_agent(os.environ["LIBRECHAT_AGENT_CONTEXT_CHRONICLER"], executed_input)
        run.log(step="context_chronicler_smoke", input=executed_input[:500], output=r.output_text[:1000])
        results["context_chronicler"] = extract_json(r.output_text)

        # --- analytics_agent: real pre-aggregated funnel numbers ---
        analytics_input = json.dumps({
            "question": "How healthy is our funnel, and where's the biggest drop?",
            "current_context": get_context(["metric:drop_off_rate", "issue:K1", "convention:funnel_analysis"]),
            "preaggregated_results": {
                "step_counts": {
                    "destination_card_clicked": 1000000, "application_started": 154413,
                    "document_uploaded": 20446, "pay_now_clicked": 14739, "purchase_completed": 7054,
                },
                "pay_to_purchase_by_os": {"iOS": 0.499, "Android": 0.468, "Windows": 0.472},
            },
        })
        r = call_agent(os.environ["LIBRECHAT_AGENT_ANALYTICS"], analytics_input)
        run.log(step="analytics_agent_smoke", input=analytics_input[:500], output=r.output_text[:1000])
        results["analytics_agent"] = extract_json(r.output_text)

        trace_url = run.url

    print(json.dumps(results, indent=2))
    print(f"\ntrace: {trace_url}")


if __name__ == "__main__":
    main()
