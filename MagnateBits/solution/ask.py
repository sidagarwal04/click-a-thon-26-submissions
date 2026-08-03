"""Ask a feature's PM questions and get answers grounded in ClickHouse.

    python ask.py                                  # interactive, pick a spec
    python ask.py --spec ../specs/<feature-dir>
    python ask.py --spec ../specs/<feature-dir> --question "where do users drop off?"

Why this is fast where run_pipeline.py is slow: the table already exists, so there is no
schema-design call. Semantics are derived deterministically (~0.1s), the template suite is
executed ONCE per feature and cached for the session, and each question costs a single LLM
call that interprets already-computed aggregates. Raw rows never reach the model.

Every number in an answer is checked against the query results it cites (grounding.py).
An answer that cites a number its own queries did not return is shown as UNVERIFIED.
"""

from __future__ import annotations

import argparse
import glob
import re
from pathlib import Path

from pydantic import BaseModel, Field
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

import agents.analytics as analytics
import agents.context_agent as context_agent
import grounding
import llm
import metric_policy
import profile as profile_mod
import queries.templates as templates
import tracing
from ch import CH
from contracts import FeatureSemantics, QueryRun, SpecProfile

con = Console()
SPECS_DIR = Path(__file__).parent.parent / "specs"


class Answer(BaseModel):
    answer: str = Field(description="Direct answer for a product manager. Lead with the number.")
    numbers_cited: list[float] = Field(default_factory=list,
        description="Every figure asserted in `answer`, as plain numbers, so they can be verified.")
    supporting_queries: list[str] = Field(default_factory=list,
        description="Names of the provided result tables this answer relies on.")
    caveats: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


SYSTEM = """You answer product-analytics questions for a PM at Atlys, a digital visa platform.

You are given: the question, the feature's event schema, and RESULT TABLES already computed
in ClickHouse. Answer ONLY from those tables.

Rules:
- Lead with the number that answers the question. Be concrete and brief.
- Every figure you state must come from a result table. Never estimate, interpolate, or
  infer a number that is not shown. If the tables cannot answer the question, say so
  plainly and name what query would be needed.
- Put every figure you assert into `numbers_cited`, and name the tables you used in
  `supporting_queries`.
- Watch the scope of each table: a data-quality profile scans every row of the table,
  while a distribution query is scoped to the events that actually carry the measure.
  Do not read a whole-column statistic as if it were a per-segment one.
- Where a documented known issue plausibly explains the number, say so. Otherwise write
  "hypothesis, unverified" rather than inventing a mechanism.
"""


