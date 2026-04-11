# api/main.py
"""
FastAPI 后端 - Multi-Agent 系统 REST API

启动方式:
    python -m uvicorn api.main:app --reload --port 8000
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from sse_starlette import EventSourceResponse

from api.routers import (
    skill_router,
    agent_router,
    soul_router,
    evolution_router,
    memory_router,
    channels_router,
)
from api.auth import router as auth_router
from api.ws.events import (
    websocket_endpoint,
    publish_bio_stage_pending,
    publish_bio_stage_running,
    publish_bio_stage_done,
    publish_bio_workflow_start,
    publish_bio_workflow_done,
)
from api.models.bio_workflow import (
    WorkflowIntentSpec,
    WorkflowPlanSpec,
    WorkflowStageSpec,
    SystemInferenceSpec,
)
from utils.feature_logs import setup_feature_loggers, get_feature_logger
from core.bio_harness import HarnessStageSpec, BioWorkflowHarness

LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logging():
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"agens_{today}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info(f"📝 日志文件: {log_file.absolute()}")
    feature_loggers = setup_feature_loggers(LOG_DIR)
    for feature in feature_loggers:
        logging.info(f"🧩 功能日志: {feature} -> {(LOG_DIR / 'features').absolute()}")
    return log_file


logger = logging.getLogger(__name__)


def _resolve_feature_from_path(path: str) -> str:
    p = (path or "").strip("/")
    if not p:
        return "system"
    first = p.split("/")[0]
    if first == "api" and len(p.split("/")) > 1:
        first = p.split("/")[1]

    mapping = {
        "auth": "auth",
        "chat": "chat",
        "sessions": "sessions",
        "providers": "providers",
        "agents": "agents",
        "skills": "skills",
        "memory": "memory",
        "evolution": "evolution",
        "hooks": "hooks",
        "traces": "traces",
        "ws": "ws",
    }
    return mapping.get(first, "system")


# ═══════════════════════════════════════════════════════════════════
# Pydantic 模型
# ═══════════════════════════════════════════════════════════════════


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    use_collaboration: bool = False
    memory_scope: Optional[str] = "session"  # session | global


class ChatSummarizeRequest(BaseModel):
    session_id: str
    auto_trigger: bool = False


class ResearchRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    provider_id: Optional[str] = None


def _extract_research_sources(raw_text: str) -> List[str]:
    if not raw_text:
        return []

    sources: List[str] = []
    # URLs
    for m in re.findall(r"https?://[^\s)\]}>\"']+", raw_text):
        if m not in sources:
            sources.append(m)

    # DOI / arXiv / PMID style snippets
    patterns = [
        r"doi:\s*10\.\d{4,9}/[-._;()/:A-Z0-9]+",
        r"arxiv:\s*\d{4}\.\d{4,5}(?:v\d+)?",
        r"pmid:\s*\d+",
    ]
    for p in patterns:
        for m in re.findall(p, raw_text, flags=re.IGNORECASE):
            s = m.strip()
            if s and s not in sources:
                sources.append(s)

    return sources[:20]


def _extract_research_knowledge(raw_text: str) -> List[str]:
    if not raw_text:
        return []

    points: List[str] = []
    for line in raw_text.splitlines():
        t = line.strip().lstrip("-•0123456789. ")
        if len(t) < 20:
            continue
        if any(
            k in t.lower()
            for k in [
                "found",
                "evidence",
                "result",
                "conclude",
                "发现",
                "证据",
                "结论",
                "提示",
            ]
        ):
            points.append(t)

    if not points:
        # fallback: keep first informative lines
        for line in raw_text.splitlines():
            t = line.strip().lstrip("-•0123456789. ")
            if len(t) >= 30:
                points.append(t)
            if len(points) >= 12:
                break

    dedup: List[str] = []
    for p in points:
        if p not in dedup:
            dedup.append(p)
    return dedup[:20]


class ChatResponse(BaseModel):
    response: str
    session_id: str
    provider: str


class BioWorkflowRequest(BaseModel):
    goal: str
    dataset: Optional[str] = None
    session_id: Optional[str] = None
    scope_id: Optional[str] = None
    provider_id: Optional[str] = None
    continue_on_error: bool = True
    stage_timeout_seconds: int = 120
    intent: Optional[WorkflowIntentSpec] = None
    plan: Optional[WorkflowPlanSpec] = None
    user_input_payload: Optional[Dict[str, Any]] = None
    resume_from_trace_id: Optional[str] = None


class WorkflowIntentConfirmRequest(BaseModel):
    goal: str
    dataset: Optional[str] = None
    intent: Optional[WorkflowIntentSpec] = None


class WorkflowPlanGenerateRequest(BaseModel):
    goal: Optional[str] = None
    dataset: Optional[str] = None
    intent: WorkflowIntentSpec


class SessionInfo(BaseModel):
    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    message_count: int


class ProviderInfo(BaseModel):
    id: str
    name: str
    model: str
    active: bool


class SkillInfo(BaseModel):
    skill_id: str
    name: str
    description: str
    version: str
    tags: List[str]
    enabled: bool


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    providers_available: int
    skills_count: int
    memory_count: int


# ═══════════════════════════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════════════════════════


class AgentSystemState:
    def __init__(self):
        self._initialized = False
        self._initializing = False

        # Lazy imports - only load when needed
        self._bus = None
        self._orchestrator = None
        self._provider_registry = None
        self._skill_registry = None
        self._hook_registry = None
        self._session_manager = None
        self._vector_store = None
        self._context_compressor = None
        self._knowledge_base = None
        self._approval_queue = None
        self._skill_installer = None
        self._auto_installer = None
        self._auto_installer_task = None
        self._bio_workflow_cache = {}
        self._all_agents = []  # 存储所有 Agent

    @property
    def all_agents(self):
        return self._all_agents

    @property
    def bus(self):
        return self._bus

    @property
    def orchestrator(self):
        return self._orchestrator

    @property
    def provider_registry(self):
        return self._get_provider_registry()

    @property
    def skill_registry(self):
        return self._get_skill_registry()

    @property
    def hook_registry(self):
        return self._get_hook_registry()

    @property
    def session_manager(self):
        return self._get_session_manager()

    @property
    def vector_store(self):
        return self._get_vector_store()

    @property
    def knowledge_base(self):
        return self._get_knowledge_base()

    @property
    def approval_queue(self):
        return self._get_approval_queue()

    @property
    def auto_installer(self):
        return self._get_auto_installer()

    def _get_provider_registry(self):
        if self._provider_registry is None:
            from providers.provider_registry import ProviderRegistry

            self._provider_registry = ProviderRegistry()
        return self._provider_registry

    def _get_skill_registry(self):
        if self._skill_registry is None:
            from core.skill_registry import SkillRegistry

            self._skill_registry = SkillRegistry()
        return self._skill_registry

    def _get_hook_registry(self):
        if self._hook_registry is None:
            from core.hooks import (
                HookRegistry,
                LoggingHook,
                RateLimitHook,
                ApprovalHook,
            )
            from core.integration_hooks import SafetyGuardHook, MLflowHook

            self._hook_registry = HookRegistry()
            self._hook_registry.register(LoggingHook())
            self._hook_registry.register(RateLimitHook(max_calls_per_minute=60))
            self._hook_registry.register(ApprovalHook())
            self._hook_registry.register(SafetyGuardHook())
            self._hook_registry.register(MLflowHook())
        return self._hook_registry

    def _get_session_manager(self):
        if self._session_manager is None:
            from session.session_store import SessionStore
            from session.session_manager import SessionManager
            from memory.vector_store import VectorStore
            from memory.context_compressor import ContextCompressor
            from memory.session_memory import SessionMemory

            session_store = SessionStore()
            self._session_manager = SessionManager(session_store)

            vector_store = VectorStore(db_path="./data/memory")
            context_compressor = ContextCompressor(
                provider=self._get_provider_registry().get(),
                max_messages=10,
                compress_threshold=20,
            )
            session_memory = SessionMemory(
                vector_store=vector_store,
                compressor=context_compressor,
                max_messages=10,
                compress_threshold=20,
            )
            self._session_manager.set_memory(session_memory)
            self._vector_store = vector_store

        return self._session_manager

    def _get_vector_store(self):
        if self._vector_store is None:
            from memory.vector_store import VectorStore

            self._vector_store = VectorStore(db_path="./data/memory")
        return self._vector_store

    def _get_knowledge_base(self):
        if self._knowledge_base is None:
            from knowledge.knowledge_base import KnowledgeBase

            self._knowledge_base = KnowledgeBase(db_path="./data/knowledge")
        return self._knowledge_base

    def _get_approval_queue(self):
        if self._approval_queue is None:
            from evolution.approval_queue import ApprovalQueue

            self._approval_queue = ApprovalQueue()
        return self._approval_queue

    def _get_skill_installer(self):
        if self._skill_installer is None:
            from installer.skill_installer import SkillInstaller

            self._skill_installer = SkillInstaller(registry=self._get_skill_registry())
        return self._skill_installer

    def _get_auto_installer(self):
        if self._auto_installer is None:
            from evolution.auto_installer import AutoInstaller

            self._auto_installer = AutoInstaller(
                registry=self._get_skill_registry(),
                installer=self._get_skill_installer(),
                queue=self._get_approval_queue(),
                provider_registry=self._get_provider_registry(),
            )
        return self._auto_installer

    def _get_orchestrator(self):
        if self._orchestrator is None:
            logger.info("🚀 [_get_orchestrator] 创建新 Orchestrator 实例")
            from core.orchestrator import Orchestrator

            self._orchestrator = Orchestrator(
                bus=self._bus or self._get_bus(),
                provider_registry=self._get_provider_registry(),
                session_manager=self._get_session_manager(),
                context_compressor=self._get_session_manager()._memory.compressor
                if self._get_session_manager()._memory
                else None,
            )
        return self._orchestrator

    def _get_bus(self):
        if self._bus is None:
            from bus.message_bus import MessageBus

            self._bus = MessageBus()
        return self._bus

    async def _init_agents(self):
        """初始化并注册所有工作 Agent"""
        if self._all_agents:
            return  # 已初始化

        bus = self._get_bus()

        # 创建 Orchestrator
        orchestrator = self._get_orchestrator()
        self._all_agents.append(orchestrator)

        # Agent 配置
        AGENT_CLASSES = {
            "research_agent": "agents.research_agent.research_agent.ResearchAgent",
            "bio_planner_agent": "agents.bio_planner_agent.bio_planner_agent.BioPlannerAgent",
            "bio_code_agent": "agents.bio_code_agent.bio_code_agent.BioCodeAgent",
            "bio_qc_agent": "agents.bio_qc_agent.bio_qc_agent.BioQCAgent",
            "bio_report_agent": "agents.bio_report_agent.bio_report_agent.BioReportAgent",
            "bio_evolution_agent": "agents.bio_evolution_agent.bio_evolution_agent.BioEvolutionAgent",
        }

        import importlib
        from core.soul_parser import SoulParser

        soul_parser = SoulParser()

        for agent_id, class_path in AGENT_CLASSES.items():
            try:
                module_path, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                AgentClass = getattr(module, class_name)

                agent = AgentClass(
                    bus=bus,
                    provider_registry=self._get_provider_registry(),
                    registry=self._get_skill_registry(),
                    knowledge=self._get_knowledge_base(),
                    auto_installer=self._get_auto_installer(),
                    memory_store=self._get_vector_store(),
                )

                soul_doc = soul_parser.parse_file(agent_id)
                if soul_doc:
                    soul_meta = soul_doc.meta
                    agent.description = soul_meta.role or agent.description
                    if soul_meta.skills:
                        agent.skills = soul_meta.skills
                    agent.config.setdefault("llm", {})
                    agent.config["llm"].update(
                        {
                            "model": soul_meta.model
                            or agent.config["llm"].get("model", ""),
                            "max_tokens": soul_meta.max_tokens,
                            "temperature": soul_meta.temperature,
                            "system_prompt": soul_meta.system_prompt
                            or f"你是 {soul_meta.name or agent_id}，当前角色是{soul_meta.role or agent.description}。",
                        }
                    )
                    agent.config["name"] = soul_meta.name or agent_id
                    agent.config["role"] = soul_meta.role or agent.description
                    agent.config["_soul_body"] = soul_doc.body

                agent.set_hook_registry(self._hook_registry)

                self._all_agents.append(agent)
                logger.info(f"✅ Agent [{agent_id}] 已创建")
            except Exception as e:
                logger.error(f"创建 Agent [{agent_id}] 失败: {e}")

        # 启动所有 Agent
        await self._start_agents()

    async def _start_agents(self):
        """启动所有 Agent"""
        for agent in self._all_agents:
            try:
                await agent.start()
            except Exception as e:
                logger.error(f"启动 Agent {agent.agent_id} 失败: {e}")

    async def initialize_async(self):
        if self._initialized or self._initializing:
            logger.info("initialize_async: 已初始化或正在初始化，跳过")
            return
        self._initializing = True
        logger.info("🚀 [initialize_async] 开始初始化...")
        try:
            # 触发所有属性的初始化
            logger.info("🚀 [initialize_async] 初始化 provider_registry...")
            _ = self.provider_registry
            logger.info("🚀 [initialize_async] 初始化 skill_registry...")
            _ = self.skill_registry
            logger.info("🚀 [initialize_async] 初始化 hook_registry...")
            _ = self.hook_registry
            logger.info("🚀 [initialize_async] 初始化 session_manager...")
            _ = self.session_manager
            logger.info("🚀 [initialize_async] 初始化 vector_store...")
            _ = self.vector_store
            logger.info("🚀 [initialize_async] 初始化 auto_installer...")
            _ = self.auto_installer
            kb = self._knowledge_base
            if kb:
                logger.info("🚀 [initialize_async] 初始化 knowledge_base...")
                await kb.init()
            logger.info("🚀 [initialize_async] 初始化 agents...")
            await self._init_agents()
            if self._auto_installer_task is None or self._auto_installer_task.done():
                self._auto_installer_task = asyncio.create_task(
                    self.auto_installer.start_watcher(interval=15)
                )
            self._initialized = True
            logger.info("✅ Multi-Agent 系统初始化完成")
        except Exception as e:
            logger.error(f"初始化错误: {e}", exc_info=True)
        finally:
            self._initializing = False


state = AgentSystemState()


def _default_dynamic_stage_templates(timeout_seconds: int) -> List[WorkflowStageSpec]:
    return [
        WorkflowStageSpec(
            id="planning",
            name="planning",
            kind="planning",
            agent_id="bio_planner_agent",
            prompt_template="请根据目标与数据集输出阶段化执行计划（输入/输出/风险/回滚）。\n目标: {goal}\n数据集: {dataset}",
            timeout_seconds=timeout_seconds,
            critical=True,
            knowledge_topic="planning",
            outputs=["plan"],
        ),
        WorkflowStageSpec(
            id="codegen",
            name="codegen",
            kind="codegen",
            agent_id="bio_code_agent",
            depends_on=["planning"],
            prompt_template="基于规划结果生成可执行脚本模板与命令清单。\n目标: {goal}\n数据集: {dataset}\n规划摘要: {prev}",
            timeout_seconds=timeout_seconds,
            knowledge_topic="codegen",
            outputs=["commands", "scripts"],
        ),
        WorkflowStageSpec(
            id="qc",
            name="qc",
            kind="qc",
            agent_id="bio_qc_agent",
            depends_on=["planning", "codegen"],
            prompt_template="基于当前方案给出 QC 检查项、阈值、失败处理建议。\n目标: {goal}\n数据集: {dataset}\n已有结果: {prev}",
            timeout_seconds=timeout_seconds,
            knowledge_topic="qc",
            qc_gate=True,
            outputs=["qc_report"],
        ),
        WorkflowStageSpec(
            id="report",
            name="report",
            kind="report",
            agent_id="bio_report_agent",
            depends_on=["planning", "codegen", "qc"],
            prompt_template="汇总当前阶段结果，输出结构化报告。\n目标: {goal}\n数据集: {dataset}\n阶段结果: {prev}",
            timeout_seconds=timeout_seconds,
            knowledge_topic="report",
            outputs=["report"],
        ),
        WorkflowStageSpec(
            id="evolution",
            name="evolution",
            kind="evolution",
            agent_id="bio_evolution_agent",
            depends_on=["planning", "codegen", "qc"],
            prompt_template="复盘本次工作流，输出下一轮优化策略与能力补齐清单。\n目标: {goal}\n数据集: {dataset}\n阶段结果: {prev}",
            timeout_seconds=timeout_seconds,
            knowledge_topic="evolution",
            outputs=["retrospective"],
        ),
    ]


def _normalize_workflow_intent(
    goal: str,
    dataset: Optional[str],
    intent: Optional[WorkflowIntentSpec],
    user_input_payload: Optional[Dict[str, Any]] = None,
) -> WorkflowIntentSpec:
    if intent:
        normalized = (
            intent.model_copy(deep=True)
            if hasattr(intent, "model_copy")
            else intent.copy(deep=True)
        )
    else:
        normalized = WorkflowIntentSpec(goal=goal)
    normalized.goal = normalized.goal or goal
    normalized.dataset = normalized.dataset or dataset
    if not normalized.request_id:
        normalized.request_id = str(uuid.uuid4())

    inferred_assay = normalized.assay_type
    confidence = 0.6 if normalized.assay_type != "other" else 0.3
    risks: List[str] = []
    if not normalized.dataset and not normalized.input_assets:
        risks.append("missing_input_assets")
    if not normalized.reference_bundle:
        risks.append("missing_reference_bundle")
    if not normalized.expected_outputs:
        risks.append("missing_expected_outputs")

    fields = list(normalized.fields_requiring_confirmation)
    for field_name, missing in [
        ("assay_type", normalized.assay_type == "other"),
        ("reference_bundle", normalized.reference_bundle is None),
        ("expected_outputs", len(normalized.expected_outputs) == 0),
    ]:
        if missing and field_name not in fields:
            fields.append(field_name)

    normalized.fields_requiring_confirmation = fields
    normalized.system_inference = SystemInferenceSpec(
        inferred_assay_type=inferred_assay,
        inferred_workflow_family=f"bio::{inferred_assay or 'generic'}",
        inferred_risks=risks,
        confidence=confidence,
    )

    if user_input_payload:
        answer = user_input_payload.get("user_answer")
        provided_fields = user_input_payload.get("provided_fields") or []
        if answer:
            normalized.analysis_type = (
                f"{normalized.analysis_type or ''}\nuser_answer:{answer}".strip()
            )
        if isinstance(provided_fields, list):
            remove_set = set(str(x) for x in provided_fields)
            normalized.fields_requiring_confirmation = [
                f
                for f in normalized.fields_requiring_confirmation
                if f not in remove_set
            ]
        if len(normalized.fields_requiring_confirmation) == 0:
            normalized.user_confirmed = True

    return normalized


def _workflow_family_from_intent(intent: WorkflowIntentSpec) -> str:
    assay = (intent.assay_type or "other").lower()
    mapping = {
        "rna_seq": "rna-seq",
        "scrna_seq": "single-cell-rna",
        "wgs": "wgs-variant",
        "wes": "wes-variant",
        "metagenomics": "metagenomics",
        "atac_seq": "atac-seq",
        "chip_seq": "chip-seq",
        "assembly": "assembly",
    }
    return mapping.get(assay, "bioinformatics-mvp")


def _assay_stage_profile(assay_type: str) -> Dict[str, Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Dict[str, Any]]] = {
        "rna_seq": {
            "codegen": {
                "focus": "prepare trimming, alignment-or-pseudoalignment, quantification, and DEG-ready matrix generation",
                "outputs": ["count_matrix", "commands", "scripts"],
            },
            "qc": {
                "focus": "review read quality, alignment rate, assignment rate, clustering, and batch effects",
                "outputs": ["qc_report", "sample_diagnostics"],
            },
            "report": {
                "focus": "summarize expression results, DEG highlights, and reproducibility metadata",
                "outputs": ["report", "de_summary"],
            },
            "evolution": {
                "focus": "capture template, parameter, and annotation improvements for RNA-seq runs",
                "outputs": ["retrospective", "template_updates"],
            },
        },
        "scrna_seq": {
            "codegen": {
                "focus": "prepare cell calling, filtering, normalization, dimensionality reduction, clustering, and marker discovery",
                "outputs": ["filtered_matrix", "cluster_labels", "commands"],
            },
            "qc": {
                "focus": "review doublets, mitochondrial fraction, cell filtering thresholds, and integration quality",
                "outputs": ["qc_report", "cell_filtering_metrics"],
            },
            "report": {
                "focus": "summarize cell populations, marker genes, and analysis caveats",
                "outputs": ["report", "marker_summary"],
            },
            "evolution": {
                "focus": "capture improvements for cell filtering thresholds and integration strategy",
                "outputs": ["retrospective", "threshold_updates"],
            },
        },
        "wgs": {
            "codegen": {
                "focus": "prepare alignment, duplicate handling, recalibration, variant calling, filtering, and annotation",
                "outputs": ["aligned_bam", "vcf", "commands"],
            },
            "qc": {
                "focus": "review coverage, contamination, duplication, callset quality, and reference concordance",
                "outputs": ["qc_report", "coverage_metrics"],
            },
            "report": {
                "focus": "summarize variant findings, annotation impact, and sequencing quality",
                "outputs": ["report", "variant_summary"],
            },
            "evolution": {
                "focus": "capture improvements for calling parameters, filtering, and annotation sources",
                "outputs": ["retrospective", "calling_updates"],
            },
        },
        "wes": {
            "codegen": {
                "focus": "prepare target-aware alignment, coverage assessment, variant calling, filtering, and annotation",
                "outputs": ["coverage_metrics", "vcf", "commands"],
            },
            "qc": {
                "focus": "review on-target rate, callable exome fraction, duplication, and target capture quality",
                "outputs": ["qc_report", "target_metrics"],
            },
            "report": {
                "focus": "summarize exon-targeted variant findings and panel limitations",
                "outputs": ["report", "variant_summary"],
            },
            "evolution": {
                "focus": "capture improvements for panel-specific thresholds and annotation policy",
                "outputs": ["retrospective", "panel_updates"],
            },
        },
        "metagenomics": {
            "codegen": {
                "focus": "prepare host depletion, taxonomic profiling, functional annotation, and abundance summarization",
                "outputs": ["taxonomic_profile", "functional_profile", "commands"],
            },
            "qc": {
                "focus": "review host contamination, classifier confidence, read complexity, and database suitability",
                "outputs": ["qc_report", "classification_metrics"],
            },
            "report": {
                "focus": "summarize dominant taxa, functional signatures, and contamination caveats",
                "outputs": ["report", "abundance_summary"],
            },
            "evolution": {
                "focus": "capture improvements for database choice, host depletion, and profiling thresholds",
                "outputs": ["retrospective", "database_updates"],
            },
        },
        "atac_seq": {
            "codegen": {
                "focus": "prepare alignment, peak calling, accessibility quantification, and differential accessibility analysis",
                "outputs": ["peak_set", "accessibility_matrix", "commands"],
            },
            "qc": {
                "focus": "review TSS enrichment, FRiP, fragment distribution, and replicate concordance",
                "outputs": ["qc_report", "peak_qc"],
            },
            "report": {
                "focus": "summarize accessibility patterns, peak quality, and biological interpretation",
                "outputs": ["report", "peak_summary"],
            },
            "evolution": {
                "focus": "capture improvements for peak calling thresholds and accessibility comparison logic",
                "outputs": ["retrospective", "peak_updates"],
            },
        },
        "chip_seq": {
            "codegen": {
                "focus": "prepare alignment, enrichment peak calling, motif/annotation, and differential binding analysis",
                "outputs": ["peak_set", "annotated_peaks", "commands"],
            },
            "qc": {
                "focus": "review enrichment quality, FRiP, cross-correlation, and control/input suitability",
                "outputs": ["qc_report", "enrichment_metrics"],
            },
            "report": {
                "focus": "summarize binding/enrichment findings, motif enrichment, and control caveats",
                "outputs": ["report", "binding_summary"],
            },
            "evolution": {
                "focus": "capture improvements for control strategy and peak calling thresholds",
                "outputs": ["retrospective", "peak_updates"],
            },
        },
        "assembly": {
            "codegen": {
                "focus": "prepare assembly, polishing, contamination screening, and annotation-ready outputs",
                "outputs": ["assembly_fasta", "polishing_outputs", "commands"],
            },
            "qc": {
                "focus": "review N50, completeness, contamination, polishing convergence, and platform error patterns",
                "outputs": ["qc_report", "assembly_metrics"],
            },
            "report": {
                "focus": "summarize assembly quality, completeness, contamination, and readiness for annotation",
                "outputs": ["report", "assembly_summary"],
            },
            "evolution": {
                "focus": "capture improvements for assembler choice, polishing passes, and contamination handling",
                "outputs": ["retrospective", "assembly_updates"],
            },
        },
    }
    return profiles.get(assay_type, {})


def _generate_workflow_plan(
    intent: WorkflowIntentSpec,
    timeout_seconds: int,
) -> WorkflowPlanSpec:
    workflow_family = _workflow_family_from_intent(intent)
    assay_profile = _assay_stage_profile(intent.assay_type)
    stages = _default_dynamic_stage_templates(timeout_seconds)
    for stage in stages:
        profile = assay_profile.get(stage.name)
        if not profile:
            continue
        stage.prompt_template = (
            f"{profile['focus']}。\n目标: {{goal}}\n数据集: {{dataset}}\n阶段结果: {{prev}}"
            if stage.name in {"qc", "report", "evolution"}
            else f"{profile['focus']}。\n目标: {{goal}}\n数据集: {{dataset}}\n规划摘要: {{prev}}"
            if stage.name == "codegen"
            else stage.prompt_template
        )
        stage.outputs = profile.get("outputs", stage.outputs)
    return WorkflowPlanSpec(
        plan_id=str(uuid.uuid4()),
        intent_id=intent.request_id,
        workflow_family=workflow_family,
        stages=stages,
    )


def _stage_specs_from_plan(
    plan: WorkflowPlanSpec,
    timeout_seconds: int,
) -> List[HarnessStageSpec]:
    stage_specs: List[HarnessStageSpec] = []
    for stage in plan.stages:
        stage_specs.append(
            HarnessStageSpec(
                name=stage.name,
                agent_id=stage.agent_id or "bio_planner_agent",
                prompt=stage.prompt_template
                or f"请完成阶段 {stage.name}。\\n目标: {{goal}}\\n数据集: {{dataset}}\\n已有结果: {{prev}}",
                timeout_seconds=stage.timeout_seconds or timeout_seconds,
                critical=stage.critical,
                depends_on=stage.depends_on,
                knowledge_topic=stage.knowledge_topic or stage.kind or stage.name,
                qc_gate=stage.qc_gate,
            )
        )
    return stage_specs


def _fallback_stage_specs(timeout_seconds: int) -> List[HarnessStageSpec]:
    return _stage_specs_from_plan(
        WorkflowPlanSpec(
            workflow_family="bioinformatics-mvp",
            stages=_default_dynamic_stage_templates(timeout_seconds),
        ),
        timeout_seconds=timeout_seconds,
    )


# ═══════════════════════════════════════════════════════════════════
# FastAPI 应用
# ═══════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logging.info("🚀 API 服务器启动")
    task = asyncio.ensure_future(state.initialize_async())
    try:
        await asyncio.wait_for(task, timeout=30.0)
    except asyncio.TimeoutError:
        logger.error("系统初始化超时")
    yield
    if state._auto_installer:
        state._auto_installer.stop_watcher()
    logging.info("👋 API 服务器关闭")


app = FastAPI(
    title="Multi-Agent System API",
    description="Multi-Agent 智能协作系统 REST API",
    version="0.02",
    lifespan=lifespan,
)


@app.post("/bio/intent/confirm")
@app.post("/api/bio/intent/confirm")
async def confirm_bio_intent(request: WorkflowIntentConfirmRequest):
    normalized = _normalize_workflow_intent(
        goal=request.goal,
        dataset=request.dataset,
        intent=request.intent,
    )
    return {
        "success": True,
        "intent": normalized.model_dump()
        if hasattr(normalized, "model_dump")
        else normalized.dict(),
        "requires_confirmation": len(normalized.fields_requiring_confirmation) > 0,
        "workflow_family": normalized.system_inference.inferred_workflow_family
        if normalized.system_inference
        else "bio::generic",
    }


@app.post("/bio/plan/generate")
@app.post("/api/bio/plan/generate")
async def generate_bio_workflow_plan(request: WorkflowPlanGenerateRequest):
    timeout_seconds = 120
    normalized = _normalize_workflow_intent(
        goal=request.goal or request.intent.goal,
        dataset=request.dataset or request.intent.dataset,
        intent=request.intent,
    )
    plan = _generate_workflow_plan(normalized, timeout_seconds=timeout_seconds)
    return {
        "success": True,
        "intent": normalized.model_dump()
        if hasattr(normalized, "model_dump")
        else normalized.dict(),
        "plan": plan.model_dump() if hasattr(plan, "model_dump") else plan.dict(),
    }


_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000",
)
_cors_list = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def feature_request_logger(request: Request, call_next):
    started = time.time()
    feature = _resolve_feature_from_path(request.url.path)
    flog = get_feature_logger(feature)
    request_id = str(uuid.uuid4())[:8]

    flog.info(
        f"[{request_id}] -> {request.method} {request.url.path} query={dict(request.query_params)}"
    )
    try:
        response = await call_next(request)
        elapsed_ms = int((time.time() - started) * 1000)
        flog.info(
            f"[{request_id}] <- status={response.status_code} elapsed_ms={elapsed_ms}"
        )
        return response
    except Exception as e:
        elapsed_ms = int((time.time() - started) * 1000)
        flog.error(
            f"[{request_id}] !! error={type(e).__name__}: {e} elapsed_ms={elapsed_ms}"
        )
        raise


app.include_router(skill_router)
app.include_router(agent_router)
app.include_router(soul_router)
app.include_router(evolution_router)
app.include_router(memory_router)
app.include_router(channels_router)

from api.routers.evolution_router import set_knowledge_base as set_evolution_kb
from api.routers.channels_router import set_runtime as set_channels_runtime

set_evolution_kb(state.knowledge_base)
set_channels_runtime(state._get_orchestrator, state._get_session_manager())

# API namespace aliases for frontend proxy (/api/*)
app.include_router(skill_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(soul_router, prefix="/api")
app.include_router(evolution_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(channels_router, prefix="/api")
app.include_router(auth_router)

from fastapi import WebSocket

app.add_api_websocket_route("/ws/events", websocket_endpoint)


# ═══════════════════════════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════════════════════════


@app.get("/health", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """系统健康检查"""
    try:
        pr = state.provider_registry
        vs = state.vector_store
        sr = state.skill_registry
        kb = state.knowledge_base
        provider_ok = await pr.health_check()
        memory_health = await vs.health_check()
        knowledge_health = await kb.health_check()
        overall_status = "healthy"
        if not provider_ok or memory_health.get("status") != "healthy":
            overall_status = "degraded"
        if knowledge_health.get("status") == "unhealthy":
            overall_status = "degraded"

        return HealthResponse(
            status=overall_status,
            provider=pr.active_id,
            model=pr.active_model,
            providers_available=len(pr.list_all()),
            skills_count=len(sr.list_all()),
            memory_count=await vs.count(),
        )
    except Exception as e:
        return HealthResponse(
            status="initializing",
            provider="unknown",
            model="unknown",
            providers_available=0,
            skills_count=0,
            memory_count=0,
        )


# ═══════════════════════════════════════════════════════════════════
# 聊天接口
# ═══════════════════════════════════════════════════════════════════


@app.post("/chat", response_model=ChatResponse)
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送消息并获取回复"""
    chat_log = get_feature_logger("chat")
    trace_id = str(uuid.uuid4())
    session_id = request.session_id or ""
    logging.info(
        f"🌐 [/chat] 请求开始 | trace_id={trace_id} | session_id={session_id[:8] if session_id else 'new'} | message_len={len(request.message)}"
    )
    chat_log.info(
        f"chat_start trace_id={trace_id} session_id={session_id or 'new'} message_len={len(request.message)}"
    )
    try:
        orch = state._get_orchestrator()
        if not orch:
            logging.error(f"🌐 [/chat] 系统未初始化")
            raise HTTPException(status_code=503, detail="System not initialized")

        logging.info(f"🌐 [/chat] 调用 orchestrator.run() | trace_id={trace_id}")
        chat_log.info(f"chat_orchestrator_run trace_id={trace_id}")
        result = await orch.run(
            user_input=request.message,
            session_id=request.session_id,
        )
        session_id = state.session_manager.current_session_id or ""
        logging.info(
            f"🌐 [/chat] ✅ 完成 | trace_id={trace_id} | session_id={session_id[:8]} | response_len={len(result) if result else 0}"
        )
        chat_log.info(
            f"chat_done trace_id={trace_id} session_id={session_id} response_len={len(result) if result else 0}"
        )
        return ChatResponse(
            response=result,
            session_id=session_id,
            provider=state.provider_registry.active_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(
            f"🌐 [/chat] ❌ 错误 | trace_id={trace_id} | {type(e).__name__}: {e}"
        )
        chat_log.error(f"chat_error trace_id={trace_id} error={type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/chat")
@app.post("/api/agents/{agent_id}/chat")
async def chat_with_agent(agent_id: str, request: ChatRequest):
    """
    直接与指定 Agent 聊天（不经过 Orchestrator 调度）

    用于独立 Agent 问答模式
    """
    trace_id = str(uuid.uuid4())
    logging.info(
        f"🌐 [agents/{agent_id}/chat] 请求开始 | trace_id={trace_id} | message='{request.message[:50]}...' "
    )
    try:
        orch = state._get_orchestrator()

        valid_agent_ids = [
            a.agent_id for a in state._all_agents if a.agent_id != "orchestrator"
        ]
        if agent_id not in valid_agent_ids:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

        result = await orch.run_single_agent(
            user_input=request.message,
            agent_id=agent_id,
            session_id=request.session_id,
            trace_id=trace_id,
        )

        logging.info(
            f"🌐 [agents/{agent_id}/chat] ✅ 完成 | trace_id={trace_id} | response_len={len(result) if result else 0}"
        )

        return {
            "success": True,
            "response": result,
            "session_id": orch._current_session_id,
            "agent_id": agent_id,
            "provider": state.provider_registry.active_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(
            f"🌐 [agents/{agent_id}/chat] ❌ 错误 | trace_id={trace_id} | {type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bio/workflow")
@app.post("/api/bio/workflow")
async def run_bio_workflow(request: BioWorkflowRequest, stream: bool = False):
    """生物信息学 MVP 工作流入口（阶段执行 + 结构化错误上报）"""
    trace_id = str(uuid.uuid4())
    chat_log = get_feature_logger("chat")
    try:
        orch = state._get_orchestrator()
        if not orch:
            raise HTTPException(status_code=503, detail="System not initialized")

        if stream:
            return EventSourceResponse(
                _bio_stream_generator(
                    request=request,
                    trace_id=trace_id,
                    chat_log=chat_log,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        prepared = await _prepare_bio_workflow_request(request, trace_id, chat_log)
        cache_key = _bio_workflow_cache_key(
            request.goal,
            prepared["dataset_desc"],
            prepared["scope_id"],
            prepared["target_provider_id"],
        )
        cached_result = _get_cached_bio_workflow_result(cache_key)
        if cached_result:
            return {
                **cached_result,
                "trace_id": trace_id,
                "session_id": prepared["session_id"],
                "cached": True,
            }

        harness = BioWorkflowHarness(
            session_manager=state.session_manager,
            logger=chat_log,
            vector_store=state.vector_store,
            knowledge_base=state.knowledge_base,
        )
        resume_stage_results = _resume_stage_results_from_trace(
            session_id=prepared["session_id"],
            resume_from_trace_id=request.resume_from_trace_id,
        )
        harness_result = await harness.run(
            orchestrator=prepared["orch"],
            session_id=prepared["session_id"],
            trace_id=trace_id,
            goal=request.goal,
            dataset=prepared["dataset_desc"],
            stage_specs=prepared["stage_specs"],
            continue_on_error=request.continue_on_error,
            scope_id=prepared["scope_id"],
            provider_id=prepared["target_provider_id"],
            resume_stage_results=resume_stage_results,
        )

        response = {
            "success": harness_result["success"],
            "status": harness_result["status"],
            "trace_id": trace_id,
            "session_id": prepared["session_id"],
            "workflow": prepared["plan"].workflow_family,
            "scope_id": prepared["scope_id"],
            "provider_id": prepared["target_provider_id"],
            "provider_fallback": prepared["target_provider_id"]
            != prepared["requested_provider_id"],
            "response": harness_result["response"],
            "stage_results": harness_result["stage_results"],
            "failed_stages": harness_result["failed_stages"],
            "total_stages": harness_result["total_stages"],
            "last_checkpoint": harness_result["last_checkpoint"],
            "execution_policy": harness_result["execution_policy"],
            "needs_user_input": harness_result.get("needs_user_input", False),
            "user_question": harness_result.get("user_question"),
            "required_fields": harness_result.get("required_fields", []),
            "harness": {
                "state_persistence": True,
                "execution_boundaries": {
                    "stage_timeout_seconds": prepared["timeout_seconds"],
                    "continue_on_error": request.continue_on_error,
                },
                "audit_traceability": True,
            },
            "intent": prepared["intent"].model_dump()
            if hasattr(prepared["intent"], "model_dump")
            else prepared["intent"].dict(),
            "plan": prepared["plan"].model_dump()
            if hasattr(prepared["plan"], "model_dump")
            else prepared["plan"].dict(),
            "cached": False,
        }
        if response["success"]:
            _set_cached_bio_workflow_result(
                cache_key,
                {
                    "success": response["success"],
                    "status": response["status"],
                    "workflow": response["workflow"],
                    "scope_id": response["scope_id"],
                    "provider_id": response["provider_id"],
                    "provider_fallback": response["provider_fallback"],
                    "response": response["response"],
                    "stage_results": response["stage_results"],
                    "failed_stages": response["failed_stages"],
                    "total_stages": response["total_stages"],
                    "last_checkpoint": response["last_checkpoint"],
                    "execution_policy": response["execution_policy"],
                    "harness": response["harness"],
                    "intent": response["intent"],
                    "plan": response["plan"],
                    "cached": False,
                },
            )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"🌐 [/bio/workflow] ❌ 错误 | trace_id={trace_id} | {type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


async def _prepare_bio_workflow_request(
    request: BioWorkflowRequest, trace_id: str, chat_log
):
    orch = state._get_orchestrator()
    if not orch:
        raise HTTPException(status_code=503, detail="System not initialized")

    if request.provider_id:
        try:
            _ = state.provider_registry.get(request.provider_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid provider_id: {e}")

    requested_provider_id = request.provider_id or state.provider_registry.active_id
    target_provider_id = requested_provider_id
    provider_healthy = await state.provider_registry.health_check(target_provider_id)
    if not provider_healthy:
        target_provider_id = await state.provider_registry.get_best_available(
            preferred_id=request.provider_id
        )
        chat_log.warning(
            f"bio_workflow_provider_fallback trace_id={trace_id} requested={requested_provider_id} fallback={target_provider_id}"
        )

    dataset_desc = request.dataset or "unspecified"
    scope_id = request.scope_id or f"bio::{dataset_desc}"
    session_id = request.session_id or state.session_manager.new_session(
        title=f"bio:{request.goal[:30]}"
    )
    timeout_seconds = max(10, min(request.stage_timeout_seconds, 600))
    normalized_intent = _normalize_workflow_intent(
        goal=request.goal,
        dataset=request.dataset,
        intent=request.intent,
        user_input_payload=request.user_input_payload,
    )
    dataset_desc = normalized_intent.dataset or dataset_desc
    if request.plan and request.plan.stages:
        workflow_plan = request.plan
    elif request.intent:
        workflow_plan = _generate_workflow_plan(
            normalized_intent,
            timeout_seconds=timeout_seconds,
        )
    else:
        workflow_plan = WorkflowPlanSpec(
            plan_id=str(uuid.uuid4()),
            intent_id=normalized_intent.request_id,
            workflow_family="bioinformatics-mvp",
            stages=_default_dynamic_stage_templates(timeout_seconds),
        )

    stage_specs = (
        _stage_specs_from_plan(workflow_plan, timeout_seconds)
        if workflow_plan.stages
        else _fallback_stage_specs(timeout_seconds)
    )

    return {
        "orch": orch,
        "requested_provider_id": requested_provider_id,
        "target_provider_id": target_provider_id,
        "dataset_desc": dataset_desc,
        "scope_id": scope_id,
        "session_id": session_id,
        "timeout_seconds": timeout_seconds,
        "stage_specs": stage_specs,
        "intent": normalized_intent,
        "plan": workflow_plan,
    }


def _bio_workflow_cache_key(
    goal: str,
    dataset: str,
    scope_id: str,
    provider_id: str,
) -> str:
    payload = f"{goal}|{dataset}|{scope_id}|{provider_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_cached_bio_workflow_result(cache_key: str) -> Optional[dict]:
    cached = state._bio_workflow_cache.get(cache_key)
    if not cached:
        return None
    if time.time() - cached["cached_at"] > 900:
        state._bio_workflow_cache.pop(cache_key, None)
        return None
    return cached["result"]


def _set_cached_bio_workflow_result(cache_key: str, result: dict) -> None:
    state._bio_workflow_cache[cache_key] = {
        "cached_at": time.time(),
        "result": result,
    }


def _estimate_context_pressure(session_id: str) -> Dict[str, Any]:
    """估算会话上下文占用率，供自动压缩策略使用。"""
    if not state.session_manager or not getattr(state.session_manager, "store", None):
        return {"total_tokens": 0, "window": 32000, "ratio": 0.0}
    total_tokens = state.session_manager.store.get_total_tokens(session_id)
    window = (
        state.provider_registry.context_window() if state.provider_registry else 32000
    )
    ratio = (total_tokens / max(window, 1)) if window > 0 else 0.0
    return {"total_tokens": total_tokens, "window": window, "ratio": ratio}


def _extract_xml_tag_values(text: str, tag: str) -> List[str]:
    if not text:
        return []
    pattern = rf"<{tag}>(.*?)</{tag}>"
    values = []
    for m in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
        value = (m.group(1) or "").strip()
        if value:
            values.append(value)
    return values


def _extract_xml_tag_value(text: str, tag: str) -> str:
    values = _extract_xml_tag_values(text, tag)
    return values[0] if values else ""


async def _summarize_session_context(session_id: str) -> Dict[str, Any]:
    """手动/自动触发会话上下文压缩，返回完成与待完成摘要。"""
    if not state.session_manager or not state.session_manager._memory:
        return {
            "summary": "Memory subsystem not enabled.",
            "completed": [],
            "pending": [],
            "compressed": False,
        }

    from core.message import ChatMessage

    raw = state.session_manager.store.get_messages(session_id)
    messages = [
        ChatMessage(
            role=str(m.get("role", "assistant")), content=str(m.get("content", ""))
        )
        for m in raw
    ]
    if not messages:
        return {
            "summary": "No messages to summarize.",
            "completed": [],
            "pending": [],
            "compressed": False,
        }

    compressed = await state.session_manager._memory.compressor.compress(messages)
    summary_text = ""
    if compressed and compressed[0].role == "system":
        summary_text = compressed[0].content

    # Prefer structured extraction from summary XML first
    completed: List[str] = _extract_xml_tag_values(summary_text, "decision")
    pending: List[str] = _extract_xml_tag_values(summary_text, "topic")
    abstract = _extract_xml_tag_value(summary_text, "abstract")

    # Fallback heuristics for non-XML summaries
    if not completed and not pending:
        for line in summary_text.splitlines():
            t = line.strip().lstrip("-• ")
            if not t:
                continue
            if any(k in t for k in ["决策", "decision", "已完成", "done"]):
                completed.append(t)
            if any(k in t for k in ["待处理", "pending", "topic", "TODO", "todo"]):
                pending.append(t)

    returned_summary = abstract or summary_text[:4000]

    # Persist compaction summary as system message for continuation
    state.session_manager.store.append_message(
        session_id,
        "system",
        f"[ContextCompaction]\n{summary_text[:4000]}",
    )

    return {
        "summary": returned_summary,
        "completed": completed[:20],
        "pending": pending[:20],
        "compressed": True,
    }


def _resume_stage_results_from_trace(
    session_id: str,
    resume_from_trace_id: Optional[str],
) -> List["HarnessStageResult"]:
    if not resume_from_trace_id:
        return []
    if not state.session_manager or not hasattr(state.session_manager, "store"):
        return []
    rows = state.session_manager.store.get_results_by_trace(resume_from_trace_id)
    resumed: List[HarnessStageResult] = []
    for row in rows:
        try:
            if row.get("session_id") != session_id:
                continue
            result_raw = row.get("result")
            if not result_raw:
                continue
            parsed = (
                result_raw if isinstance(result_raw, dict) else json.loads(result_raw)
            )
            if not isinstance(parsed, dict):
                continue
            if not parsed.get("stage") or not parsed.get("status"):
                continue
            resumed.append(
                HarnessStageResult(
                    stage=str(parsed.get("stage")),
                    agent_id=str(
                        parsed.get("agent_id", row.get("agent_id", "unknown"))
                    ),
                    status=str(parsed.get("status", "error")),
                    elapsed_ms=int(parsed.get("elapsed_ms", 0) or 0),
                    trace_id=str(parsed.get("trace_id", resume_from_trace_id)),
                    error=parsed.get("error"),
                    output=str(parsed.get("output", "") or ""),
                    provenance=parsed.get("provenance") or {},
                    needs_user_input=bool(parsed.get("needs_user_input", False)),
                    user_question=parsed.get("user_question"),
                    required_fields=parsed.get("required_fields") or [],
                )
            )
        except Exception:
            continue
    dedup: Dict[str, HarnessStageResult] = {}
    for item in resumed:
        dedup[item.stage] = item
    return list(dedup.values())


async def _bio_stream_generator(
    request: BioWorkflowRequest,
    trace_id: str,
    chat_log,
):
    """SSE generator for streaming bio workflow stage events."""
    event_queue = asyncio.Queue()

    async def emit_to_queue(payload: Any):
        await event_queue.put(payload)

    yield {
        "event": "bio_workflow_start",
        "data": json.dumps(
            {
                "session_id": request.session_id or "pending",
                "trace_id": trace_id,
                "goal": request.goal,
                "scope_id": request.scope_id
                or (f"bio::{request.dataset or 'unspecified'}"),
                "provider_id": request.provider_id or state.provider_registry.active_id,
            }
        ),
        "id": str(uuid.uuid4())[:8],
    }

    try:
        prepared = await _prepare_bio_workflow_request(request, trace_id, chat_log)
    except Exception as e:
        message = str(e.detail) if isinstance(e, HTTPException) else str(e)
        yield {
            "event": "error",
            "data": json.dumps({"message": message, "trace_id": trace_id}),
            "id": str(uuid.uuid4())[:8],
        }
        yield {
            "event": "bio_workflow_final",
            "data": json.dumps(
                {
                    "success": False,
                    "status": "partial_failure",
                    "trace_id": trace_id,
                    "session_id": request.session_id or "pending",
                    "scope_id": request.scope_id
                    or (f"bio::{request.dataset or 'unspecified'}"),
                    "provider_id": request.provider_id
                    or state.provider_registry.active_id,
                    "response": message,
                    "stage_results": [],
                    "failed_stages": 1,
                    "total_stages": 0,
                    "execution_policy": {},
                }
            ),
            "id": str(uuid.uuid4())[:8],
        }
        return

    cache_key = _bio_workflow_cache_key(
        request.goal,
        prepared["dataset_desc"],
        prepared["scope_id"],
        prepared["target_provider_id"],
    )
    cached_result = _get_cached_bio_workflow_result(cache_key)
    if cached_result:
        yield {
            "event": "bio_workflow_done",
            "data": json.dumps(
                {
                    "session_id": prepared["session_id"],
                    "trace_id": trace_id,
                    "success": cached_result["success"],
                    "status": cached_result["status"],
                    "total_stages": cached_result["total_stages"],
                    "failed_stages": cached_result["failed_stages"],
                    "cached": True,
                }
            ),
            "id": str(uuid.uuid4())[:8],
        }
        yield {
            "event": "bio_workflow_final",
            "data": json.dumps(
                {
                    **cached_result,
                    "trace_id": trace_id,
                    "session_id": prepared["session_id"],
                    "cached": True,
                }
            ),
            "id": str(uuid.uuid4())[:8],
        }
        return
    orch = prepared["orch"]
    session_id = prepared["session_id"]
    dataset = prepared["dataset_desc"]
    stage_specs = prepared["stage_specs"]
    scope_id = prepared["scope_id"]
    provider_id = prepared["target_provider_id"]
    stage_trace_ids = [
        f"{trace_id}-{idx}" for idx, _ in enumerate(stage_specs, start=1)
    ]
    subscribed_trace_ids = [trace_id, *stage_trace_ids]

    previous_emitters = []
    for agent in state._all_agents:
        previous_emitters.append(agent)
        if hasattr(agent, "register_trace_emitter"):
            for subscribed_trace_id in subscribed_trace_ids:
                agent.register_trace_emitter(subscribed_trace_id, emit_to_queue)

    for subscribed_trace_id in subscribed_trace_ids:
        orch.set_event_callback(subscribed_trace_id, emit_to_queue)

    harness = BioWorkflowHarness(
        session_manager=state.session_manager,
        logger=chat_log,
        event_emitter=emit_to_queue,
        vector_store=state.vector_store,
        knowledge_base=state.knowledge_base,
    )

    task = asyncio.create_task(
        harness.run(
            orchestrator=orch,
            session_id=session_id,
            trace_id=trace_id,
            goal=request.goal,
            dataset=dataset,
            stage_specs=stage_specs,
            continue_on_error=request.continue_on_error,
            scope_id=scope_id,
            provider_id=provider_id,
            resume_stage_results=_resume_stage_results_from_trace(
                session_id=session_id,
                resume_from_trace_id=request.resume_from_trace_id,
            ),
        )
    )

    HEARTBEAT_INTERVAL = 15
    last_heartbeat = time.time()

    while not task.done() or not event_queue.empty():
        try:
            remaining = HEARTBEAT_INTERVAL - (time.time() - last_heartbeat)
            if remaining <= 0:
                yield {
                    "event": "heartbeat",
                    "data": "keepalive",
                    "id": str(uuid.uuid4())[:8],
                }
                last_heartbeat = time.time()
            remaining = HEARTBEAT_INTERVAL

            payload = await asyncio.wait_for(event_queue.get(), timeout=remaining)
            if hasattr(payload, "to_dict"):
                payload_dict = payload.to_dict()
                event_type = payload_dict.get("type", "agent_event")
                yield {
                    "event": event_type,
                    "data": json.dumps(payload_dict),
                    "id": payload_dict.get("event_id") or str(uuid.uuid4())[:8],
                }
            else:
                event_type = payload.pop("event", "bio_stage")
                yield {
                    "event": event_type,
                    "data": json.dumps(payload),
                    "id": str(uuid.uuid4())[:8],
                }
        except asyncio.TimeoutError:
            yield {
                "event": "heartbeat",
                "data": "keepalive",
                "id": str(uuid.uuid4())[:8],
            }
            last_heartbeat = time.time()
            continue
        except Exception as e:
            yield {"event": "error", "data": str(e), "id": str(uuid.uuid4())[:8]}
            break

    try:
        result = await task
        if result["success"]:
            _set_cached_bio_workflow_result(
                cache_key,
                {
                    "success": result["success"],
                    "status": result["status"],
                    "workflow": "bioinformatics-mvp",
                    "intent": prepared["intent"].model_dump()
                    if hasattr(prepared["intent"], "model_dump")
                    else prepared["intent"].dict(),
                    "plan": prepared["plan"].model_dump()
                    if hasattr(prepared["plan"], "model_dump")
                    else prepared["plan"].dict(),
                    "scope_id": scope_id,
                    "provider_id": provider_id or state.provider_registry.active_id,
                    "provider_fallback": provider_id
                    != prepared["requested_provider_id"],
                    "response": result["response"],
                    "stage_results": result["stage_results"],
                    "failed_stages": result["failed_stages"],
                    "total_stages": result["total_stages"],
                    "execution_policy": result["execution_policy"],
                    "cached": False,
                },
            )
        yield {
            "event": "bio_workflow_final",
            "data": json.dumps(
                {
                    "success": result["success"],
                    "status": result["status"],
                    "workflow": prepared["plan"].workflow_family,
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "scope_id": scope_id,
                    "provider_id": provider_id or state.provider_registry.active_id,
                    "response": result["response"],
                    "stage_results": result["stage_results"],
                    "failed_stages": result["failed_stages"],
                    "total_stages": result["total_stages"],
                    "execution_policy": result["execution_policy"],
                    "needs_user_input": result.get("needs_user_input", False),
                    "user_question": result.get("user_question"),
                    "required_fields": result.get("required_fields", []),
                    "provider_fallback": provider_id
                    != prepared["requested_provider_id"],
                    "intent": prepared["intent"].model_dump()
                    if hasattr(prepared["intent"], "model_dump")
                    else prepared["intent"].dict(),
                    "plan": prepared["plan"].model_dump()
                    if hasattr(prepared["plan"], "model_dump")
                    else prepared["plan"].dict(),
                    "cached": False,
                }
            ),
            "id": str(uuid.uuid4())[:8],
        }
    finally:
        for agent in previous_emitters:
            if hasattr(agent, "clear_trace_emitter"):
                for subscribed_trace_id in subscribed_trace_ids:
                    agent.clear_trace_emitter(subscribed_trace_id, emit_to_queue)
        for subscribed_trace_id in subscribed_trace_ids:
            orch.clear_event_queue(subscribed_trace_id)


@app.post("/chat/stream")
@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, last_event_id: str = None):
    """
    SSE 流式事件端点 - 实时推送 Agent 执行事件

    可靠性特性:
    - 心跳事件（每 15 秒）避免代理断流
    - 支持 Last-Event-ID 断线续传
    """
    trace_id = str(uuid.uuid4())
    chat_log = get_feature_logger("chat")
    session_desc = request.session_id or "new"
    logger.info(
        f"🌐 [/chat/stream] 请求开始 | trace_id={trace_id} | session_id={session_desc[:8]} | message='{request.message[:50]}...'"
    )
    chat_log.info(
        f"chat_stream_start trace_id={trace_id} session_id={session_desc} message_len={len(request.message)}"
    )

    HEARTBEAT_INTERVAL = 15

    async def event_generator():
        try:
            orch = state._get_orchestrator()
            if not orch:
                logger.error(f"🌐 [/chat/stream:{trace_id}] 系统未初始化")
                yield {"event": "error", "data": "System not initialized"}
                return

            session_id = request.session_id
            if not session_id:
                session_id = state.session_manager.new_session(
                    title=request.message[:40]
                )
                logger.info(f"🌐 [/chat/stream:{trace_id}] 🆕 创建新会话: {session_id}")
                chat_log.info(
                    f"chat_stream_new_session trace_id={trace_id} session_id={session_id}"
                )
            else:
                logger.info(
                    f"🌐 [/chat/stream:{trace_id}] ▶️ 恢复会话: {session_id[:8]}"
                )
                chat_log.info(
                    f"chat_stream_resume_session trace_id={trace_id} session_id={session_id}"
                )

            # Auto compaction when context pressure is high
            pressure = _estimate_context_pressure(session_id)
            if pressure["ratio"] >= 0.70:
                compaction = await _summarize_session_context(session_id)
                yield {
                    "event": "context_compaction",
                    "data": json.dumps(
                        {
                            "event": "context_compaction",
                            "trace_id": trace_id,
                            "session_id": session_id,
                            "total_tokens": pressure["total_tokens"],
                            "window": pressure["window"],
                            "ratio": pressure["ratio"],
                            "summary": compaction.get("summary", ""),
                            "completed": compaction.get("completed", []),
                            "pending": compaction.get("pending", []),
                        },
                        ensure_ascii=False,
                    ),
                    "id": str(uuid.uuid4())[:8],
                }

            event_queue = asyncio.Queue()
            last_yielded_event_id = last_event_id or ""
            events_received = 0

            async def emit_to_queue(event):
                nonlocal events_received
                event_type = getattr(event, "type", None) or (
                    event.event_type.value
                    if hasattr(event, "event_type")
                    else "unknown"
                )
                event_id = getattr(event, "event_id", None) or str(uuid.uuid4())
                events_received += 1
                logger.info(
                    f"🌐 [SSE:{trace_id}] 📤 事件 [{events_received}] type={event_type} id={event_id[:8]}"
                )
                chat_log.info(
                    f"chat_stream_event trace_id={trace_id} event_type={event_type} event_id={event_id[:8]} idx={events_received}"
                )
                await event_queue.put((event_id, event))

            for agent in state._all_agents:
                if hasattr(agent, "register_trace_emitter"):
                    agent.register_trace_emitter(trace_id, emit_to_queue)

            orch.set_event_callback(trace_id, emit_to_queue)

            logger.info(f"🌐 [/chat/stream:{trace_id}] 🚀 启动 orchestrator.run()")

            task = asyncio.create_task(
                orch.run(
                    user_input=request.message,
                    session_id=session_id,
                    trace_id=trace_id,
                    memory_scope=request.memory_scope or "session",
                )
            )

            last_heartbeat = time.time()
            loop_count = 0
            while True:
                loop_count += 1
                try:
                    remaining = HEARTBEAT_INTERVAL - (time.time() - last_heartbeat)
                    if remaining <= 0:
                        logger.debug(f"🌐 [SSE:{trace_id}] ❤️ 心跳")
                        yield {
                            "event": "heartbeat",
                            "data": "keepalive",
                            "id": str(uuid.uuid4())[:8],
                        }
                        last_heartbeat = time.time()
                        remaining = HEARTBEAT_INTERVAL

                    logger.debug(f"🌐 [SSE:{trace_id}] ⏳ 等待事件 (loop={loop_count})")
                    event_id, event = await asyncio.wait_for(
                        event_queue.get(), timeout=remaining
                    )
                    event_queue.task_done()

                    if last_event_id and event_id <= last_event_id:
                        logger.info(
                            f"🌐 [SSE:{trace_id}] 🔁 跳过已发送: {event_id[:8]}"
                        )
                        continue

                    event_data = event.to_dict() if hasattr(event, "to_dict") else {}
                    event_type = event_data.get("event") or event_data.get(
                        "type", "message"
                    )

                    logger.info(
                        f"🌐 [SSE:{trace_id}] 📤 yield event={event_type} id={event_id[:8]}"
                    )
                    yield {
                        "event": event_type,
                        "data": json.dumps(event_data),
                        "id": event_id[:8] if len(event_id) > 8 else event_id,
                    }

                    last_yielded_event_id = event_id

                    if event_type in ("final_response", "task_failed", "task_timeout"):
                        logger.info(
                            f"🌐 [SSE:{trace_id}] 🛑 收到终止事件: {event_type}"
                        )
                        break

                except asyncio.TimeoutError:
                    logger.debug(f"🌐 [SSE:{trace_id}] ⏰ 超时等待")
                    yield {
                        "event": "heartbeat",
                        "data": "keepalive",
                        "id": str(uuid.uuid4())[:8],
                    }
                    last_heartbeat = time.time()
                    continue

            logger.info(f"🌐 [/chat/stream:{trace_id}] ⏳ 等待 orchestrator.run() 完成")
            result = await task
            response_len = len(result) if result else 0
            logger.info(
                f"🌐 [/chat/stream:{trace_id}] ✅ 完成 | response_len={response_len}"
            )
            if response_len == 0:
                chat_log.error(
                    f"chat_stream_no_response trace_id={trace_id} provider={state.provider_registry.active_id}"
                )
            else:
                chat_log.info(
                    f"chat_stream_done trace_id={trace_id} response_len={response_len} provider={state.provider_registry.active_id}"
                )
            yield {
                "event": "done",
                "data": f"Final response: {result[:500]}" if result else "No response",
                "id": str(uuid.uuid4())[:8],
            }

        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            logger.error(
                f"🌐 [/chat/stream:{trace_id}] ❌ 异常: {type(e).__name__}: {e}\n{tb}"
            )
            chat_log.error(
                f"chat_stream_error trace_id={trace_id} error={type(e).__name__}: {e} provider={state.provider_registry.active_id}"
            )
            yield {"event": "error", "data": str(e)}
        finally:
            for agent in state._all_agents:
                if hasattr(agent, "clear_trace_emitter"):
                    agent.clear_trace_emitter(trace_id, emit_to_queue)
            orch.clear_event_queue(trace_id)

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat/summarize")
@app.post("/api/chat/summarize")
async def summarize_chat_context(request: ChatSummarizeRequest):
    """手动触发会话上下文总结并返回 completed/pending。"""
    session = state.session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pressure = _estimate_context_pressure(request.session_id)
    if not request.auto_trigger and pressure["ratio"] < 0.20:
        return {
            "success": True,
            "session_id": request.session_id,
            "message": "Context usage is low; summary is optional.",
            "total_tokens": pressure["total_tokens"],
            "window": pressure["window"],
            "ratio": pressure["ratio"],
            "summary": "",
            "completed": [],
            "pending": [],
        }

    result = await _summarize_session_context(request.session_id)
    return {
        "success": True,
        "session_id": request.session_id,
        "total_tokens": pressure["total_tokens"],
        "window": pressure["window"],
        "ratio": pressure["ratio"],
        **result,
    }


@app.get("/chat/history/{session_id}")
@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """获取会话历史"""
    try:
        session = state.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        messages = state.session_manager.store.get_messages(session_id)
        return {**session, "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/research/run")
@app.post("/api/research/run")
async def run_research(request: ResearchRequest):
    """运行 research_agent 并由 bio_report_agent 进行结构化总结。"""
    orch = state._get_orchestrator()
    if not orch:
        raise HTTPException(status_code=500, detail="System not initialized")

    if request.provider_id:
        try:
            state.provider_registry.use(request.provider_id)
        except Exception:
            pass

    trace_id = str(uuid.uuid4())
    session_id = request.session_id

    raw = await orch.run_single_agent(
        user_input=request.query,
        agent_id="research_agent",
        session_id=session_id,
        trace_id=trace_id,
    )

    summary_prompt = (
        "请将以下 research 结果整理为结构化结论，输出包括："
        "1) 关键发现 2) 证据与来源 3) 风险与局限 4) 下一步建议。\n\n"
        f"Research Query: {request.query}\n\nRaw Findings:\n{raw}"
    )
    summarized = await orch.run_single_agent(
        user_input=summary_prompt,
        agent_id="bio_report_agent",
        session_id=session_id,
        trace_id=str(uuid.uuid4()),
    )

    return {
        "success": True,
        "session_id": session_id,
        "query": request.query,
        "research": raw,
        "summary": summarized,
    }


@app.post("/research/stream")
@app.post("/api/research/stream")
async def stream_research(request: ResearchRequest):
    """SSE 流式 research：输出中间过程（来源/知识点）与最终总结。"""
    trace_id = str(uuid.uuid4())

    async def event_generator():
        try:
            orch = state._get_orchestrator()
            if not orch:
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"event": "error", "message": "System not initialized"},
                        ensure_ascii=False,
                    ),
                }
                return

            if request.provider_id:
                try:
                    state.provider_registry.use(request.provider_id)
                except Exception:
                    pass

            session_id = request.session_id or state.session_manager.new_session(
                title=f"Research: {request.query[:40]}"
            )

            yield {
                "event": "research_start",
                "data": json.dumps(
                    {
                        "event": "research_start",
                        "trace_id": trace_id,
                        "session_id": session_id,
                        "query": request.query,
                    },
                    ensure_ascii=False,
                ),
                "id": str(uuid.uuid4())[:8],
            }

            yield {
                "event": "research_progress",
                "data": json.dumps(
                    {
                        "event": "research_progress",
                        "trace_id": trace_id,
                        "stage": "searching",
                        "message": "Research agent is searching sources...",
                    },
                    ensure_ascii=False,
                ),
                "id": str(uuid.uuid4())[:8],
            }

            raw = await orch.run_single_agent(
                user_input=request.query,
                agent_id="research_agent",
                session_id=session_id,
                trace_id=trace_id,
            )

            sources = _extract_research_sources(raw)
            for idx, src in enumerate(sources, start=1):
                yield {
                    "event": "research_source",
                    "data": json.dumps(
                        {
                            "event": "research_source",
                            "trace_id": trace_id,
                            "index": idx,
                            "source": src,
                        },
                        ensure_ascii=False,
                    ),
                    "id": str(uuid.uuid4())[:8],
                }

            knowledge_points = _extract_research_knowledge(raw)
            for idx, point in enumerate(knowledge_points, start=1):
                yield {
                    "event": "research_knowledge",
                    "data": json.dumps(
                        {
                            "event": "research_knowledge",
                            "trace_id": trace_id,
                            "index": idx,
                            "point": point,
                        },
                        ensure_ascii=False,
                    ),
                    "id": str(uuid.uuid4())[:8],
                }

            yield {
                "event": "research_progress",
                "data": json.dumps(
                    {
                        "event": "research_progress",
                        "trace_id": trace_id,
                        "stage": "summarizing",
                        "message": "Report agent is synthesizing structured summary...",
                    },
                    ensure_ascii=False,
                ),
                "id": str(uuid.uuid4())[:8],
            }

            summary_prompt = (
                "请将以下 research 结果整理为结构化结论，输出包括："
                "1) 关键发现 2) 证据与来源 3) 风险与局限 4) 下一步建议。\n\n"
                f"Research Query: {request.query}\n\nRaw Findings:\n{raw}"
            )
            summarized = await orch.run_single_agent(
                user_input=summary_prompt,
                agent_id="bio_report_agent",
                session_id=session_id,
                trace_id=str(uuid.uuid4()),
            )

            yield {
                "event": "research_done",
                "data": json.dumps(
                    {
                        "event": "research_done",
                        "success": True,
                        "trace_id": trace_id,
                        "session_id": session_id,
                        "query": request.query,
                        "research": raw,
                        "summary": summarized,
                        "sources": sources,
                        "knowledge": knowledge_points,
                    },
                    ensure_ascii=False,
                ),
                "id": str(uuid.uuid4())[:8],
            }
            yield {
                "event": "done",
                "data": json.dumps(
                    {"event": "done", "trace_id": trace_id}, ensure_ascii=False
                ),
                "id": str(uuid.uuid4())[:8],
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"event": "error", "trace_id": trace_id, "message": str(e)},
                    ensure_ascii=False,
                ),
                "id": str(uuid.uuid4())[:8],
            }

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════════
# 会话管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/sessions", response_model=List[SessionInfo])
@app.get("/api/sessions", response_model=List[SessionInfo])
async def list_sessions():
    """列出所有会话"""
    session_log = get_feature_logger("sessions")
    try:
        sessions = state.session_manager.list_sessions()
        session_log.info(f"list_sessions total={len(sessions)}")
        return [
            SessionInfo(
                session_id=s.get("session_id", ""),
                title=s.get("title", "")[:50],
                status=s.get("status", "active"),
                created_at=s.get("created_at", ""),
                updated_at=s.get("updated_at", ""),
                message_count=s.get("message_count", 0),
            )
            for s in sessions[:50]
        ]
    except Exception as e:
        logger.error(f"List sessions error: {e}")
        session_log.error(f"list_sessions_error error={type(e).__name__}: {e}")
        return []


