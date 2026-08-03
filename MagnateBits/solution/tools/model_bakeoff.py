"""Score models x retrieval modes on the SAME questions, deterministically.

    python -m tools.model_bakeoff --spec 06_unseen
    python -m tools.model_bakeoff --spec 06_unseen --models cli:claude-sonnet-5,openai:gpt-oss:20b

Why the analytics path and not the full pipeline: a full run is ~200s and three LLM
calls, so a 4x2 matrix is half an hour and most of it re-derives a schema that is not
what is being compared. `ask.Session` exercises the call that actually matters here --
plan + interpret over real aggregates -- in ~40s, against identical data and identical
questions, so the only things varying are the model and the retrieval mode.

Scored WITHOUT an LLM judge. Everything below is checkable arithmetic:

  schema_ok     did the model emit an object satisfying the contract at all (this is
                where small models fail first, and a failure here is total -- the
                pipeline gets nothing, not a worse answer)
  grounded      of the numbers the answer asserts, how many appear in the query results
                it cites -- `grounding.py`, the same guard the pipeline runs
  ungrounded    the count that did not, i.e. figures a PM would have acted on
  refused_ok    when a question names a metric with an open definition_conflict, did it
                refuse/qualify rather than inventing one number
  prompt_chars  size of the context block actually sent -- this is what RAG on/off moves
  latency/tokens

An "n/a" is reported wherever a cell could not run; a model that 403s or times out is
recorded as such rather than dropped, because a model you cannot reach is a real result.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

SPECS_DIR = HERE.parent / "specs"
OUT_DIR = HERE / "out" / "eval"

#: backend:model. Only these two Ollama Cloud models are reachable on the current key --
#: glm-5.2 / deepseek-v4-flash / kimi-k2.6 all return 403 (a plan/tier restriction, not a
#: bad key: the same key serves gpt-oss:*). Measured, not assumed.
DEFAULT_MODELS = [
    "cli:claude-sonnet-5",
    "openai:gpt-oss:120b",
    "openai:gpt-oss:20b",
    "mock:mock",
]

#: Fixed question set. Deliberately mixes shapes: a plain aggregate, a comparison, and
#: one that names a DISPUTED metric so refusal behaviour is exercised on every model.
QUESTIONS = [
    "What is the coupon apply rate from coupon_field_shown to coupon_applied?",
    "Which device_type has the worst checkout_with_coupon rate?",
    "What is our conversion rate?",
]


def _set_mode(rag: bool) -> None:
    os.environ["ATLYS_CONTEXT_RETRIEVAL"] = "vector" if rag else "full"


def _set_model(spec: str) -> tuple[str, str]:
    """'backend:model' -> configure llm and return (backend, model)."""
    backend, _, model = spec.partition(":")
    import llm

    llm.BACKEND = backend
    llm.DEFAULT_MODEL = model or llm.DEFAULT_MODEL
    return backend, (model or llm.DEFAULT_MODEL)


def run_cell(spec_dir: Path, model_spec: str, rag: bool) -> dict[str, Any]:
    import grounding
    import llm
    import metric_policy
    from ask import Session
    from ch import CH

    backend, model = _set_model(model_spec)
    _set_mode(rag)
    row: dict[str, Any] = {
        "model": f"{backend}:{model}", "rag": "on" if rag else "off",
        "asked": 0, "schema_ok": 0, "numbers": 0, "grounded": 0, "ungrounded": 0,
        "refused_ok": "n/a", "prompt_chars": 0, "latency_s": 0.0,
        "out_tokens": 0, "notes": "",
    }

    before = llm.usage()
    t0 = time.time()
    try:
        ch = CH()
        sess = Session(spec_dir, ch)
        sess.warm()  # template suite runs once, shared by every question
    except Exception as exc:  # noqa: BLE001
        row["notes"] = f"setup failed: {type(exc).__name__}: {str(exc)[:90]}"
        return row

    # What the retrieval mode actually costs/saves, measured once per cell.
    try:
        import vector_rag

        block = (
            vector_rag.ranked_prompt(ch, sess.ctx, QUESTIONS[0])
            if vector_rag.enabled() else sess.ctx.as_prompt()
        )
        row["prompt_chars"] = len(block)
    except Exception:  # noqa: BLE001
        row["prompt_chars"] = len(sess.ctx.as_prompt())

    conflicts = metric_policy.load_open_conflicts(ch, sess.ctx)
    refusals_expected = refusals_ok = 0

    for q in QUESTIONS:
        row["asked"] += 1
        try:
            ans, ungrounded = sess.answer(q)
        except Exception as exc:  # noqa: BLE001
            row["notes"] = (row["notes"] + f" | {type(exc).__name__}: {str(exc)[:70]}").strip(" |")
            continue
        row["schema_ok"] += 1
        nums = list(ans.numbers_cited or [])
        row["numbers"] += len(nums)
        row["ungrounded"] += len(ungrounded)
        row["grounded"] += len(nums) - len(ungrounded)

        if metric_policy.mentions_subject(q, "conversion") and conflicts:
            refusals_expected += 1
            # Correct behaviour is EITHER a policy refusal OR an answer that qualifies
            # by naming both definitions -- not a single invented headline number.
            txt = ans.answer or ""
            if metric_policy.is_qualified(txt, conflicts[0]) or "Refused" in txt:
                refusals_ok += 1

    row["latency_s"] = round(time.time() - t0, 1)
    after = llm.usage()
    row["out_tokens"] = after["output_tokens"] - before["output_tokens"]
    if refusals_expected:
        row["refused_ok"] = f"{refusals_ok}/{refusals_expected}"
    row["groundedness"] = (
        f"{row['grounded']}/{row['numbers']}" if row["numbers"] else "no numbers cited"
    )
    return row


#: `numbers` (figures cited) comes BEFORE the groundedness ratio on purpose.
#: Groundedness is a PRECISION measure and precision alone rewards saying less: a model
#: that cites one figure and gets it right scores 1/1, identical to one that cites seven
#: and gets all seven right. Measured on the first run of this harness: gpt-oss cited 1
#: figure per question set and scored "100%", the same as Sonnet's 5-7 -- and the
#: deterministic `mock` stub, which emits placeholder prose, also scored "100%". A
#: comparison where the stub ties the frontier model is not measuring answer quality.
#: Read the two columns together: substance first, then whether it held up.
COLS = [
    ("model", "Model"), ("rag", "RAG"), ("schema_ok", "Schema-valid"),
    ("numbers", "Figures cited"), ("groundedness", "…of which grounded"),
    ("ungrounded", "Ungrounded"), ("refused_ok", "DISPUTED handled"),
    ("prompt_chars", "Context chars"), ("out_tokens", "Output tokens"),
    ("latency_s", "Latency (s)"), ("notes", "Notes"),
]


def _md(rows: list[dict[str, Any]]) -> str:
    head = "| " + " | ".join(h for _, h in COLS) + " |"
    sep = "| " + " | ".join("---" for _ in COLS) + " |"
    out = [head, sep]
    for r in rows:
        out.append(
            "| " + " | ".join(str(r.get(k, "")).replace("|", "\\|") for k, _ in COLS) + " |"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", default="06_unseen", help="spec directory name under ../specs")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--rag", default="on,off", help="comma list: on,off")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)

    spec_dir = SPECS_DIR / args.spec
    if not (spec_dir / "spec.md").exists():
        print(f"no spec at {spec_dir}", file=sys.stderr)
        return 1

    models = [m for m in args.models.split(",") if m.strip()]
    modes = [m.strip() == "on" for m in args.rag.split(",") if m.strip()]

    rows: list[dict[str, Any]] = []
    for m in models:
        for rag in modes:
            print(f"[bakeoff] {m:26s} rag={'on ' if rag else 'off'} ...", flush=True)
            try:
                rows.append(run_cell(spec_dir, m, rag))
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                rows.append({"model": m, "rag": "on" if rag else "off",
                             "notes": f"HARNESS ERROR: {exc}"})

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "model_bakeoff.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    md = [
        "# Model x retrieval-mode bake-off",
        "",
        f"Spec `{args.spec}`, {len(QUESTIONS)} fixed questions, identical data. "
        "Scored deterministically -- no LLM judge. `grounding.py` decides whether an "
        "asserted number appears in the query results the answer cites.",
        "",
        "**Read `Figures cited` and `…of which grounded` together.** Groundedness on "
        "its own is a *precision* measure, and precision rewards saying less: a model "
        "citing one correct figure scores the same 100% as one citing seven. On the "
        "first run of this harness the deterministic `mock` stub -- placeholder prose "
        "by construction -- scored \"100% grounded\", identical to Sonnet. Volume is "
        "what separates them.",
        "",
        _md(rows),
        "",
        "Questions asked:",
        "",
    ] + [f"{i+1}. {q}" for i, q in enumerate(QUESTIONS)]
    (args.out / "model_bakeoff.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out / 'model_bakeoff.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
