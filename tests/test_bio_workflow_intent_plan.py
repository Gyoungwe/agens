import pytest

from api.main import (
    WorkflowIntentConfirmRequest,
    WorkflowPlanGenerateRequest,
    BioWorkflowRequest,
    confirm_bio_intent,
    generate_bio_workflow_plan,
    run_bio_workflow,
    _generate_workflow_plan,
    _normalize_workflow_intent,
    _stage_specs_from_plan,
)
from api.models.bio_workflow import (
    WorkflowIntentSpec,
    WorkflowPlanSpec,
    WorkflowStageSpec,
)


def test_normalize_workflow_intent_adds_inference_and_required_fields():
    intent = _normalize_workflow_intent(
        goal="Run RNA-seq differential expression",
        dataset="demo-min",
        intent=WorkflowIntentSpec(
            goal="Run RNA-seq differential expression",
            assay_type="rna_seq",
        ),
    )

    assert intent.request_id
    assert intent.dataset == "demo-min"
    assert intent.system_inference is not None
    assert intent.system_inference.inferred_assay_type == "rna_seq"
    assert "reference_bundle" in intent.fields_requiring_confirmation
    assert "expected_outputs" in intent.fields_requiring_confirmation


def test_generate_workflow_plan_preserves_five_stage_fallback_shape():
    intent = _normalize_workflow_intent(
        goal="Run WGS variant calling",
        dataset="demo-min",
        intent=WorkflowIntentSpec(goal="Run WGS variant calling", assay_type="wgs"),
    )

    plan = _generate_workflow_plan(intent, timeout_seconds=120)
    stage_specs = _stage_specs_from_plan(plan, timeout_seconds=120)

    assert plan.plan_id
    assert plan.workflow_family == "wgs-variant"
    assert [stage.name for stage in plan.stages] == [
        "planning",
        "codegen",
        "qc",
        "report",
        "evolution",
    ]
    assert [spec.name for spec in stage_specs] == [
        "planning",
        "codegen",
        "qc",
        "report",
        "evolution",
    ]
    assert stage_specs[1].depends_on == ["planning"]
    assert stage_specs[2].depends_on == ["planning", "codegen"]


def test_generate_workflow_plan_is_assay_aware_for_rna_seq():
    intent = _normalize_workflow_intent(
        goal="Run RNA-seq differential expression",
        dataset="demo-min",
        intent=WorkflowIntentSpec(
            goal="Run RNA-seq differential expression", assay_type="rna_seq"
        ),
    )

    plan = _generate_workflow_plan(intent, timeout_seconds=120)

    assert plan.workflow_family == "rna-seq"
    assert plan.stages[1].outputs == ["count_matrix", "commands", "scripts"]
    assert "quantification" in (plan.stages[1].prompt_template or "")
    assert "batch effects" in (plan.stages[2].prompt_template or "")


def test_generate_workflow_plan_is_assay_aware_for_metagenomics():
    intent = _normalize_workflow_intent(
        goal="Profile metagenomics samples",
        dataset="demo-min",
        intent=WorkflowIntentSpec(
            goal="Profile metagenomics samples", assay_type="metagenomics"
        ),
    )

    plan = _generate_workflow_plan(intent, timeout_seconds=120)

    assert plan.workflow_family == "metagenomics"
    assert plan.stages[1].outputs == [
        "taxonomic_profile",
        "functional_profile",
        "commands",
    ]
    assert "host depletion" in (plan.stages[1].prompt_template or "")
    assert "classifier confidence" in (plan.stages[2].prompt_template or "")