@app.post("/sessions")
@app.post("/api/sessions")
async def create_session(title: str = "新会话"):
    """创建新会话"""
    session_log = get_feature_logger("sessions")
    try:
        session_id = state.session_manager.new_session(title=title[:50])
        session_log.info(f"create_session session_id={session_id} title={title[:50]}")
        return {"session_id": session_id, "title": title}
    except Exception as e:
        session_log.error(
            f"create_session_error title={title[:50]} error={type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    session_log = get_feature_logger("sessions")
    try:
        session = state.session_manager.get_session(session_id)
        if not session:
            session_log.warning(f"get_session_not_found session_id={session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        session_log.info(f"get_session session_id={session_id}")
        return session
    except HTTPException:
        raise
    except Exception as e:
        session_log.error(
            f"get_session_error session_id={session_id} error={type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    session_log = get_feature_logger("sessions")
    try:
        state.session_manager.delete_session(session_id)
        session_log.info(f"delete_session session_id={session_id}")
        return {"success": True}
    except Exception as e:
        session_log.error(
            f"delete_session_error session_id={session_id} error={type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# Provider 管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/providers", response_model=List[ProviderInfo])
@app.get("/api/providers", response_model=List[ProviderInfo])
async def list_providers():
    """列出所有 Provider"""
    provider_log = get_feature_logger("providers")
    try:
        pr = state.provider_registry
        providers = pr.list_all()
        provider_log.info(
            f"list_providers total={len(providers)} active={pr.active_id}"
        )
        result = []
        for p in providers:
            try:
                prov = pr.get(p["id"])
                model = getattr(prov, "model", "")
            except Exception as e:
                logger.warning(f"Failed to get model for {p['id']}: {e}")
                model = ""
            result.append(
                ProviderInfo(
                    id=p["id"],
                    name=p["name"],
                    model=model,
                    active=p["active"],
                )
            )
        return result
    except Exception as e:
        logger.error(f"List providers error: {e}")
        provider_log.error(f"list_providers_error error={type(e).__name__}: {e}")
        return []


@app.post("/providers/{provider_id}/use")
@app.post("/api/providers/{provider_id}/use")
async def use_provider(provider_id: str):
    """切换 Provider"""
    try:
        state.provider_registry.use(provider_id)
        return {"success": True, "provider": provider_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/providers/current")
@app.get("/api/providers/current")
async def get_current_provider():
    """获取当前 Provider"""
    try:
        pr = state.provider_registry
        return {
            "id": pr.active_id,
            "name": pr.active_name,
            "model": pr.active_model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/providers/health")
@app.get("/api/providers/health")
async def get_provider_health(provider_id: Optional[str] = None):
    """获取 Provider 健康状态"""
    try:
        healthy = await state.provider_registry.health_check(provider_id)
        pid = provider_id or state.provider_registry.active_id
        return {
            "provider_id": pid,
            "healthy": healthy,
            "active": pid == state.provider_registry.active_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel


class AddProviderRequest(BaseModel):
    id: str
    name: str
    type: str  # "openai" or "anthropic"
    model: str
    base_url: str = ""
    api_key: str


class UpdateProviderRequest(BaseModel):
    name: str
    type: str  # "openai" or "anthropic"
    model: str
    base_url: str = ""
    api_key: str


@app.post("/providers")
@app.post("/api/providers")
async def add_provider(request: AddProviderRequest):
    """添加新 Provider"""
    try:
        pr = state.provider_registry
        from providers.openai_provider import OpenAIProvider
        from providers.anthropic_provider import AnthropicProvider

        if request.type == "anthropic":
            provider = AnthropicProvider(
                model=request.model,
                api_key=request.api_key,
            )
            provider.name = request.name
        else:
            provider = OpenAIProvider(
                model=request.model,
                base_url=request.base_url or "https://api.openai.com/v1",
                api_key=request.api_key,
            )
            provider.name = request.name

        profile = {
            "id": request.id,
            "name": request.name,
            "type": request.type,
            "model": request.model,
            "base_url": request.base_url or "https://api.openai.com/v1",
            "api_key": request.api_key,
            "active": False,
        }

        pr.add(request.id, provider, profile)

        logger.info(f"✅ 添加 Provider: {request.id} ({request.name})")
        return {
            "success": True,
            "provider_id": request.id,
            "name": request.name,
            "model": request.model,
        }
    except Exception as e:
        logger.error(f"添加 Provider 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/providers/{provider_id}")
@app.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """删除 Provider"""
    try:
        pr = state.provider_registry
        if provider_id == pr.active_id:
            raise HTTPException(status_code=400, detail="不能删除当前使用的 Provider")

        pr.remove(provider_id)

        logger.info(f"🗑️ 删除 Provider: {provider_id}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/providers/{provider_id}")
@app.put("/api/providers/{provider_id}")
async def update_provider(provider_id: str, request: UpdateProviderRequest):
    """更新已有 Provider 配置"""
    try:
        pr = state.provider_registry
        if provider_id not in pr.profiles:
            raise HTTPException(status_code=404, detail="Provider not found")

        from providers.openai_provider import OpenAIProvider
        from providers.anthropic_provider import AnthropicProvider

        if request.type == "anthropic":
            provider = AnthropicProvider(
                model=request.model,
                api_key=request.api_key,
            )
            provider.name = request.name
        else:
            provider = OpenAIProvider(
                model=request.model,
                base_url=request.base_url or "https://api.openai.com/v1",
                api_key=request.api_key,
            )
            provider.name = request.name

        profile = {
            "id": provider_id,
            "name": request.name,
            "type": request.type,
            "model": request.model,
            "base_url": request.base_url or "https://api.openai.com/v1",
            "api_key": request.api_key,
            "active": provider_id == pr.active_id,
        }

        pr.update(provider_id, provider, profile)

        logger.info(f"♻️ 更新 Provider: {provider_id} ({request.name})")
        return {
            "success": True,
            "provider_id": provider_id,
            "name": request.name,
            "model": request.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新 Provider 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# 技能管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/skills", response_model=List[SkillInfo])
@app.get("/api/skills", response_model=List[SkillInfo])
async def list_skills():
    """列出所有技能"""
    try:
        skills = state.skill_registry.list_all()
        return [
            SkillInfo(
                skill_id=s["skill_id"],
                name=s["name"],
                description=s.get("description", ""),
                version=s.get("version", "0.02"),
                tags=[],
                enabled=bool(s.get("enabled", 1)),
            )
            for s in skills
        ]
    except Exception as e:
        logger.error(f"List skills error: {e}")
        return []


@app.get("/skills/{skill_id}")
@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    """获取技能详情"""
    try:
        meta = state.skill_registry.get_metadata(skill_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Skill not found")
        return meta.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skills/{skill_id}/enable")
@app.post("/api/skills/{skill_id}/enable")
async def enable_skill(skill_id: str):
    """启用技能"""
    try:
        state.skill_registry.enable(skill_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skills/{skill_id}/disable")
@app.post("/api/skills/{skill_id}/disable")
async def disable_skill(skill_id: str):
    """禁用技能"""
    try:
        state.skill_registry.disable(skill_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# 记忆管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/memory/stats")
@app.get("/api/memory/stats")
async def get_memory_stats():
    """获取记忆统计"""
    try:
        return {
            "total": await state.vector_store.count(),
            "vector_store": "LanceDB",
        }
    except Exception as e:
        logger.error(f"Memory stats error: {e}")
        return {"total": 0, "vector_store": "LanceDB"}


@app.delete("/memory/{memory_id}")
@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """删除记忆"""
    try:
        await state.vector_store.delete(memory_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# Hooks 管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/hooks")
@app.get("/api/hooks")
async def list_hooks():
    """列出所有 Hook"""
    try:
        return state.hook_registry.list_hooks()
    except Exception as e:
        logger.error(f"List hooks error: {e}")
        return []


@app.get("/traces")
@app.get("/api/traces")
async def list_traces(limit: int = 20):
    """列出最近的 trace 运行记录（MLflow）"""
    traces_log = get_feature_logger("traces")
    try:
        from integrations.mlflow_trace import get_trace_tracker

        tracker = get_trace_tracker()
        traces = tracker.list_recent_traces(limit=limit)
        traces_log.info(f"list_traces limit={limit} returned={len(traces)}")
        return {"success": True, "traces": traces, "total": len(traces)}
    except Exception as e:
        logger.error(f"List traces error: {e}")
        traces_log.error(
            f"list_traces_error limit={limit} error={type(e).__name__}: {e}"
        )
        return {"success": True, "traces": [], "total": 0}


# ═══════════════════════════════════════════════════════════════════
# Debug / Status 接口
# ═══════════════════════════════════════════════════════════════════

DEBUG_DEV_MODE = os.getenv("DEBUG_DEV_MODE", "true").lower() == "true"


def _check_dev_mode():
    """检查是否为开发模式，非开发模式拒绝访问 debug 接口"""
    if not DEBUG_DEV_MODE:
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints disabled. Set DEBUG_DEV_MODE=true to enable.",
        )


@app.get("/debug/status")
async def debug_status():
    """获取完整系统状态（用于调试）"""
    _check_dev_mode()
    try:
        return {
            "initialized": state._initialized,
            "agents_count": len(state.all_agents),
            "agents": [
                {
                    "id": a.agent_id,
                    "running": getattr(a, "_running", False),
                }
                for a in state.all_agents
            ],
            "bus_agents": list(state.bus.registered_agents) if state.bus else [],
            "hooks": state.hook_registry.list_hooks() if state.hook_registry else [],
            "providers": state.provider_registry.list_all()
            if state.provider_registry
            else [],
            "skills": state.skill_registry.list_all() if state.skill_registry else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug status error: {e}")
        return {"error": str(e)}


@app.get("/debug/agents")
async def debug_agents():
    """获取所有 Agent 详细信息"""
    _check_dev_mode()
    try:
        return {
            "agents": [
                {
                    "id": a.agent_id,
                    "description": getattr(a, "description", ""),
                    "skills": getattr(a, "skills", []),
                    "running": getattr(a, "_running", False),
                    "role": getattr(a, "config", {}).get("role", ""),
                    "name": getattr(a, "config", {}).get("name", ""),
                    "system_prompt": getattr(a, "config", {})
                    .get("llm", {})
                    .get("system_prompt", ""),
                    "has_soul_body": bool(
                        getattr(a, "config", {}).get("_soul_body", "")
                    ),
                }
                for a in state.all_agents
            ],
            "bus_agents": list(state.bus.registered_agents) if state.bus else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug agents error: {e}")
        return {"error": str(e)}


@app.post("/debug/reload")
async def debug_reload():
    """重新加载系统"""
    _check_dev_mode()
    try:
        state._initialized = False
        state._initializing = False
        state._all_agents = []
        await state.initialize_async()
        return {"success": True, "message": "System reloaded"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reload error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/debug/trace/{trace_id}")
async def get_trace(trace_id: str):
    """获取指定 trace 的详细信息"""
    _check_dev_mode()
    try:
        if not state.bus:
            return {"error": "MessageBus not available"}

        history = state.bus.get_history(trace_id=trace_id)

        return {
            "trace_id": trace_id,
            "message_count": len(history),
            "messages": [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "recipient": m.recipient,
                    "type": m.type,
                    "created_at": m.created_at,
                    "payload": m.payload,
                }
                for m in history
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get trace error: {e}")
        return {"error": str(e)}


@app.get("/debug/results/{session_id}")
async def get_session_results(session_id: str):
    """获取会话的所有任务结果"""
    _check_dev_mode()
    try:
        results = state.session_manager.store.get_results(session_id)
        return {
            "session_id": session_id,
            "results_count": len(results),
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get results error: {e}")
        return {"error": str(e)}


@app.get("/")
async def root():
    return RedirectResponse(url="http://localhost:5173/", status_code=307)


@app.get("/agent.html")
async def agent_page():
    return RedirectResponse(url="http://localhost:5173/", status_code=307)


@app.get("/skills.html")
async def skills_page():
    return RedirectResponse(url="http://localhost:5173/skills", status_code=307)


@app.get("/evolution.html")
async def evolution_page():
    return RedirectResponse(url="http://localhost:5173/approvals", status_code=307)


@app.get("/memory.html")
async def memory_page():
    return RedirectResponse(url="http://localhost:5173/knowledge", status_code=307)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