class Session:
    """One analysis subject: semantics + a cached set of executed query frames.

    Normally that subject is a feature spec, and the semantics are profiled from its
    raw events. `semantics=` lets a caller supply them directly instead, for a subject
    that has no spec.md/events.ndjson to profile -- the pre-existing production tables
    being the case that motivated it (see `probe.py`). Everything below this point
    already worked off `self.semantics`, so nothing downstream needed changing.
    """

    def __init__(
        self,
        spec_dir: Path | None = None,
        ch: CH | None = None,
        *,
        semantics: FeatureSemantics | None = None,
        slug: str = "",
        questions: list[str] | None = None,
    ) -> None:
        if ch is None:
            raise ValueError("ch is required")
        if semantics is None and spec_dir is None:
            raise ValueError("pass either spec_dir (to profile) or semantics (pre-built)")
        self.ch = ch
        self.profile: SpecProfile | None = None
        self._slug = slug
        if semantics is not None:
            self.spec_md = self.events = None
            self.semantics = semantics
            self.questions = list(questions or [])
            self._slug = slug or semantics.feature_slug
        else:
            self.spec_md = spec_dir / "spec.md"
            self.events = spec_dir / "events.ndjson"
            self.profile = profile_mod.profile_spec(self.spec_md, self.events)
            self.semantics = profile_mod.derive_semantics(self.profile, ch=ch)
            self.questions = profile_mod.extract_questions(self.profile.spec_markdown)
            self._slug = slug or self.profile.feature_slug
        self.runs: list[QueryRun] | None = None
        self.scanned = 0
        self.ctx = context_agent.snapshot(ch=ch, run_id="ask", note="ask.py")

    @property
    def slug(self) -> str:
        return self._slug

    def warm(self) -> list[QueryRun]:
        """Execute the template suite once; reuse for every question this session."""
        if self.runs is None:
            with con.status(f"[cyan]computing aggregates for {self.slug}…"):
                plan = templates.build_all(self.semantics, max_segment_dims=6)
                self.runs = [r for r in analytics.execute(plan, self.ch) if not r.error]
                # rows_scanned is what ClickHouse actually read; r.rows is only what
                # came back. Conflating them understated the ratio by ~4 orders of
                # magnitude and mislabelled it, so take the real figure from the executor.
                self.scanned = int(analytics.last_exec_stats().get("rows_scanned", 0))
        return self.runs

    def schema_brief(self) -> str:
        cols = analytics.describe_table(self.ch, self.semantics.table_fqn)
        return (
            f"table: {self.semantics.table_fqn}\n"
            f"entity_key: {self.semantics.entity_key}\n"
            f"funnel: {' -> '.join(self.semantics.ordered_steps)}\n"
            f"anonymous event types (no user_id): {self.semantics.disconnected_event_types or 'none'}\n"
            f"columns: {', '.join(f'{n} {t}' for n, t in cols[:40])}"
        )

    def answer(self, question: str) -> tuple[Answer, list[str]]:
        runs = self.warm()
        frames, rows_sent = analytics.frames_markdown(runs, 40)
        conflicts = metric_policy.load_open_conflicts(self.ch, self.ctx)
        policy = metric_policy.conflict_prompt_prefix(conflicts)
        user = (
            f"{policy}\n"
            f"QUESTION\n{question}\n\n"
            f"FEATURE SCHEMA\n{self.schema_brief()}\n\n"
            f"CONTEXT LAYER (v{self.ctx.version})\n{self.ctx.as_prompt()[:6000]}\n\n"
            f"RESULT TABLES\n{frames}"
        )
        with tracing.trace_run(spec=f"ask:{self.slug}", run_id=tracing.new_run_id(),
                               context_version=self.ctx.version):
            # A question that names this feature's own funnel step / measure supplies
            # its own denominator and is answerable from this table alone -- it is not
            # asking for the disputed org-wide metric, so the conflict does not apply.
            feature_scoped = metric_policy.question_is_feature_scoped(question, self.semantics)

            # Fast path: refuse unqualified conversion questions without an LLM call.
            if metric_policy.mentions_subject(question, "conversion") and conflicts and not feature_scoped:
                refused = metric_policy.refuse_or_qualify_answer(question, "", conflicts)
                if refused:
                    ans = Answer(
                        answer=refused,
                        numbers_cited=[],
                        supporting_queries=[],
                        caveats=["metric_policy refused unqualified conversion rate"],
                        confidence=0.95,
                    )
                    ans.__dict__["_trace_url"] = tracing.current_trace_url()
                    ans.__dict__["_rows_sent"] = 0
                    return ans, []

            ans = llm.complete_json(
                name="ask.answer", system=SYSTEM, user=user, schema=Answer,
                context_version=self.ctx.version,
            )
            replacement = (
                None if feature_scoped
                else metric_policy.refuse_or_qualify_answer(question, ans.answer, conflicts)
            )
            if replacement:
                ans.answer = replacement
                ans.caveats = list(ans.caveats) + [
                    "metric_policy overrode an unqualified conversion-rate answer"
                ]
                ans.numbers_cited = []
            url = tracing.current_trace_url()
        tracing.flush()

        # Ground every asserted number against the tables the answer cites.
        by_name = {r.name: r for r in runs}
        cited = [by_name[n] for n in ans.supporting_queries if n in by_name] or runs
        pool = grounding.evidence_pool(cited)
        bad = [n for n in ans.numbers_cited if not grounding._matches(float(n), pool)]
        ans.__dict__["_trace_url"] = url
        ans.__dict__["_rows_sent"] = rows_sent
        return ans, bad