@pytest.mark.asyncio
async def test_confirm_bio_intent_endpoint_returns_confirmation_payload():
    response = await confirm_bio_intent(
        WorkflowIntentConfirmRequest(
            goal="Analyze RNA-seq",
            dataset="demo-min",
            intent=WorkflowIntentSpec(goal="Analyze RNA-seq", assay_type="rna_seq"),
        )
    )

    assert response["success"] is True
    assert response["intent"]["dataset"] == "demo-min"
    assert response["workflow_family"] == "bio::rna_seq"
    assert response["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_generate_bio_workflow_plan_endpoint_returns_dynamic_plan():
    response = await generate_bio_workflow_plan(
        WorkflowPlanGenerateRequest(
            intent=WorkflowIntentSpec(
                goal="Analyze metagenomics samples",
                assay_type="metagenomics",
                dataset="demo-min",
            )
        )
    )

    assert response["success"] is True
    assert (
        response["intent"]["system_inference"]["inferred_workflow_family"]
        == "bio::metagenomics"
    )
    assert response["plan"]["workflow_family"] == "metagenomics"
    assert len(response["plan"]["stages"]) == 5


@pytest.mark.asyncio
async def test_execute_bio_workflow_clarifies_before_execution_for_underspecified_request():
    response = await run_bio_workflow(
        BioWorkflowRequest(
            goal="给我一个处理高重复序列优化的基因组组装流程",
            dataset="chat-session",
        )
    )

    assert response["status"] == "needs_user_input"
    assert response["needs_user_input"] is True
    assert response["total_stages"] == 0
    assert "关键信息" in response["user_question"]
    assert len(response["required_fields"]) >= 1


@pytest.mark.asyncio
async def test_plan_pipeline_skill_returns_known_artifacts():
    from skills.plan_pipeline.skill import Skill as PlanPipelineSkill
    from core.base_skill import SkillInput

    skill = PlanPipelineSkill()

    rna_result = await skill.run(
        SkillInput(
            instruction="Run RNA-seq differential expression",
            context={
                "assay_type": "rna_seq",
                "expected_outputs": ["count_matrix", "qc_report"],
            },
        )
    )
    assert rna_result["workflow_family"] == "rna-seq"
    assert rna_result["assay_type"] == "rna_seq"
    assert len(rna_result["stages"]) == 5
    assert rna_result["stages"][0]["name"] == "planning"
    assert rna_result["stages"][1]["name"] == "codegen"
    assert rna_result["stages"][1]["goal"]

    wgs_result = await skill.run(
        SkillInput(
            instruction="Call variants from WGS",
            context={"assay_type": "wgs"},
        )
    )
    assert wgs_result["workflow_family"] == "wgs-variant"

    meta_result = await skill.run(
        SkillInput(
            instruction="Profile metagenomics",
            context={"assay_type": "metagenomics"},
        )
    )
    assert meta_result["workflow_family"] == "metagenomics"
    assert "taxonomic_profile" in meta_result["stages"][1]["outputs"]


@pytest.mark.asyncio
async def test_qc_review_skill_returns_structured_qc_checks():
    from skills.qc_review.skill import Skill as QCReviewSkill
    from core.base_skill import SkillInput

    skill = QCReviewSkill()
    result = await skill.run(SkillInput(instruction="QC review for RNA-seq run"))
    assert result["status"] == "reviewed"
    assert isinstance(result["checks"], list)
    assert all("status" in c for c in result["checks"])
    assert all("name" in c for c in result["checks"])
    assert all("recommendation" in c for c in result["checks"])


@pytest.mark.asyncio
async def test_compile_bio_report_skill_returns_structured_sections():
    from skills.compile_bio_report.skill import Skill as CompileBioReportSkill
    from core.base_skill import SkillInput

    skill = CompileBioReportSkill()
    result = await skill.run(SkillInput(instruction="Compile report for RNA-seq run"))
    assert result["title"] == "Bioinformatics Workflow Report"
    assert isinstance(result["sections"], list)
    headings = {s["heading"] for s in result["sections"]}
    assert "executive_summary" in headings
    assert "key_findings" in headings


@pytest.mark.asyncio
async def test_generate_bio_code_skill_is_assay_aware():
    from skills.generate_bio_code.skill import Skill as GenerateBioCodeSkill
    from core.base_skill import SkillInput

    skill = GenerateBioCodeSkill()

    rna_result = await skill.run(
        SkillInput(
            instruction="Generate RNA-seq pipeline",
            context={"assay_type": "rna_seq"},
        )
    )
    assert rna_result["engine"] == "nextflow"
    assert rna_result["assay_type"] == "rna_seq"
    assert len(rna_result["steps"]) == 4
    step_names = {s["name"] for s in rna_result["steps"]}
    assert "ALIGN" in step_names
    assert "QUANTIFY" in step_names

    wgs_result = await skill.run(
        SkillInput(
            instruction="Generate WGS pipeline",
            context={"assay_type": "wgs"},
        )
    )
    assert wgs_result["assay_type"] == "wgs"
    wgs_step_names = {s["name"] for s in wgs_result["steps"]}
    assert "ALIGN" in wgs_step_names
    assert "HAPLOTYPECALLER" in wgs_step_names

    meta_result = await skill.run(
        SkillInput(
            instruction="Generate metagenomics pipeline",
            context={"assay_type": "metagenomics"},
        )
    )
    assert meta_result["assay_type"] == "metagenomics"
    assert any(s["name"] == "TAXAPROFILE" for s in meta_result["steps"])


@pytest.mark.asyncio
async def test_bio_code_agent_prompt_mentions_nextflow_and_processes():
    from agents.bio_code_agent.bio_code_agent import BioCodeAgent
    from unittest.mock import AsyncMock, MagicMock

    agent = BioCodeAgent(
        bus=MagicMock(),
        provider=MagicMock(),
    )
    agent.use_skill = AsyncMock(
        return_value={
            "engine": "nextflow",
            "assay_type": "rna_seq",
            "params": {"outdir": "results/rnaseq"},
            "steps": [
                {"Name": "ALIGN", "tool": "star", "input": "reads", "output": "bam"},
                {
                    "Name": "QUANTIFY",
                    "tool": "featurecounts",
                    "input": "bam",
                    "output": "counts",
                },
            ],
        }
    )
    agent._execute_with_llm = AsyncMock(
        return_value='{"engine":"nextflow","workflow_family":"rna-seq","assay_type":"rna_seq","params":{"outdir":"results/rnaseq"},"processes":[{"name":"ALIGN","tool":"star","input":"reads","output":"bam","description":""}],"nextflow_script":"#!/usr/bin/env nextflow\\n\\nparams.outdir = \\"results/rnaseq\\"\\n\\nprocess ALIGN {\\n  input:\\n    path reads\\n  output:\\n    path \\"*.bam\\"\\n  \\"\\"\\"\\n  star reads\\n  \\"\\"\\"\\n}\\n\\nworkflow {\\n  ALIGN(params.reads)\\n}","snakemake_script":"","entrypoint":"workflow"}'
    )

    result = await agent.execute(
        instruction="Generate RNA-seq pipeline",
        context={"workflow_family": "rna-seq"},
    )

    assert "nextflow_script" in result
    assert "process" in result.lower()
    agent.use_skill.assert_awaited_once()


def test_harness_stage_result_has_provenance_field():
    from core.bio_harness import HarnessStageResult

    result = HarnessStageResult(
        stage="qc",
        agent_id="bio_qc_agent",
        status="ok",
        elapsed_ms=5000,
        trace_id="trace-1",
        error=None,
        output='{"overall_pass":true,"checks":[],"critical_failures":[]}',
    )
    assert hasattr(result, "provenance")
    d = result.to_dict()
    assert "provenance" in d


def test_harness_stage_spec_has_qc_gate_field():
    from core.bio_harness import HarnessStageSpec

    spec = HarnessStageSpec(
        name="qc",
        agent_id="bio_qc_agent",
        prompt="qc",
        qc_gate=True,
    )
    assert spec.qc_gate is True
    spec2 = HarnessStageSpec(
        name="codegen", agent_id="bio_code_agent", prompt="codegen"
    )
    assert spec2.qc_gate is False


@pytest.mark.asyncio
async def test_qc_gate_blocks_downstream_on_fail():
    import json

    from core.bio_harness import BioWorkflowHarness, HarnessStageSpec

    class FakeStore:
        def __init__(self):
            self.rows = []

        def save_result(self, session_id, trace_id, agent_id, result, status="ok"):
            self.rows.append(
                {
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "agent_id": agent_id,
                    "result": result,
                    "status": status,
                }
            )

        def get_results(self, session_id):
            return [r for r in self.rows if r["session_id"] == session_id]

    class FakeSessionManager:
        def __init__(self):
            self.store = FakeStore()

    class FakeVectorStore:
        async def add(self, **kwargs):
            return "mem-1"

    class FakeKnowledgeBase:
        async def add(self, **kwargs):
            return "kb-1"

    class FakeLogger:
        def info(self, msg):
            pass

        def warning(self, msg):
            pass

    harness = BioWorkflowHarness(
        session_manager=FakeSessionManager(),
        logger=FakeLogger(),
        vector_store=FakeVectorStore(),
        knowledge_base=FakeKnowledgeBase(),
    )

    qc_fail_output = json.dumps(
        {"overall_pass": False, "checks": [], "critical_failures": ["low_mapping_rate"]}
    )

    call_log = []

    class StubOrchestrator:
        def __init__(self):
            self.call_log = call_log

        async def run_single_agent(
            self,
            user_input,
            agent_id,
            session_id=None,
            trace_id=None,
            runtime_context=None,
        ):
            self.call_log.append(agent_id)
            if agent_id == "bio_qc_agent":
                return qc_fail_output
            return '{"status":"ok"}'

    stage_specs = [
        HarnessStageSpec(
            name="planning",
            agent_id="bio_planner_agent",
            prompt="plan {goal}",
            critical=True,
        ),
        HarnessStageSpec(
            name="codegen",
            agent_id="bio_code_agent",
            prompt="codegen",
            depends_on=["planning"],
        ),
        HarnessStageSpec(
            name="qc",
            agent_id="bio_qc_agent",
            prompt="qc",
            depends_on=["planning", "codegen"],
            qc_gate=True,
        ),
        HarnessStageSpec(
            name="report",
            agent_id="bio_report_agent",
            prompt="report",
            depends_on=["qc"],
        ),
    ]

    result = await harness.run(
        orchestrator=StubOrchestrator(),
        session_id="sess-qc-gate",
        trace_id="trace-qc-gate",
        goal="test qc gate",
        dataset="test",
        stage_specs=stage_specs,
        continue_on_error=False,
        scope_id="scope-qc-gate",
        provider_id="test",
    )

    assert result["success"] is False, (
        f"expected success=False but got True. stage_results={[r['stage'] + ':' + str(r.get('error', '')) for r in result['stage_results']]}"
    )
    report_stages = [r for r in result["stage_results"] if r["stage"] == "report"]
    assert len(report_stages) == 1
    assert (
        report_stages[0].get("error") and "qc_gate_failed" in report_stages[0]["error"]
    ), (
        f"report should have qc_gate_failed error but got: {report_stages[0].get('error')}"
    )


@pytest.mark.asyncio
async def test_workflow_pauses_when_stage_requests_user_input():
    import json

    from core.bio_harness import BioWorkflowHarness, HarnessStageSpec

    class FakeStore:
        def __init__(self):
            self.rows = []

        def save_result(self, session_id, trace_id, agent_id, result, status="ok"):
            self.rows.append(
                {
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "agent_id": agent_id,
                    "result": result,
                    "status": status,
                }
            )

        def get_results(self, session_id):
            return [r for r in self.rows if r["session_id"] == session_id]

    class FakeSessionManager:
        def __init__(self):
            self.store = FakeStore()

    class FakeVectorStore:
        async def add(self, **kwargs):
            return "mem-1"

    class FakeKnowledgeBase:
        async def add(self, **kwargs):
            return "kb-1"

    class FakeLogger:
        def info(self, msg):
            pass

        def warning(self, msg):
            pass

    harness = BioWorkflowHarness(
        session_manager=FakeSessionManager(),
        logger=FakeLogger(),
        vector_store=FakeVectorStore(),
        knowledge_base=FakeKnowledgeBase(),
    )

    call_log = []

    class StubOrchestrator:
        def __init__(self):
            self.call_log = call_log

        async def run_single_agent(
            self,
            user_input,
            agent_id,
            session_id=None,
            trace_id=None,
            runtime_context=None,
        ):
            self.call_log.append(agent_id)
            if agent_id == "bio_planner_agent":
                return json.dumps(
                    {
                        "needs_user_input": True,
                        "user_question": "Please provide reference bundle (genome + annotation).",
                        "required_fields": [
                            "reference_bundle.genome",
                            "reference_bundle.annotation",
                        ],
                    }
                )
            return '{"status":"ok"}'

    stage_specs = [
        HarnessStageSpec(name="planning", agent_id="bio_planner_agent", prompt="plan"),
        HarnessStageSpec(
            name="codegen",
            agent_id="bio_code_agent",
            prompt="codegen",
            depends_on=["planning"],
        ),
    ]

    result = await harness.run(
        orchestrator=StubOrchestrator(),
        session_id="sess-needs-input",
        trace_id="trace-needs-input",
        goal="test needs input",
        dataset="test",
        stage_specs=stage_specs,
        continue_on_error=False,
        scope_id="scope-needs-input",
        provider_id="test",
    )

    assert result["status"] == "needs_user_input"
    assert result["needs_user_input"] is True
    assert "reference_bundle.genome" in result["required_fields"]
    skipped_codegen = [r for r in result["stage_results"] if r["stage"] == "codegen"]
    assert len(skipped_codegen) == 1
    assert skipped_codegen[0]["status"] in ("ok", "error")


@pytest.mark.asyncio
async def test_harness_resume_skips_completed_stages():
    from core.bio_harness import (
        BioWorkflowHarness,
        HarnessStageSpec,
        HarnessStageResult,
    )

    class FakeStore:
        def __init__(self):
            self.rows = []

        def save_result(self, session_id, trace_id, agent_id, result, status="ok"):
            self.rows.append(
                {
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "agent_id": agent_id,
                    "result": result,
                    "status": status,
                }
            )

        def get_results(self, session_id):
            return [r for r in self.rows if r["session_id"] == session_id]

    class FakeSessionManager:
        def __init__(self):
            self.store = FakeStore()

    class FakeVectorStore:
        async def add(self, **kwargs):
            return "mem-1"

    class FakeKnowledgeBase:
        async def add(self, **kwargs):
            return "kb-1"

    class FakeLogger:
        def info(self, msg):
            pass

        def warning(self, msg):
            pass

    harness = BioWorkflowHarness(
        session_manager=FakeSessionManager(),
        logger=FakeLogger(),
        vector_store=FakeVectorStore(),
        knowledge_base=FakeKnowledgeBase(),
    )

    calls = []

    class StubOrchestrator:
        async def run_single_agent(
            self,
            user_input,
            agent_id,
            session_id=None,
            trace_id=None,
            runtime_context=None,
        ):
            calls.append(agent_id)
            return '{"status":"ok"}'

    stage_specs = [
        HarnessStageSpec(name="planning", agent_id="bio_planner_agent", prompt="plan"),
        HarnessStageSpec(
            name="codegen",
            agent_id="bio_code_agent",
            prompt="codegen",
            depends_on=["planning"],
        ),
    ]
    resumed = [
        HarnessStageResult(
            stage="planning",
            agent_id="bio_planner_agent",
            status="ok",
            elapsed_ms=100,
            trace_id="old-trace-1",
            error=None,
            output='{"status":"ok"}',
        )
    ]

    result = await harness.run(
        orchestrator=StubOrchestrator(),
        session_id="sess-resume",
        trace_id="trace-resume",
        goal="resume",
        dataset="test",
        stage_specs=stage_specs,
        continue_on_error=True,
        resume_stage_results=resumed,
    )

    assert "bio_planner_agent" not in calls
    assert "bio_code_agent" in calls
    assert result["total_stages"] == 2


def test_stage_specs_from_plan_preserves_depends_on_and_qc_gate():
    from api.main import _stage_specs_from_plan
    from core.bio_harness import HarnessStageSpec

    plan_spec = WorkflowPlanSpec(
        workflow_family="rna-seq",
        stages=[
            WorkflowStageSpec(
                id="1",
                name="planning",
                kind="analysis",
                depends_on=[],
                agent_id="bio_planner_agent",
            ),
            WorkflowStageSpec(
                id="2",
                name="codegen",
                kind="codegen",
                depends_on=["planning"],
                agent_id="bio_code_agent",
            ),
            WorkflowStageSpec(
                id="3",
                name="qc",
                kind="qc",
                depends_on=["planning", "codegen"],
                agent_id="bio_qc_agent",
                qc_gate=True,
            ),
            WorkflowStageSpec(
                id="4",
                name="report",
                kind="report",
                depends_on=["qc"],
                agent_id="bio_report_agent",
            ),
        ],
    )

    specs = _stage_specs_from_plan(plan_spec, timeout_seconds=120)

    assert [s.name for s in specs] == ["planning", "codegen", "qc", "report"]
    assert specs[0].depends_on == []
    assert specs[1].depends_on == ["planning"]
    assert specs[2].depends_on == ["planning", "codegen"]
    assert specs[2].qc_gate is True, "qc stage should have qc_gate=True"
    assert specs[3].depends_on == ["qc"]


def test_evolution_approval_approve_stores_to_knowledge_base(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "evolution_router_mod",
        "/Users/gaoyangwei/Downloads/Dev1/api/routers/evolution_router.py",
    )
    er_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(er_mod)

    tmp_db = tmp_path / "evolution.db"

    original_kb = er_mod._kb_inject

    class FakeKB:
        def __init__(self):
            self.calls = []

        async def add(self, **kwargs):
            self.calls.append(kwargs)

    fake_kb = FakeKB()
    er_mod._kb_inject = fake_kb

    import sqlite3

    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS evolution_approvals ("
        "request_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
        "changes TEXT NOT NULL DEFAULT '{}', reason TEXT NOT NULL DEFAULT '', "
        "status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, "
        "reviewed_at TEXT, reviewer TEXT, comment TEXT)"
    )
    conn.execute(
        "INSERT OR REPLACE INTO evolution_approvals "
        "(request_id, agent_id, changes, reason, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "req_test_approve",
            "bio_evolution_agent",
            '{"kind":"workflow_retrospective","scope_id":"scope-test",'
            '"provider_id":"deepseek","goal":"test goal",'
            '"dataset":"test-dataset","summary":"test summary",'
            '"workflow_trace_id":"trace-123","session_id":"sess-abc"}',
            "test reason",
            "pending",
            "2025-01-01T00:00:00",
        ),
    )
    conn.commit()
    conn.close()

    original_store = er_mod._store
    try:
        er_mod._store = er_mod.EvolutionStore(db_path=tmp_path / "evolution.db")

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            er_mod.approve_evolution("req_test_approve", comment="looks good")
        )

        assert result["success"] is True
        assert result["status"] == "approved"
        assert len(fake_kb.calls) == 1
        call = fake_kb.calls[0]
        assert call["topic"] == "planning"
        assert "test summary" in call["text"]
        assert call["metadata"]["kind"] == "workflow_retrospective_approved"
        assert call["metadata"]["workflow_trace_id"] == "trace-123"
    finally:
        er_mod._store = original_store
        er_mod._kb_inject = original_kb


