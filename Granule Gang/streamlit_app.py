import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional

import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.analytics.agent import AnalyticsAgent
from agents.analytics.mcp_client import ClickHouseMCPClient
from agents.config import get_config
from agents.context.agent import ContextAgent
from agents.instrumentation.agent import InstrumentationAgent
from agents.setup import ensure_control_tables
from main import _default_for_column, _flatten_event_row


@st.cache_resource(show_spinner=False)
def get_mcp_client(host: str, port: int, user: str, password: str, secure: bool, database: str):
    """Spawn the ClickHouse MCP server subprocess once per Streamlit session and
    reuse it across reruns/button clicks -- st.cache_resource keys on the config
    values passed in, so a changed .env (new host/creds) still gets a fresh
    client instead of silently reusing a stale connection. Mirrors main.py's
    pipeline, which routes every AnalyticsAgent query through this same MCP
    server (agents/analytics/mcp_client.py) rather than clickhouse_connect
    directly, falling back to direct-connect only if the server can't start."""
    from agents.config import ClickHouseConfig

    ch_config = ClickHouseConfig(host=host, port=port, user=user, password=password, database=database, secure=secure)
    return ClickHouseMCPClient.connect_or_none(ch_config)


def normalize_schemas(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        normalized: Dict[str, Any] = {}
        for item in payload:
            name = getattr(item, "name", None)
            if name:
                normalized[name] = item
        return normalized
    return {}


def get_clickhouse_client(ch_config):
    if not ch_config or not ch_config.host:
        return None
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=ch_config.host,
        port=ch_config.port,
        username=ch_config.user,
        password=ch_config.password,
        secure=ch_config.secure,
        database=ch_config.database,
    )


def format_insights_for_chat(insights: List[Any]) -> str:
    if not insights:
        return "No insights were generated yet."

    lines: List[str] = []
    for insight in insights:
        title = getattr(insight, "title", "Insight")
        desc = getattr(insight, "description", "")
        metric = getattr(insight, "metric", "N/A")
        value = getattr(insight, "value", "N/A")
        severity = getattr(insight, "severity", "info").upper()
        lines.append(f"- **{title}** [{severity}]")
        lines.append(f"  {desc}")
        lines.append(f"  Metric: {metric} | Value: {value}")
    return "\n".join(lines)

# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Atlys Analytics Agent Pipeline",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stAppViewContainer { padding-top: 1rem; }
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Header & Context
# -----------------------------------------------------------------------------
st.title("🚀 Atlys Click-a-thon 2026 Pipeline")
st.caption(
    "Autonomous Feature Instrumentation, Living Context Update & Insight Engine"
)

# -----------------------------------------------------------------------------
# Sidebar Configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Pipeline Settings")

    with st.expander("Execution Steps", expanded=True):
        run_context = st.checkbox(
            "Context Agent",
            value=True,
            help="Load base context and update registry",
        )
        run_instrumentation = st.checkbox(
            "Instrumentation Agent",
            value=True,
            help="Generate schema and DDL from spec",
        )
        run_ddl = st.checkbox(
            "Execute DDL", value=True, help="Run statements in ClickHouse"
        )
        run_ingestion = st.checkbox(
            "Ingest Events", value=True, help="Load raw event samples"
        )
        run_analytics = st.checkbox(
            "Analytics Agent", value=True, help="Run statistical analysis & LLM reasoning"
        )

    st.divider()

    st.subheader("🌐 Environment & Config")
    ch_config, lf_config, or_config = get_config()

    if ch_config:
        st.success(f"ClickHouse: `{ch_config.host}:{ch_config.port}`")
        st.caption(f"Database target: `{ch_config.database}`")
    else:
        st.error("ClickHouse configuration missing")

    if or_config and or_config.enabled:
        st.success("OpenRouter (LLM) Active")
        st.caption(f"Model: `{or_config.model}`")
    else:
        st.info("LLM disabled — running structural fallback")

    mcp_client = None
    if ch_config and ch_config.host:
        with st.spinner("Connecting to ClickHouse MCP server..."):
            mcp_client = get_mcp_client(
                ch_config.host, ch_config.port, ch_config.user,
                ch_config.password, ch_config.secure, ch_config.database,
            )
        if mcp_client is not None:
            st.success("ClickHouse MCP server connected")
            st.caption("Analytics Agent queries route through `mcp-clickhouse`")
        else:
            st.info("ClickHouse MCP unavailable — querying ClickHouse directly")

    st.divider()
    st.markdown("### Expected Folder Layout")
    st.code(
        """specs/
└── 01_express_checkout/
    ├── spec.md
    └── events.ndjson""",
        language="text",
    )

# -----------------------------------------------------------------------------
# Main Area: Input Selection
# -----------------------------------------------------------------------------
st.header("1. Select Feature Spec")

