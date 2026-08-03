"""Group / Family Applications — one traveller creates a single application for
a group, adding/removing co-travellers before submitting together. Structurally
distinct from prior specs: events are keyed by group_id (not per-event envelope
alone), and completion needs to be sliced by group_size, so ordering-key/rollup
choices matter more than usual."""
import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from orchestrator import ingest_spec

SPEC_DIR = pathlib.Path(
    "/Users/anshmehta/Downloads/Clickhouse Hackathon/click-a-thon-2026-main/Atlys/specs/02_group_family"
)
PER_EVENT_SAMPLE = 30


def load_full_events() -> list[dict]:
    with open(SPEC_DIR / "events.ndjson") as f:
        events = [json.loads(line) for line in f]
    print(f"loaded {len(events)} full events")
    return events


def stratified_sample(events: list[dict]) -> list[dict]:
    """Small, design-time-only slice for the proposer's prompt context — NOT what
    gets perf-tested, test-harnessed, or inserted (see ingest_spec's docstring:
    that's full_events, always)."""
    by_event = defaultdict(list)
    for e in events:
        name = e.get("event")
        if len(by_event[name]) < PER_EVENT_SAMPLE:
            by_event[name].append(e)
    sample = [e for group in by_event.values() for e in group]
    print(f"sampled {len(sample)} events across {len(by_event)} event types for proposer context: "
          f"{ {k: len(v) for k, v in by_event.items()} }")
    return sample


def main():
    spec_markdown = (SPEC_DIR / "spec.md").read_text()
    full_events = load_full_events()
    sample_events = stratified_sample(full_events)

    result = ingest_spec(
        spec_name="group_family",
        spec_markdown=spec_markdown,
        sample_events=sample_events,
        full_events=full_events,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
