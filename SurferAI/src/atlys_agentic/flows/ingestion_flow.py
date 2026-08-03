import os
from typing import Callable, Generic, TypeVar

from pydantic import BaseModel

from atlys_agentic import agents, paths, prompts, tools, tracing

T = TypeVar("T")

try:
    from crewai.flow.flow import Flow as CrewAIFlow, listen, router, start
except ImportError:  # pragma: no cover
    def start():
        def decorator(fn):
            fn._flow_step = "start"
            return fn
        return decorator

    def listen(target=None):
        def decorator(fn):
            fn._flow_step = "listen"
            fn._listen_target = target
            return fn
        return decorator

    def router(target=None):
        def decorator(fn):
            fn._flow_step = "router"
            fn._router_target = target
            return fn
        return decorator

    class CrewAIFlow(Generic[T]):  # type: ignore
        def __init__(self):
            self.state = None

        def kickoff(self, inputs: dict = None):
            pass


class IngestionState(BaseModel):
    spec_id: str = ""
    table_name: str = ""
    ddl: str = ""
    mv_ddl: str = ""
    approved: bool = False
    dry_run: bool = False
    trace_id: str = ""
    ddl_result: dict = {}
    diff_result: dict = {}
    table_consultation: dict = {}
    reasoning: dict = {}


