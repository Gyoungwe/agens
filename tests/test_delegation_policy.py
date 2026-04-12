from core.delegation_policy import decide_delegation, looks_like_research_query


def test_research_marker_detection_matches_expected_queries():
    assert (
        looks_like_research_query(
            "Please research recent papers on single-cell RNA-seq"
        )
        is True
    )
    assert looks_like_research_query("hello there") is False


def test_decide_delegation_returns_research_mode_when_research_agent_available():
    decision = decide_delegation(
        user_input="research literature about CRISPR off-target effects",
        available_agents=["research_agent", "writer_agent", "bio_planner_agent"],
    )

    assert decision.mode == "research"
    assert decision.selected_agents == ["research_agent", "writer_agent"]


def test_decide_delegation_returns_clarify_for_broad_workflow_requests():
    decision = decide_delegation(
        user_input="帮我做一个生信 workflow",
        available_agents=["bio_planner_agent", "bio_report_agent"],
        selected_agents=["bio_planner_agent", "bio_report_agent"],
        recommendation="请补充 assay 类型、输入格式和期望产出。",
        decision_reason="Bioinformatics workflow intent detected.",
    )

    assert decision.mode == "clarify_first"
    assert decision.clarification_question == "请补充 assay 类型、输入格式和期望产出。"


def test_decide_delegation_returns_multi_agent_for_specific_workflow_requests():
    decision = decide_delegation(
        user_input="请为 RNA-seq 数据设计 nextflow pipeline 并加上 QC 报告",
        available_agents=["bio_planner_agent", "bio_code_agent", "bio_qc_agent"],
        selected_agents=["bio_planner_agent", "bio_code_agent", "bio_qc_agent"],
        decision_reason="Bioinformatics workflow intent detected; selecting minimal relevant agents.",
    )

    assert decision.mode == "multi_agent"
    assert decision.selected_agents == [
        "bio_planner_agent",
        "bio_code_agent",
        "bio_qc_agent",
    ]


def test_decide_delegation_returns_direct_chat_without_specialized_signals():
    decision = decide_delegation(
        user_input="你好，帮我润色一句英文",
        available_agents=["research_agent", "writer_agent"],
        decision_reason="Detected general conversational intent; no multi-agent collaboration needed.",
    )

    assert decision.mode == "direct_chat"
    assert decision.selected_agents == []
