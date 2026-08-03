"""
auto_improve.py
---------------
Compares two experiment runs and, when the challenger wins, rewrites the AGENT
prompt and publishes it as the new production version.

The loop closes properly here. lc-agent fetches its prompts from Langfuse by
the production label, and caches the graph keyed on prompt version — so
publishing from this script changes live agent behaviour within the cache TTL.
No rebuild, no restart, no redeploy.

    seed (ground truth from ClickHouse)
              |
      run_experiment  baseline   ---+
      run_experiment  challenger ---+
                                     v
              auto_improve: read both runs' scores
                 correctness regressed?  -> never publish, exit
                 challenger wins?        -> rewrite -> publish production
                 otherwise               -> print suggestion, publish nothing
                                     |
                              lc-agent picks it up

Usage:
    python experiments/auto_improve.py --prompt liv-concurrency-agent \
        --dataset liv-concurrency-evals --baseline baseline --challenger v2

    python experiments/auto_improve.py ... --dry-run
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from langfuse_client import client, call_improver

lf = client()

THRESHOLD = 0.3          # challenger must beat baseline by this on the 0-10 blend
DETERMINISTIC = ("numeric_accuracy", "reports_moment", "rule_compliance")
SUBJECTIVE = ("groundedness", "conciseness", "actionability", "clarity")
ALL_AXES = DETERMINISTIC + SUBJECTIVE


def run_scores(dataset_name: str, run_name: str) -> dict[str, list[float]]:
    run = lf.get_dataset_run(dataset_name=dataset_name, run_name=run_name)
    out: dict[str, list[float]] = {a: [] for a in ALL_AXES}
    for ri in run.dataset_run_items:
        if not ri.trace_id:
            continue
        trace = lf.api.trace.get(ri.trace_id)
        for s in (trace.scores or []):
            if s.name in out and s.value is not None:
                out[s.name].append(float(s.value))
    return out


def averages(scores: dict[str, list[float]]) -> dict[str, float]:
    return {a: (sum(v) / len(v) if v else 0.0) for a, v in scores.items()}


def blended(avgs: dict[str, float]) -> float:
    """
    Correctness is weighted double. A prompt that reads beautifully and reports
    the wrong peak is worse than a blunt one that is right, and the score has
    to say so or the loop will happily optimise toward fluent errors.
    """
    det = [avgs[a] for a in DETERMINISTIC if avgs.get(a)]
    sub = [avgs[a] for a in SUBJECTIVE if avgs.get(a)]
    det_avg = sum(det) / len(det) if det else 0.0
    sub_avg = sum(sub) / len(sub) if sub else 0.0
    if not det:
        return sub_avg * 10
    if not sub:
        return det_avg * 10
    return ((det_avg * 2) + sub_avg) / 3 * 10


def correctness_avg(avgs: dict[str, float]) -> float:
    vals = [avgs[a] for a in DETERMINISTIC if avgs.get(a)]
    return sum(vals) / len(vals) if vals else 0.0


def worst_samples(dataset_name: str, run_name: str, limit: int = 3) -> str:
    run = lf.get_dataset_run(dataset_name=dataset_name, run_name=run_name)
    scored = []
    for ri in run.dataset_run_items:
        if not ri.trace_id:
            continue
        trace = lf.api.trace.get(ri.trace_id)
        vals = [float(s.value) for s in (trace.scores or []) if s.name in ALL_AXES]
        if not vals:
            continue
        comments = "; ".join(s.comment for s in (trace.scores or []) if s.comment)[:300]
        scored.append((sum(vals) / len(vals), str(trace.input)[:200],
                       str(trace.output)[:400], comments))
    scored.sort(key=lambda x: x[0])
    return "\n\n---\n\n".join(
        f"Question: {q}\nAnswer: {o}\nScore: {a:.2f}\nEvaluator notes: {c}"
        for a, q, o, c in scored[:limit]
    ) or "No scored samples."


IMPROVE_SYSTEM = """\
You are a prompt engineer for a streaming-analytics agent that queries
ClickHouse before answering. Rewrite the agent's system prompt to fix the
weaknesses shown in the low-scoring samples.

Hard rules:
  - Keep every {{variable}} placeholder exactly as-is.
  - The agent MUST always state the minute a peak occurred, not just the value.
  - The agent MUST refuse false premises: peaks do not sum across dimensions,
    concurrency does not sum across time.
  - The agent MUST query before answering; never estimate.
  - No markdown headers or bullet symbols in the prompt.
  - Do NOT add schema or SQL rules — those are injected separately from code
    and duplicating them here creates two sources of truth that will drift.

Return ONLY the improved prompt text.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="agent prompt, e.g. liv-concurrency-agent")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--challenger", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = averages(run_scores(args.dataset, args.baseline))
    chal = averages(run_scores(args.dataset, args.challenger))
    base_blend, chal_blend = blended(base), blended(chal)
    delta = chal_blend - base_blend

    def show(label, avgs, blend):
        det = "  ".join(f"{a}={avgs[a]*100:.0f}%" for a in DETERMINISTIC if avgs.get(a))
        sub = "  ".join(f"{a}={avgs[a]*10:.1f}" for a in SUBJECTIVE if avgs.get(a))
        print(f"{label:<11} blended={blend:.2f}/10\n            {det}\n            {sub}")

    show("baseline", base, base_blend)
    show("challenger", chal, chal_blend)
    print(f"delta       {delta:+.2f}\n")

    # Correctness is a gate, not a term to be traded off.
    base_correct, chal_correct = correctness_avg(base), correctness_avg(chal)
    if chal_correct < base_correct - 0.001:
        print(f"BLOCKED: correctness regressed "
              f"({base_correct*100:.0f}% -> {chal_correct*100:.0f}%). Nothing published.")
        print("A nicer-reading answer that gets the number wrong is not an improvement.")
        return

    best_run = args.challenger if chal_blend >= base_blend else args.baseline
    best = chal if best_run == args.challenger else base
    weak = [a for a in ALL_AXES if best.get(a) and best[a] < 0.8]

    current = lf.get_prompt(args.prompt, label="production")
    improved = call_improver(
        f"CURRENT PROMPT:\n{current.prompt}\n\n"
        f"WEAK AXES (below 80%): {', '.join(weak) or 'none'}\n\n"
        f"LOW-SCORING SAMPLES:\n{worst_samples(args.dataset, best_run)}",
        system=IMPROVE_SYSTEM,
    ).strip()

    print(f"Improved prompt ({len(improved)} chars):\n{improved[:600]}...\n")

    if delta >= THRESHOLD and not args.dry_run:
        created = lf.create_prompt(
            name=args.prompt, prompt=improved, labels=["production"], type="text",
            config=current.config or {},
            commit_message=(f"auto-improve: {args.challenger} beat {args.baseline} "
                            f"by {delta:.2f} (correctness {chal_correct*100:.0f}%)"),
        )
        print(f"Published v{created.version} -> production. "
              f"lc-agent picks it up within the prompt cache TTL.")
    elif delta < THRESHOLD:
        print(f"Challenger did not beat baseline by >= {THRESHOLD}. Nothing published.")
        print("Paste the text above into Langfuse as a new version, run a fresh "
              "experiment against it, then re-compare.")
    else:
        print("[dry-run] Would publish — skipped.")

    lf.flush()


if __name__ == "__main__":
    main()