specs_dir = Path("specs")
spec_dirs = (
    [d for d in specs_dir.iterdir() if d.is_dir()] if specs_dir.exists() else []
)

col1, col2 = st.columns([2, 2])

with col1:
    spec_option = st.selectbox(
        "Choose pre-loaded spec",
        options=[""] + [d.name for d in spec_dirs],
        help="Select a benchmark feature spec directory",
    )

with col2:
    custom_path = st.text_input(
        "Or specify custom directory path",
        placeholder="specs/06_unseen_spec",
    )

st.markdown("**OR** Upload raw files directly:")
uploaded_files = st.file_uploader(
    "Upload spec.md and events.ndjson",
    type=["md", "ndjson", "json", "txt"],
    accept_multiple_files=True,
)

effective_spec_path = None
if uploaded_files:
    if "uploaded_temp_dir" not in st.session_state:
        st.session_state["uploaded_temp_dir"] = tempfile.mkdtemp()

    temp_path = Path(st.session_state["uploaded_temp_dir"])
    for f in uploaded_files:
        (temp_path / f.name).write_bytes(f.getvalue())
    effective_spec_path = temp_path
elif custom_path:
    effective_spec_path = Path(custom_path)
elif spec_option:
    effective_spec_path = Path("specs") / spec_option

st.divider()

# -----------------------------------------------------------------------------
# Action Button & Pipeline Runner
# -----------------------------------------------------------------------------
can_run = effective_spec_path is not None and effective_spec_path.exists()
run_clicked = st.button(
    "🚀 Execute Agentic Pipeline",
    type="primary",
    use_container_width=True,
    disabled=not can_run,
)

