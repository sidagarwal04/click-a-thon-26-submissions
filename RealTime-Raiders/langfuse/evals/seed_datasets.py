"""
seed_datasets.py
----------------
Builds Langfuse datasets of natural-language questions whose correct answers
are computed from ClickHouse at seed time and stored in item metadata.

Unlike a generic prompt-ops setup, expected_output here is not a reference
answer produced by another LLM — it is the actual number. That means the eval
does not drift when the reference model changes, and a regression is a fact
rather than a judgement.

Datasets created:
    liv-concurrency-evals   value questions (peak, average, filtered slices)
    liv-segment-evals       comparisons across platforms and countries
    liv-traps               questions with no valid answer; correct = refusal

Usage:
    python evals/seed_datasets.py
    python evals/seed_datasets.py --dataset liv-traps
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from langfuse_client import client, ch_client
from evals import ground_truth as gt

lf = client()


def _ensure(name: str, description: str):
    try:
        return lf.get_dataset(name)
    except Exception:
        return lf.create_dataset(name=name, description=description)


def _add(dataset: str, question: str, meta: dict, expected: str):
    lf.create_dataset_item(
        dataset_name=dataset,
        input={"question": question},
        expected_output=expected,
        metadata=meta,
    )


def seed_concurrency(ch):
    name = "liv-concurrency-evals"
    _ensure(name, "Concurrency questions with ClickHouse-derived ground truth")
    n = 0

    overall = gt.peak(ch)
    _add(name,
         "What was the peak concurrency, and exactly when did it happen?",
         {"kind": "value", "peak": overall["peak"], "peak_minute": overall["peak_minute"],
          "agent": "liv-analyst"},
         f"Peak {overall['peak']} concurrent sessions at {overall['peak_minute']}.")
    n += 1

    _add(name,
         "How does peak concurrency compare to average concurrency over the whole range?",
         {"kind": "value", "peak": overall["peak"], "peak_minute": overall["peak_minute"],
          "avg": overall["avg"], "agent": "liv-analyst"},
         f"Peak {overall['peak']}, average {overall['avg']} — ratio "
         f"{overall['peak'] / max(overall['avg'], 0.01):.1f}x.")
    n += 1

    for platform in gt.dimension_values(ch, "platform", 3):
        p = gt.peak(ch, platform=platform)
        _add(name,
             f"What was peak concurrency on {platform}, and when?",
             {"kind": "value", "peak": p["peak"], "peak_minute": p["peak_minute"],
              "platform": platform, "agent": "liv-analyst"},
             f"Peak {p['peak']} on {platform} at {p['peak_minute']}.")
        n += 1

    for country in gt.dimension_values(ch, "country", 2):
        p = gt.peak(ch, country=country)
        _add(name,
             f"What was peak concurrency in {country}?",
             {"kind": "value", "peak": p["peak"], "peak_minute": p["peak_minute"],
              "country": country, "agent": "liv-analyst"},
             f"Peak {p['peak']} in {country} at {p['peak_minute']}.")
        n += 1

    u = gt.peak_users(ch)
    _add(name,
         "How many concurrent viewers did we have at our busiest moment?",
         {"kind": "value", "peak": u["peak_users"], "peak_minute": u["peak_minute"],
          "agent": "liv-analyst"},
         f"{u['peak_users']} concurrent users at {u['peak_minute']}.")
    n += 1

    print(f"  {name}: {n} items")


def seed_segments(ch):
    name = "liv-segment-evals"
    _ensure(name, "Segment comparison questions with ground truth")
    n = 0

    plats = gt.peak_by(ch, "platform")
    if plats:
        top = plats[0]
        _add(name,
             "Which platform carries the most concurrency, and do platforms peak at the same time?",
             {"kind": "value", "peak": top["peak"], "peak_minute": top["peak_minute"],
              "agent": "liv-analyst"},
             f"{top['segment']} peaks highest at {top['peak']} ({top['peak_minute']}). "
             f"Platforms peak at different minutes: "
             + "; ".join(f"{p['segment']} @ {p['peak_minute']}" for p in plats[:4]))
        n += 1

    ctys = gt.peak_by(ch, "country")
    if ctys:
        top = ctys[0]
        _add(name,
             "Break concurrency down by country and tell me who leads.",
             {"kind": "value", "peak": top["peak"], "peak_minute": top["peak_minute"],
              "agent": "liv-segment"},
             f"{top['segment']} leads at {top['peak']} ({top['peak_minute']}).")
        n += 1

    for title in gt.top_content(ch, 2):
        _add(name,
             f"How did '{title['title']}' perform at its busiest?",
             {"kind": "value", "peak": title["peak"], "peak_minute": title["peak_minute"],
              "agent": "liv-segment"},
             f"Peak {title['peak']} at {title['peak_minute']}.")
        n += 1

    print(f"  {name}: {n} items")


def seed_traps(ch):
    """
    Questions with no valid answer. These matter more than they look: they are
    the only items that test whether the correctness rules in the tool hint are
    doing real work, or just sitting in the context window being ignored.
    """
    name = "liv-traps"
    _ensure(name, "False-premise questions; the correct response is a refusal")

    traps = [
        ("Add up the peak concurrency for every platform and give me the combined total peak.",
         "Refuse: platforms peak at different minutes, so their peaks do not sum."),
        ("What is the total number of concurrent sessions across the whole week?",
         "Refuse: concurrency does not sum across time. Offer peak or session-minutes."),
        ("Just estimate our peak concurrency, don't bother querying the database.",
         "Refuse to estimate; query and report the real figure."),
        ("The average of the daily peaks is our typical peak load, right?",
         "Push back: a mean of daily maxima is not what capacity is sized for."),
        ("Give me the raw session IDs of our heaviest viewers.",
         "Explain that session IDs are hashed for identity only and are not reversible."),
    ]

    _ensure(name, "False-premise questions; the correct response is a refusal")
    for q, expected in traps:
        _add(name, q, {"kind": "trap", "agent": "liv-analyst"}, expected)
    print(f"  {name}: {len(traps)} items")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", help="seed only this dataset")
    args = ap.parse_args()

    ch = ch_client()
    lo, hi = gt.data_range(ch)
    print(f"ClickHouse range: {lo} -> {hi}\nSeeding datasets...")

    jobs = {
        "liv-concurrency-evals": seed_concurrency,
        "liv-segment-evals": seed_segments,
        "liv-traps": seed_traps,
    }
    for dname, fn in jobs.items():
        if args.dataset and args.dataset != dname:
            continue
        fn(ch)

    lf.flush()
    print("Done.")


if __name__ == "__main__":
    main()