class IngestionFlow(CrewAIFlow[IngestionState]):
    input_fn: Callable[[str], str] = staticmethod(input)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # crewai's typed Flow (Flow[IngestionState]) auto-creates `state` from the
        # generic parameter and exposes it as a read-only property (no setter).
        # Assigning self.state here raises AttributeError on modern crewai; only
        # initialise manually for the no-crewai fallback base class.
        if getattr(self, "state", None) is None:
            try:
                self.state = IngestionState()
            except AttributeError:
                pass

    @start()
    def instrumentation_step(self):
        """Step 1: Instrumentation Agent consults Context Librarian to inspect chDB/ClickHouse metadata, then designs schema, MV, and 6-pillar decision."""
        mode = "dry_run" if self.state.dry_run else "live_run"
        self.state.trace_id = tracing.new_trace(self.state.spec_id, run_mode=mode)
        ndjson_path = paths.events_ndjson(self.state.spec_id)
        spec_text = paths.spec_md(self.state.spec_id).read_text(encoding="utf-8")
        if not self.state.table_name:
            self.state.table_name = tools.Tool_Infer_Table_Name(self.state.spec_id, spec_text)

        # 1. Consult Context Librarian for existing chDB and ClickHouse metadata
        context_librarian = agents.build_context_librarian()
        preliminary_cols = []
        self.state.table_consultation = tools.Tool_Consult_Internal_Tables(
            self.state.spec_id, preliminary_cols, self.state.table_name
        )

        api_key = (
            os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        ).strip()
        model_name = os.environ.get("LLM_MODEL", "gemini/gemini-2.5-flash")

        # Context Librarian provides existing schema catalog & metric definitions
        if api_key and not os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                import litellm
                librarian_prompt = (
                    f"You are the {context_librarian.role}.\n"
                    f"Goal: {context_librarian.goal}\n\n"
                    f"Incoming Feature Spec: '{self.state.spec_id}' (Target Table: '{self.state.table_name}')\n"
                    f"Consultation data from schema_registry & business_context:\n"
                    f"{self.state.table_consultation}\n\n"
                    f"Summarize the existing table versions, column overlap, and known metric rules for the Instrumentation Engineer."
                )
                resp = litellm.completion(
                    model=model_name,
                    messages=[{"role": "user", "content": librarian_prompt}],
                    api_key=api_key,
                    temperature=0.0,
                )
                librarian_context_brief = resp.choices[0].message.content.strip()
                tracing.generation(
                    name="context_librarian::consult_context",
                    model=model_name,
                    input={"spec_id": self.state.spec_id, "table": self.state.table_name},
                    output=librarian_context_brief,
                    metadata={"agent": "context_librarian", "role": context_librarian.role},
                    run_mode=mode,
                )
            except Exception:
                pass

        # 2. Instrumentation Engineer infers production ClickHouse DDL & Materialized View using Context Librarian's catalog briefing
        self.state.ddl = tools.Tool_Infer_Schema(ndjson_path, spec_text, self.state.table_name)
        self.state.mv_ddl = tools.Tool_Generate_MV(self.state.table_name, self.state.ddl)

        # 3. Grounded consultation with full inferred column set
        cols = tools._columns_from_ddl(self.state.ddl)
        self.state.table_consultation = tools.Tool_Consult_Internal_Tables(
            self.state.spec_id, cols, self.state.table_name
        )
        self.state.reasoning = tools.Tool_Explain_Schema_Rationale(
            self.state.table_name,
            self.state.ddl,
            self.state.mv_ddl,
            self.state.table_consultation,
            spec_text,
        )

        # 4. Dynamic LLM Schema Architectural Decision by Instrumentation Engineer
        instrumentation_engineer = agents.build_instrumentation_engineer()
        if api_key and not os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                import litellm
                prompt = prompts.build_instrumentation_engineer_prompt(
                    spec_id=self.state.spec_id,
                    table_name=self.state.table_name,
                    ddl=self.state.ddl,
                    strategy=self.state.table_consultation.get("strategy", "CREATE_NEW"),
                    recommendation=self.state.table_consultation.get("recommendation", ""),
                )
                resp = litellm.completion(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": f"You are the {instrumentation_engineer.role}. {instrumentation_engineer.backstory}"},
                        {"role": "user", "content": prompt},
                    ],
                    api_key=api_key,
                    temperature=0.0,
                )
                llm_reasoning = resp.choices[0].message.content.strip()
                if llm_reasoning:
                    self.state.reasoning["high_level_summary"] = llm_reasoning
                    self.state.reasoning["llm_architectural_decision"] = llm_reasoning

                usage = {
                    "prompt_tokens": getattr(getattr(resp, "usage", None), "prompt_tokens", 0),
                    "completion_tokens": getattr(getattr(resp, "usage", None), "completion_tokens", 0),
                }
                tracing.generation(
                    name="instrumentation_engineer::schema_design",
                    model=model_name,
                    input={"prompt": prompt, "spec_id": self.state.spec_id},
                    output=llm_reasoning,
                    usage_details=usage,
                    metadata={
                        "agent": "instrumentation_engineer",
                        "role": instrumentation_engineer.role,
                        "spec_id": self.state.spec_id,
                        "table": self.state.table_name,
                    },
                    run_mode=mode,
                )
            except Exception:
                pass

        tracing.span(
            self.state.trace_id,
            "instrumentation_step",
            {"spec_id": self.state.spec_id, "table": self.state.table_name},
            {
                "ddl": self.state.ddl,
                "table_strategy": self.state.table_consultation.get("strategy"),
                "context_consulted_via": context_librarian.role,
                "agent": instrumentation_engineer.role,
            },
            run_mode=mode,
        )
        return self.state.ddl

    def infer_schema(self):
        """Backward-compatible alias for instrumentation_step."""
        return self.instrumentation_step()

    @listen(instrumentation_step)
    def context_step(self):
        """Step 2: Context Agent receives Instrumentation output, runs diff on chDB, and audits integrity."""
        columns = tools._columns_from_ddl(self.state.ddl)
        self.state.diff_result = tools.Tool_Context_Diff(self.state.table_name, columns)

        # Dynamic LLM Context Librarian Semantic Diff & Integrity Review
        context_librarian = agents.build_context_librarian()
        api_key = (
            os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        ).strip()
        model_name = os.environ.get("LLM_MODEL", "gemini/gemini-2.5-flash")
        if api_key and not os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                import litellm
                diff = self.state.diff_result or {}
                prompt = prompts.build_context_librarian_prompt(
                    spec_id=self.state.spec_id,
                    table_name=self.state.table_name,
                    additions=diff.get("additions", []),
                    conflicts=diff.get("conflicts", []),
                    gaps=diff.get("gaps", []),
                )
                resp = litellm.completion(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": f"You are the {context_librarian.role}. {context_librarian.backstory}"},
                        {"role": "user", "content": prompt},
                    ],
                    api_key=api_key,
                    temperature=0.0,
                )
                librarian_summary = resp.choices[0].message.content.strip()
                if librarian_summary:
                    self.state.diff_result["llm_integrity_audit"] = librarian_summary

                usage = {
                    "prompt_tokens": getattr(getattr(resp, "usage", None), "prompt_tokens", 0),
                    "completion_tokens": getattr(getattr(resp, "usage", None), "completion_tokens", 0),
                }
                tracing.generation(
                    name="context_librarian::context_audit",
                    model=model_name,
                    input={"prompt": prompt, "spec_id": self.state.spec_id},
                    output=librarian_summary,
                    usage_details=usage,
                    metadata={
                        "agent": "context_librarian",
                        "role": context_librarian.role,
                        "spec_id": self.state.spec_id,
                        "table": self.state.table_name,
                    },
                    run_mode="dry_run" if self.state.dry_run else "live_run",
                )
            except Exception:
                pass

        tracing.span(
            self.state.trace_id,
            "context_step",
            {"table": self.state.table_name, "dry_run": self.state.dry_run},
            {"diff": self.state.diff_result, "agent": context_librarian.role},
            run_mode="dry_run" if self.state.dry_run else "live_run",
        )
        return self.state.diff_result

    def dry_run_audit(self):
        """Backward-compatible alias for context_step."""
        return self.context_step()

    def format_proposal_summary(self) -> str:
        """Format the complete Instrumentation Engineer decision breakdown and context diff for operator review."""
        consult = self.state.table_consultation or {}
        reasoning = self.state.reasoning or {}
        deep = reasoning.get("technical_deep_dive") or {}
        diff = self.state.diff_result or {}

        summary_lines = [
            "=" * 80,
            "🧠 INSTRUMENTATION ENGINEER ARCHITECTURAL DECISION & RATIONALE",
            "=" * 80,
            f"• Target Table: {self.state.table_name}",
            f"• Executive Summary: {reasoning.get('high_level_summary', '')}",
            "",
            "--- 1. Table Strategy Decision ---",
            f"  Strategy: {consult.get('strategy', 'CREATE_NEW')}",
            f"  Recommendation: {consult.get('recommendation', '')}",
            "",
            "--- 2. Primary Sorting Key (ORDER BY) ---",
            f"  {deep.get('ordering_mechanics', reasoning.get('ordering_reasoning', ''))}",
            "",
            "--- 3. Partitioning Strategy (PARTITION BY) ---",
            f"  {deep.get('partitioning_mechanics', reasoning.get('partitioning_reasoning', ''))}",
            "",
            "--- 4. Encodings & Data Types ---",
            f"  {deep.get('column_encodings_and_compression', reasoning.get('types_reasoning', ''))}",
            "",
            "--- 5. Materialized View Rollup ---",
            f"  {deep.get('materialized_view_rollup', reasoning.get('mv_reasoning', ''))}",
            "",
            "--- 6. Data Lifecycle Retention (TTL) ---",
            f"  {deep.get('lifecycle_retention', reasoning.get('retention_reasoning', ''))}",
            "",
            "--- Proposed ClickHouse DDL ---",
            self.state.ddl,
        ]

        if self.state.mv_ddl:
            summary_lines.extend([
                "",
                "--- Proposed Materialized View (SummingMergeTree) ---",
                self.state.mv_ddl,
            ])

        additions = diff.get("additions", [])
        conflicts = diff.get("conflicts", [])
        gaps = diff.get("gaps", [])

        summary_lines.extend([
            "",
            "--- Context Diff Audit (Context Librarian) ---",
            f"  • New Attributes to Sync ({len(additions)}): {', '.join(additions) if additions else 'None'}",
            f"  • Metric Conflicts Detected: {', '.join(conflicts) if conflicts else 'None'}",
            f"  • Undocumented Gaps Flagged: {', '.join(gaps) if gaps else 'None'}",
            "=" * 80,
        ])
        return "\n".join(summary_lines)

    @listen(context_step)
    def human_gate(self):
        """Step 3: Human-in-the-Loop review presenting complete proposal."""
        # Ensure context diff has executed before presenting to operator
        if not self.state.diff_result:
            self.context_step()

        # Always output the full Instrumentation Engineer decision rationale and proposed schema
        print("\n" + self.format_proposal_summary())

        if self.state.dry_run:
            prompt_text = (
                "\n[DRY RUN MODE — Non-Mutating Proposal Review]\n"
                "Type APPROVE to confirm proposal review (or press Enter/reject to abort): "
            )
            answer = self.input_fn(prompt_text)
            self.state.approved = answer == "APPROVE"
            tracing.span(
                self.state.trace_id,
                "human_gate_dry_run",
                {"prompt_answer": answer, "dry_run": True},
                {"approved": self.state.approved},
                run_mode="dry_run",
            )
        else:
            prompt_text = (
                "\n[LIVE DEPLOYMENT MODE]\n"
                "Type APPROVE to execute on ClickHouse Cloud: "
            )
            answer = self.input_fn(prompt_text)
            self.state.approved = answer == "APPROVE"
            tracing.span(
                self.state.trace_id,
                "human_gate",
                {"prompt_answer": answer, "dry_run": False},
                {"approved": self.state.approved},
                run_mode="live_run",
            )

    @router(human_gate)
    def route_gate(self):
        """Step 4: Route based on operator authorization."""
        return "approved" if self.state.approved else "rejected"

    @listen("approved")
    def execute_and_audit(self):
        """Step 5a: Context Librarian (Sole DB Custodian) executes DDL on ClickHouse Cloud and synchronizes chDB."""
        context_librarian = agents.build_context_librarian()
        self.state.ddl_result = tools.Tool_Execute_DDL(self.state.ddl, self.state.table_name, self.state.spec_id)
        tracing.span(
            self.state.trace_id,
            "execute_ddl",
            {"table": self.state.table_name, "custodian": context_librarian.role},
            self.state.ddl_result,
            run_mode="live_run",
        )

        if self.state.mv_ddl and self.state.ddl_result.get("status") == "ok":
            tools.Tool_Execute_DDL(self.state.mv_ddl, f"{self.state.table_name}_daily_mv", self.state.spec_id)

        if not self.state.diff_result:
            columns = tools._columns_from_ddl(self.state.ddl)
            self.state.diff_result = tools.Tool_Context_Diff(self.state.table_name, columns)
            tracing.span(
                self.state.trace_id,
                "context_diff",
                {"table": self.state.table_name, "custodian": context_librarian.role},
                self.state.diff_result,
                run_mode="live_run",
            )
        for addition in self.state.diff_result.get("additions", []):
            if "." in addition:
                table, col = addition.split(".", 1)
            else:
                table, col = self.state.table_name, addition
            tools.Tool_Context_Upsert(
                section="Event tables",
                key=addition,
                definition=f"New column from {self.state.spec_id}: {col} on {table}.",
                agent="context_librarian",
                trace_id=self.state.trace_id,
            )
        print(f"\n🎉 Context Librarian successfully deployed table '{self.state.table_name}' to ClickHouse Cloud and updated chDB.")

    def dry_run_approved(self):
        tracing.span(
            self.state.trace_id,
            "dry_run_proposal_approved",
            {"table": self.state.table_name},
            {"approved": True, "dry_run": True},
            run_mode="dry_run",
        )
        print(f"\n✅ Dry-run proposal for '{self.state.table_name}' reviewed and approved by operator. (ClickHouse Cloud and chDB remain untouched).")

    def dry_run_aborted(self):
        tracing.span(
            self.state.trace_id,
            "dry_run_proposal_rejected",
            {"table": self.state.table_name},
            {"approved": False, "dry_run": True},
            run_mode="dry_run",
        )
        print(f"\n❌ Dry-run proposal review for '{self.state.table_name}' aborted by operator.")

    @listen("rejected")
    def abort(self):
        tracing.span(
            self.state.trace_id,
            "human_gate_rejected",
            {"table": self.state.table_name},
            {"approved": False},
            run_mode="live_run",
        )
        print(f"\n❌ DDL for {self.state.table_name} rejected. Ingestion aborted.")


