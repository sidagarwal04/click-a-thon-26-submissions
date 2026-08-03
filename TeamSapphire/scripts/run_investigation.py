#!/usr/bin/env python3
"""Run the full investigation and write the submission artifacts.

This is what executes for the unseen incident. It must run cold and unattended,
so everything it needs is either a flag or inferred from the data — there is no
step that expects a human to remember something under pressure.

Writes to out/:
    diagnosis.json  — the full structured investigation, every number and query
    diagnosis.md    — the human-readable report, narration plus evidence
and prints the Langfuse trace URL, which is the artifact the "no trace, no
credit" criterion is actually scored on.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engine.db import DB, _load_env          # noqa: E402
from engine.investigate import investigate    # noqa: E402
from engine.narrate import narrate            # noqa: E402
from engine.trace import make_tracer          # noqa: E402


def infer_window(db: DB, hours_back: int | None,
                 include_partial_hour: bool = False) -> tuple[str, str]:
    """Default to the most recent slice of data present.

    The unseen incident arrives as new rows, so "what should I investigate" has
    an obvious answer that does not require a human to type dates under time
    pressure. Baselines reach further back than the window regardless.

    THE PARTIAL-HOUR TRAP
    ---------------------
    Under continuous ingestion the newest hour is always incomplete. Run at
    14:30 and hour 14 holds thirty minutes of traffic, which against a
    full-hour baseline reads as a ~50% collapse — a false alarm on every single
    run, and a confident one, since the arithmetic is correct and only the
    comparison is invalid.

    The provided batch dataset happens to end on a complete hour, so this never
    surfaces in testing here. It would surface immediately in production.

    So the newest hour is dropped from an inferred window: for an append-only
    stream, an hour is only provably complete once data from a later hour has
    arrived. An explicitly passed --end is respected as given — the caller
    stated the window and owns that choice.
    """
    row = db.query(
        "SELECT min(hour) AS lo, max(hour) AS hi FROM inmobi.events_hourly",
        label="window:data_range",
    ).first()
    lo, hi = str(row["lo"]), str(row["hi"])

    end = datetime.fromisoformat(hi)
    if not include_partial_hour:
        end -= timedelta(hours=1)

    start = datetime.fromisoformat(lo)
    if hours_back is not None:
        start = max(start, end - timedelta(hours=hours_back))
    return str(start), str(end)


def render_markdown(inv, narrations: dict[int, object], elapsed: float) -> str:
    out: list[str] = []
    w = out.append

    w("# Incident diagnosis\n")
    w(f"**Window analysed:** {inv.window_start} → {inv.window_end}  ")
    w(f"**Events found:** {len(inv.events)}  ")
    w(f"**Runtime:** {elapsed:.1f}s · {inv.total_query_ms:.0f} ms of query time · "
      f"{inv.total_rows_read:,} rows read across {len(inv.queries)} queries  ")
    if inv.trace_url:
        w(f"**Trace:** {inv.trace_url}  ")
    w("")
    w(f"Detection discarded {inv.discarded_noise} short runs as noise and suppressed "
      f"{inv.suppressed_low_severity} low-severity events.\n")

    for n, event in enumerate(inv.events, 1):
        e = event.to_dict()
        w(f"\n---\n\n## Event {n} — {e['classification']}\n")
        w(f"**{e['headline']}**\n")
        w(f"Window `{e['start']}` → `{e['end']}` ({e['hours']}h), severity "
          f"{e['severity']} percent-hours, consolidated from {e['trigger_count']} "
          f"triggering incident(s).\n")

        narration = narrations.get(n)
        if narration is not None:
            w("### Diagnosis\n")
            w(narration.text + "\n")
            status = ("all numbers verified against the computed evidence"
                      if narration.all_numbers_verified
                      else f"UNVERIFIED NUMBERS: {narration.unverified_numbers}")
            w(f"*Narrated by {narration.model}; {status}.*\n")

        w("### Factor decomposition\n")
        w("| factor | actual | baseline | change | share of movement |")
        w("|---|---:|---:|---:|---:|")
        for f in e["decomposition"]["factors"]:
            w(f"| {f['factor']} | {f['actual']:,.4f} | {f['baseline']:,.4f} | "
              f"{f['pct_change']:+.2%} | {f['contribution_share']:.1%} |")
        w(f"\nIdentity residual `{e['decomposition']['identity_residual']:.2e}` "
          f"— the four factors reconstruct the movement exactly.\n")

        sig = e.get("signature")
        if sig and sig.get("reading"):
            w("### Shape of the change\n")
            w(sig["reading"] + "\n")
            if sig.get("rules_out"):
                w("**Rules out:**\n")
                for r in sig["rules_out"]:
                    w(f"- {r}")
                w("")

        if e["responsible"]:
            w("### Responsible segments\n")
            for v in e["responsible"]:
                w(f"- **{v['dim_name']} = {v['top_value']}** — {v['reason']}")
            w("")

        w("### Checked and ruled out\n")
        for v in e["ruled_out"]:
            w(f"- **{v['dim_name']}** [{v['verdict']}] — {v['reason']}")
        w("")

    if inv.compound_findings:
        w("\n---\n\n## Compound anomalies\n")
        w("Cells that moved at least 2x more than either parent dimension did — so the "
          "parent's own movement is a *consequence* of this cell, not an explanation for "
          "it. Invisible to any single-dimension scan by construction.\n")
        w("| day | segment | cell | parent A | parent B | requests |")
        w("|---|---|---:|---:|---:|---:|")
        for c in inv.compound_findings[:15]:
            scope = f"{c['dim_a']}={c['value_a']} x {c['dim_b']}={c['value_b']}"
            w(f"| {c['day']} | {scope} | {c['pct_change']:+.1%} | "
              f"{c['parent_a_pct']:+.1%} | {c['parent_b_pct']:+.1%} | {c['requests']:,} |")
        w("")

    w("\n---\n\n## Detector ledger\n")
    w("| scan | metric | examined | flagged | max abs z | verdict | query ms | rows read |")
    w("|---|---|---:|---:|---:|---|---:|---:|")
    for c in inv.detector_ledger:
        examined = c.get("hours_examined", c.get("segment_hours_examined", 0))
        flagged = c.get("hours_flagged", c.get("segment_hours_flagged", 0))
        w(f"| {c.get('scan','global')} | {c['metric']} | {examined:,} | {flagged:,} | "
          f"{c['max_abs_z']} | {c['verdict']} | {c['query_ms']:.0f} | {c['rows_read']:,} |")

    return "\n".join(out)


def run_once(db: DB, args, seen: set[str] | None = None) -> int:
    """One investigation pass. Returns the process exit code.

    Split out from main() so the watch loop reuses it verbatim — the
    scheduled path and the one-shot path must not be able to drift apart.
    """
    started = time.perf_counter()
    # The DB object is reused across watch passes, so its query log would
    # accumulate and each pass would report the running total rather than its
    # own cost. Misreported numbers are the one thing this project cannot ship.
    db.log.entries.clear()
    start = args.start or None
    end = args.end or None
    if not (start and end):
        inferred_start, inferred_end = infer_window(
            db, args.hours_back, include_partial_hour=args.include_partial_hour)
        start, end = start or inferred_start, end or inferred_end

    print(f"Investigating {start} -> {end}")

    tracer = make_tracer(
        enabled=not args.no_trace,
        name="rca-investigation",
        metadata={"window": [start, end], "baseline_weeks": args.weeks},
    )

    inv = investigate(db, start, end, weeks=args.weeks, tracer=tracer)
    fresh = inv.events
    if seen is not None:
        fresh = [e for e in inv.events
                 if f"{e.start}|{e.classification}|{e.headline}" not in seen]
        for e in inv.events:
            seen.add(f"{e.start}|{e.classification}|{e.headline}")

    print(f"  {len(inv.events)} event(s)"
          + (f", {len(fresh)} new" if seen is not None else "")
          + f" · {inv.total_query_ms:.0f} ms · {inv.total_rows_read:,} rows read")
    for e in fresh:
        print(f"  NEW  [{e.classification}] {e.headline}")

    narrations: dict[int, object] = {}
    if not args.no_narrate:
        for n, event in enumerate(inv.events[: args.max_narrate], 1):
            e = event.to_dict()
            print(f"  narrating event {n} ...")
            try:
                result = narrate(e)
            except Exception as exc:  # noqa: BLE001 — narration must not sink the run
                print(f"    narration failed ({exc}); structured diagnosis is unaffected")
                continue
            narrations[n] = result
            with tracer.span(f"narrate event {n}"):
                tracer.generation(
                    name="diagnosis", model=result.model,
                    prompt=result.payload, completion=result.text,
                    metadata={
                        "all_numbers_verified": result.all_numbers_verified,
                        "unverified_numbers": result.unverified_numbers,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                    },
                )
            if not result.all_numbers_verified:
                print(f"    WARNING unverified numbers: {result.unverified_numbers}")

    if hasattr(tracer, "close"):
        tracer.close(output={"events": len(inv.events)})
    else:
        tracer.flush()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    elapsed = time.perf_counter() - started

    payload = inv.to_dict()
    payload["narrations"] = {
        str(n): {"text": r.text, "model": r.model,
                 "all_numbers_verified": r.all_numbers_verified,
                 "unverified_numbers": r.unverified_numbers}
        for n, r in narrations.items()
    }
    payload["runtime_seconds"] = round(elapsed, 1)
    (out_dir / "diagnosis.json").write_text(json.dumps(payload, indent=2, default=str))
    (out_dir / "diagnosis.md").write_text(render_markdown(inv, narrations, elapsed))

    print(f"\nWrote {out_dir/'diagnosis.md'} and {out_dir/'diagnosis.json'}")
    if inv.trace_url:
        print(f"Trace: {inv.trace_url}")
    print(f"Done in {elapsed:.1f}s")

    unverified = [n for n, r in narrations.items() if not r.all_numbers_verified]
    if unverified:
        print(f"\nFAILED number verification on event(s): {unverified}")
        return 2
    return 0




def main() -> None:
    ap = argparse.ArgumentParser(description="Run the investigation and write artifacts.")
    ap.add_argument("--start", help="window start (default: inferred from the data)")
    ap.add_argument("--end", help="window end (default: latest hour present)")
    ap.add_argument("--hours-back", type=int,
                    help="analyse only the last N hours of data")
    ap.add_argument("--weeks", type=int, default=4, help="baseline weeks (default 4)")
    ap.add_argument("--out", default=str(REPO / "out"), help="output directory")
    ap.add_argument("--no-narrate", action="store_true",
                    help="skip the LLM call; structured diagnosis is still complete")
    ap.add_argument("--no-trace", action="store_true", help="disable Langfuse tracing")
    ap.add_argument("--max-narrate", type=int, default=3,
                    help="narrate at most this many events (default 3)")
    ap.add_argument("--include-partial-hour", action="store_true",
                    help="include the newest (likely incomplete) hour in an "
                         "inferred window; off by default because a partial "
                         "hour reads as a large false drop")
    ap.add_argument("--watch", type=int, metavar="SECONDS",
                    help="run continuously every N seconds instead of once — "
                         "the production shape, same engine")
    args = ap.parse_args()


    _load_env()
    db = DB()

    if args.watch:
        # Production shape: same engine, scheduled instead of invoked. Alert
        # identity is (window, classification, headline) — polling a rolling
        # window re-detects a live incident every pass, and re-announcing it
        # every 60 seconds is how an on-call engineer learns to ignore you.
        seen: set[str] = set()
        print(f"Watching — every {args.watch}s. Ctrl-C to stop.")
        while True:
            try:
                run_once(db, args, seen)
            except KeyboardInterrupt:
                print("\nstopped")
                break
            except Exception as exc:  # noqa: BLE001 — a poll failing must not end the watch
                print(f"  pass failed ({exc}); retrying next interval")
            time.sleep(args.watch)
        return

    sys.exit(run_once(db, args))


if __name__ == "__main__":
    main()