if run_clicked:
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        status_text.text("⚙️ Initializing clients and state...")
        progress_bar.progress(5)

        ch_client = get_clickhouse_client(ch_config)

        if ch_client is None:
            st.warning("ClickHouse client could not be initialized. Check CLICKHOUSE_HOST/CLICKHOUSE_PASSWORD and your .env file.")
        else:
            try:
                ensure_control_tables(ch_client)
            except Exception as e:
                st.warning(f"Control tables setup warning: {e}")

        # Helper function for ContextAgent's llm_call_fn parameter
        def dummy_llm_call(prompt: str, span_name: str = "ui_call") -> str:
            return "{}"

        # 1. Context Agent Phase
        if run_context:
            status_text.text("🧠 [Context Agent] Ingesting business logic & updating registry...")
            progress_bar.progress(20)
            
            # FIXED: ContextAgent expects (client, llm_call_fn) as positional parameters
            ca = ContextAgent(client=ch_client if run_ddl else None, llm_call_fn=dummy_llm_call)
            ca.load_v1()  # Load base context and update registry

        # 2. Instrumentation Agent Phase
        if run_instrumentation:
            status_text.text("🔧 [Instrumentation Agent] Designing ClickHouse DDL & schema...")
            progress_bar.progress(40)
            ia = InstrumentationAgent(
                clickhouse_client=ch_client if run_ddl else None,
                context_agent=None,
                openrouter_config=or_config if or_config and or_config.enabled else None,
                database=ch_config.database if ch_config else "atlys",
            )
            schemas = ia.process_spec(effective_spec_path)
            ddl = ia.emit_ddl()

            st.session_state["schemas"] = normalize_schemas(schemas)
            st.session_state["ddl"] = ddl

        # 3. DDL Execution Phase
        if run_ddl and ch_client and "ddl" in st.session_state:
            status_text.text("📝 Executing DDL in ClickHouse...")
            progress_bar.progress(60)
            for statement in st.session_state["ddl"].split(";"):
                stmt = statement.strip()
                if stmt:
                    try:
                        ch_client.command(stmt)
                    except Exception as e:
                        st.warning(f"DDL Statement Warning: {e}")

        # 4. Ingestion Phase
        if run_ingestion and ch_client:
            status_text.text("📥 Ingesting events dataset into ClickHouse...")
            progress_bar.progress(75)

            events_file = effective_spec_path / "events.ndjson"
            if not events_file.exists():
                events_file = effective_spec_path / "events.json"

            if events_file.exists():
                from collections import defaultdict

                records_by_table = defaultdict(list)
                with open(events_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        event_data = json.loads(line)
                        event_type = event_data.get("event", "unknown_event")
                        table_name = event_type.lower().replace("-", "_")
                        records_by_table[table_name].append(_flatten_event_row(event_data))

                for table_name, records in records_by_table.items():
                    if (
                        records
                        and "schemas" in st.session_state
                        and table_name in st.session_state["schemas"]
                    ):
                        try:
                            schema = st.session_state["schemas"][table_name]
                            col_names = [c.name for c in schema.columns]
                            rows = []
                            for r in records:
                                row_values = []
                                for col in schema.columns:
                                    value = r.get(col.name)
                                    if value is None and not col.nullable:
                                        value = _default_for_column(col)
                                    row_values.append(value)
                                rows.append(tuple(row_values))
                            ch_client.insert(
                                f"{ch_config.database}.{table_name}",
                                rows,
                                column_names=col_names,
                            )
                        except Exception as e:
                            st.warning(f"Ingestion warning for `{table_name}`: {e}")

        # 5. Analytics Agent Phase
        if run_analytics and ch_client and st.session_state.get("analytics_question"):
            status_text.text("📊 [Analytics Agent] Executing ClickHouse analysis & context link...")
            progress_bar.progress(90)
            aa = AnalyticsAgent(
                client=ch_client,
                database=ch_config.database if ch_config else "atlys",
                context_agent=None,
                openrouter_config=or_config if or_config and or_config.enabled else None,
                mcp_client=mcp_client,
            )
            question = st.session_state.get("analytics_question", "").strip()
            pm_questions = [question] if question else None
            st.session_state["insights"] = aa.run_full_analysis(
                pm_questions=pm_questions,
                spec_name=spec_option or effective_spec_path.name if effective_spec_path else "",
            )

        progress_bar.progress(100)
        status_text.text("✅ Pipeline run completed successfully!")

    except Exception as e:
        status_text.text("❌ Pipeline failure execution error.")
        st.error(f"Pipeline Execution Failed: {str(e)}")
        st.exception(e)

# -----------------------------------------------------------------------------
# Results View Section
# -----------------------------------------------------------------------------
if "schemas" in st.session_state or "insights" in st.session_state:
    st.header("2. Pipeline Output & Results")

    tab_insights, tab_schema = st.tabs(["💡 Business Insights", "📋 Schemas & DDL"])

    with tab_insights:
        if "schemas" in st.session_state:
            schemas_map = normalize_schemas(st.session_state.get("schemas"))
            st.subheader("New tables added")
            table_names = list(schemas_map.keys())
            if table_names:
                st.table({"Table Name": table_names})
            else:
                st.info("No new tables were generated.")

        st.divider()
        st.subheader("Ask for the insight")
        st.caption("Type a question like 'Which segment converts best?' and the analytics agent will respond with focused insights.")

        prompt = st.chat_input("Ask the analytics agent...")
        if prompt:
            with st.spinner("Generating insight cards..."):
                client = get_clickhouse_client(ch_config)
                if client is None:
                    st.error("ClickHouse is not available right now, so I cannot generate insights.")
                else:
                    aa = AnalyticsAgent(
                        client=client,
                        database=ch_config.database if ch_config else "atlys",
                        context_agent=None,
                        openrouter_config=or_config if or_config and or_config.enabled else None,
                        mcp_client=mcp_client,
                    )
                    # Mirrors the CLI's interactive "ask" flow (handle_insight_request):
                    # question -> SQL -> narrative insight grounded only in that query's
                    # rows. run_full_analysis() instead prepends the generic core-funnel/
                    # drop-off/segment dump before the question's own answer, and the [:6]
                    # slice below never reached the actual answer.
                    insights = aa.handle_insight_request(prompt)
                    st.session_state["insights"] = insights

        if "insights" in st.session_state and st.session_state["insights"]:
            st.divider()
            st.subheader("Latest response")
            insights = st.session_state["insights"][:6]
            for insight in insights:
                sev = getattr(insight, "severity", "info").lower()
                title = getattr(insight, "title", "Insight")
                description = getattr(insight, "description", "")
                metric = getattr(insight, "metric", "N/A")
                value = getattr(insight, "value", "N/A")

                if sev in ["high", "critical", "error"]:
                    st.error(f"### {title}")
                elif sev in ["medium", "warning"]:
                    st.warning(f"### {title}")
                else:
                    st.info(f"### {title}")

                if description:
                    st.markdown(description)
                st.caption(f"**Metric:** `{metric}` &nbsp;·&nbsp; **Value:** `{value}`")
        else:
            st.info("Ask a question to start the analytics insight cards.")

    with tab_schema:
        if "schemas" in st.session_state:
            schemas_map = normalize_schemas(st.session_state.get("schemas"))
            st.subheader("Generated ClickHouse Schemas")
            for table_name, schema in schemas_map.items():
                with st.expander(
                    f"Table: `{table_name}` ({len(schema.columns)} columns)",
                    expanded=True,
                ):
                    table_data = [
                        {
                            "Column Name": col.name,
                            "Type": col.type,
                            "Nullable": "YES" if col.nullable else "NO",
                        }
                        for col in schema.columns
                    ]
                    st.table(table_data)

            st.subheader("Production DDL")
            ddl = st.session_state.get("ddl", "-- No DDL")
            st.text_area("DDL", ddl, height=300)
            st.download_button(
                "📥 Download DDL Script (.sql)",
                data=ddl,
                file_name="clickhouse_instrumentation.sql",
                mime="text/x-sql",
            )
        else:
            st.info("No schema data is available yet.")