def test_bio_workflow_cache_key_deterministic():
    from api.main import _bio_workflow_cache_key
    import hashlib

    key1 = _bio_workflow_cache_key("analyze rna", "demo", "scope-1", "deepseek")
    key2 = _bio_workflow_cache_key("analyze rna", "demo", "scope-1", "deepseek")
    key3 = _bio_workflow_cache_key("analyze rna", "demo", "scope-1", "anthropic")

    assert key1 == key2, "same inputs should produce same cache key"
    assert key1 != key3, "different provider should produce different cache key"
    assert len(key1) == 64  # SHA256 hex


def test_bio_workflow_cache_set_and_get():
    import time
    from api.main import (
        _bio_workflow_cache_key,
        _get_cached_bio_workflow_result,
        _set_cached_bio_workflow_result,
        state,
    )

    cache_key = _bio_workflow_cache_key(
        "test-goal", "test-dataset", "test-scope", "test-provider"
    )

    initial = _get_cached_bio_workflow_result(cache_key)
    assert initial is None, "cache should be empty initially"

    fake_result = {
        "success": True,
        "status": "success",
        "total_stages": 5,
        "failed_stages": 0,
    }
    _set_cached_bio_workflow_result(cache_key, fake_result)

    retrieved = _get_cached_bio_workflow_result(cache_key)
    assert retrieved is not None
    assert retrieved["success"] is True
    assert retrieved["total_stages"] == 5

    state._bio_workflow_cache.clear()