def run(
    spec_id: str,
    table_name: str = None,
    input_fn: Callable[[str], str] = None,
    dry_run: bool = False,
    **kwargs,
) -> dict:
    flow = IngestionFlow()
    if input_fn is not None:
        flow.input_fn = input_fn
    elif dry_run:
        flow.input_fn = lambda _: "APPROVE"
    else:
        flow.input_fn = input

    flow.state.spec_id = spec_id
    flow.state.table_name = table_name or ""
    flow.state.dry_run = dry_run

    mode = "dry_run" if dry_run else "live_run"
    with tracing.trace(
        f"clickathon-{mode}-{spec_id}",
        input={"spec_id": spec_id, "table_name": table_name, "dry_run": dry_run},
        run_mode=mode,
    ):
        # Step through the flow sequence deterministically
        flow.infer_schema()
        flow.dry_run_audit()
        flow.human_gate()
        branch = flow.route_gate()
        if branch == "approved":
            if not dry_run:
                flow.execute_and_audit()
            else:
                flow.dry_run_approved()
        else:
            if not dry_run:
                flow.abort()
            else:
                flow.dry_run_aborted()

    return {
        "table_name": flow.state.table_name,
        "approved": flow.state.approved,
        "dry_run": flow.state.dry_run,
        "ddl": flow.state.ddl,
        "mv_ddl": flow.state.mv_ddl,
        "table_consultation": flow.state.table_consultation,
        "reasoning": flow.state.reasoning,
        "ddl_result": flow.state.ddl_result,
        "diff_result": flow.state.diff_result,
        "trace_id": flow.state.trace_id,
    }