def show(ans: Answer, ungrounded: list[float], rows_scanned: int) -> None:
    con.print(Panel(Markdown(ans.answer), border_style="green" if not ungrounded else "yellow"))
    if ungrounded:
        con.print(f"[yellow]UNVERIFIED[/yellow] {len(ungrounded)} figure(s) not found in the "
                  f"cited results: {', '.join(f'{n:g}' for n in ungrounded[:6])}")
        con.print("           Treat those as leads, not facts.")
    else:
        con.print(f"[green]grounded[/green]   all {len(ans.numbers_cited)} figure(s) matched the cited results")
    if ans.caveats:
        for c in ans.caveats[:3]:
            con.print(f"[dim]caveat[/dim]     {c}")
    con.print(f"[dim]sources[/dim]    {', '.join(ans.supporting_queries[:4]) or '(none named)'}")
    con.print(f"[dim]scanned[/dim]    {rows_scanned:,} rows in ClickHouse -> "
              f"{ans.__dict__.get('_rows_sent', 0)} rows to the model")
    if ans.__dict__.get("_trace_url"):
        con.print(f"[dim]trace[/dim]      {ans.__dict__['_trace_url']}")


def pick_spec() -> Path:
    dirs = sorted(p for p in SPECS_DIR.iterdir() if (p / "spec.md").exists())
    con.print("\n[bold]specs[/bold]")
    for i, d in enumerate(dirs, 1):
        con.print(f"  {i}. {d.name}")
    while True:
        raw = con.input("\npick a spec [1]: ").strip() or "1"
        if raw.isdigit() and 1 <= int(raw) <= len(dirs):
            return dirs[int(raw) - 1]


def repl(sess: Session) -> None:
    con.rule(f"[bold]{sess.slug}[/bold]")
    con.print(f"entity key : {sess.semantics.entity_key}")
    con.print(f"funnel     : {' -> '.join(sess.semantics.ordered_steps)}")
    con.print("\n[bold]PM questions from the spec[/bold]")
    for i, q in enumerate(sess.questions, 1):
        con.print(f"  {i}. {q}")
    con.print("\n[dim]enter a number, type your own question, or /quit[/dim]")

    while True:
        try:
            raw = con.input("\n[bold cyan]ask>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not raw:
            continue
        if raw in ("/q", "/quit", "/exit"):
            return
        if raw == "/questions":
            for i, q in enumerate(sess.questions, 1):
                con.print(f"  {i}. {q}")
            continue
        question = sess.questions[int(raw) - 1] if (raw.isdigit() and 1 <= int(raw) <= len(sess.questions)) else raw
        con.print(f"[dim]{question}[/dim]")
        try:
            ans, bad = sess.answer(question)
        except Exception as exc:  # noqa: BLE001 - a REPL must survive a bad answer
            con.print(f"[red]failed[/red] {exc}")
            continue
        scanned = sess.scanned
        show(ans, bad, scanned)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ask a feature's PM questions, grounded in ClickHouse")
    ap.add_argument("--spec", type=Path, help="spec directory (or spec.md path)")
    ap.add_argument("--question", type=str, help="one-shot question; omit for interactive")
    ap.add_argument("--list", action="store_true", help="list the spec's PM questions and exit")
    args = ap.parse_args()

    spec_dir = args.spec or pick_spec()
    if spec_dir.is_file():
        spec_dir = spec_dir.parent
    sess = Session(spec_dir, CH())

    if args.list:
        for i, q in enumerate(sess.questions, 1):
            con.print(f"  {i}. {q}")
        return 0
    if args.question:
        ans, bad = sess.answer(args.question)
        show(ans, bad, sess.scanned)
        return 0
    repl(sess)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
