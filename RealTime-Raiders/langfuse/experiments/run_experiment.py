"""
run_experiment.py
-----------------
Runs a Langfuse experiment against the LIVE agent.

The task calls lc-agent over HTTP, so every run exercises the real thing: the
MCP tools, the Langfuse-served prompt, the supervisor's routing. A prompt that
scores well here is a prompt that works in the product, which is not something
you can say when you evaluate a compiled prompt string in isolation.

Evaluators run in this order:
    correctness  deterministic, from ClickHouse ground truth  (free, decisive)
    word_count   deterministic
    llm_judge    subjective axes only                          (costs tokens)

Usage:
    python experiments/run_experiment.py --dataset liv-concurrency-evals --run-name baseline
    python experiments/run_experiment.py --dataset liv-traps --run-name traps-baseline
    python experiments/run_experiment.py --dataset liv-concurrency-evals \
        --agent liv-concurrency --run-name specialist-direct
    python experiments/run_experiment.py --dataset liv-traps --run-name quick --no-judge
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from langfuse_client import client, call_agent
from evals.correctness import correctness_evaluator, word_budget_evaluator
from evals.llm_judge import llm_judge_evaluator

lf = client()

DETERMINISTIC = ("numeric_accuracy", "reports_moment", "rule_compliance")
SUBJECTIVE = ("groundedness", "conciseness", "actionability", "clarity")


def build_task(agent_override: str | None):
    def task(*, item, **kwargs):
        question = (item.input or {}).get("question", "")
        agent = agent_override or (item.metadata or {}).get("agent", "liv-analyst")
        try:
            return call_agent(question, agent_id=agent)
        except Exception as e:  # noqa: BLE001 — one bad item shouldn't kill the run
            return f"[agent error] {e}"
    return task


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--run-name", required=True)
    ap.add_argument("--agent", default=None,
                    help="override the agent; default is per-item metadata")
    ap.add_argument("--no-judge", action="store_true",
                    help="deterministic scores only — fast and free")
    args = ap.parse_args()

    dataset = lf.get_dataset(args.dataset)
    evaluators = [correctness_evaluator, word_budget_evaluator]
    if not args.no_judge:
        evaluators.append(llm_judge_evaluator)

    print(f"Experiment '{args.run_name}'  dataset={args.dataset} "
          f"({len(dataset.items)} items)  agent={args.agent or 'per-item'}")

    result = dataset.run_experiment(
        name=f"LIV {args.dataset}",
        run_name=args.run_name,
        description=f"live agent run on {args.dataset}",
        task=build_task(args.agent),
        evaluators=evaluators,
    )

    sums, counts = {}, {}
    for ir in result.item_results:
        for ev in (ir.evaluations or []):
            name = ev.get("name") if isinstance(ev, dict) else getattr(ev, "name", None)
            val = ev.get("value") if isinstance(ev, dict) else getattr(ev, "value", None)
            if name is None or val is None:
                continue
            sums[name] = sums.get(name, 0.0) + float(val)
            counts[name] = counts.get(name, 0) + 1

    print(f"\n-- {args.run_name}: {len(result.item_results)} items --")
    print("  deterministic (pass rate):")
    for k in DETERMINISTIC:
        if counts.get(k):
            print(f"    {k:<18} {sums[k] / counts[k] * 100:5.1f}%  ({counts[k]} items)")
    print("  judged (0-10):")
    for k in SUBJECTIVE:
        if counts.get(k):
            print(f"    {k:<18} {sums[k] / counts[k] * 10:5.2f}")
    if counts.get("word_count"):
        print(f"  avg words           {sums['word_count'] / counts['word_count']:5.0f}")

    lf.flush()
    print(f"\nDone. {getattr(result, 'dataset_run_url', None) or 'View in Langfuse UI.'}")


if __name__ == "__main__":
    main()