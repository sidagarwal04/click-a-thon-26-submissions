from atlys_agentic import agents


def test_llm_reads_model_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gemini/gemini-flash-latest")
    monkeypatch.setenv("LLM_TEMPERATURE", "0")
    llm = agents.llm()
    assert llm.model == "gemini/gemini-flash-latest"


def test_all_three_agents_are_memory_free():
    for builder in (
        agents.build_instrumentation_engineer,
        agents.build_context_librarian,
        agents.build_product_analyst,
    ):
        agent = builder()
        assert agent.memory in (False, None), f"{builder.__name__} must not use CrewAI native memory"


def test_instrumentation_engineer_has_schema_tools():
    agent = agents.build_instrumentation_engineer()
    tool_names = {t.name for t in agent.tools}
    assert {"infer_schema", "generate_mv", "execute_ddl"} <= tool_names


def test_context_librarian_has_context_tools():
    agent = agents.build_context_librarian()
    tool_names = {t.name for t in agent.tools}
    assert {"context_diff", "context_upsert"} <= tool_names


def test_product_analyst_has_no_ddl_tool():
    agent = agents.build_product_analyst()
    tool_names = {t.name for t in agent.tools}
    assert "execute_ddl" not in tool_names
    assert {"analytics_compute", "score_confidence"} <= tool_names


def test_agent_configurations_and_execution_parameters():
    cfg = agents.load_agents_config()
    for key in ("instrumentation_engineer", "context_librarian", "product_analyst"):
        assert key in cfg
        assert len(cfg[key]["role"]) > 0
        assert len(cfg[key]["goal"]) > 0
        assert len(cfg[key]["backstory"]) > 0

    for builder in (
        agents.build_instrumentation_engineer,
        agents.build_context_librarian,
        agents.build_product_analyst,
    ):
        agent = builder()
        assert agent.allow_delegation is False
        assert agent.verbose is True
        assert agent.max_iter == 5
        assert len(agent.role) > 0
        assert len(agent.goal) > 0
        assert len(agent.backstory) > 0

