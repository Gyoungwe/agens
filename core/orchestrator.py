# core/orchestrator.py

import asyncio
import logging
import json
import time
import uuid
import yaml
from pathlib import Path
from copy import deepcopy
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from core.delegation_policy import decide_delegation
from core.message import Message, TaskPayload, ResultPayload
from core.base_agent import BaseAgent
from core.events import EventEnvelope, AgentEvent, AgentEventType
from core.runtime_contract import RuntimeDelegationDecisionContract
from bus.message_bus import MessageBus, DeduplicationCache
from utils.retry import retry_with_backoff, RetryError
from integrations.mlflow_trace import get_trace_tracker

logger = logging.getLogger(__name__)

AGENTS_CONFIG_PATH = Path("config/agents.yaml")
_agents_config_cache = None


def _default_parallel_plan(user_input: str, available_agents: List[str]) -> List[dict]:
    """当 LLM 规划失败时，提供安全回退计划。"""
    fallback = []
    for agent_id in available_agents:
        fallback.append(
            {
                "agent": agent_id,
                "instruction": f"围绕以下原始任务，从你的专业角色给出可执行贡献：{user_input}",
                "depends_on": [],
            }
        )
    return fallback


def _select_candidate_agents(
    user_input: str,
    available_agents: List[str],
) -> tuple[List[str], Optional[str], str]:
    """根据用户输入选择最小必要 agent 子集，并给出补充建议。"""
    text = (user_input or "").lower()

    bio_keywords = [
        "rna-seq",
        "rna_seq",
        "wgs",
        "wes",
        "metagenomics",
        "atac",
        "chip",
        "assembly",
        "fastq",
        "bam",
        "vcf",
        "gtf",
        "fasta",
        "nextflow",
        "snakemake",
        "pipeline",
        "workflow",
        "生信",
        "生物信息",
        "差异表达",
        "变异检测",
        "质控",
        "qc",
    ]
    chat_keywords = [
        "生日",
        "who is",
        "what is",
        "你好",
        "hello",
        "hi",
        "翻译",
        "解释",
        "写一段",
        "润色",
        "谢谢",
    ]

    has_bio = any(k in text for k in bio_keywords)
    has_chat = any(k in text for k in chat_keywords)

    if has_chat and not has_bio:
        return (
            [],
            None,
            "Detected general conversational intent; no multi-agent collaboration needed.",
        )

    if not has_bio:
        return (
            [],
            None,
            "No explicit workflow/bioinformatics intent detected; defaulting to direct chat response.",
        )

    selected: List[str] = []
    recommendation: Optional[str] = None

    def add_if_exists(agent_id: str):
        if agent_id in available_agents and agent_id not in selected:
            selected.append(agent_id)

    if any(k in text for k in ["规划", "plan", "流程设计", "路线"]):
        add_if_exists("bio_planner_agent")
    if any(k in text for k in ["代码", "脚本", "nextflow", "snakemake", "实现"]):
        add_if_exists("bio_code_agent")
    if any(k in text for k in ["qc", "质控", "质量", "通过", "指标"]):
        add_if_exists("bio_qc_agent")
    if any(k in text for k in ["报告", "总结", "汇报", "结论"]):
        add_if_exists("bio_report_agent")
    if any(k in text for k in ["优化", "改进", "迭代", "evolution"]):
        add_if_exists("bio_evolution_agent")

    if not selected:
        # 生信相关但用户没明确需求时，先做轻量协作并给建议
        add_if_exists("bio_planner_agent")
        add_if_exists("bio_report_agent")
        recommendation = (
            "你的需求还比较宽泛。建议补充 assay 类型（如 RNA-seq/WGS）、"
            "输入数据格式（FASTQ/BAM/VCF）和期望产出（如 QC 报告/差异表达结果），"
            "这样我可以调度更精准的 agent 协作。"
        )

    return (
        selected,
        recommendation,
        "Bioinformatics workflow intent detected; selecting minimal relevant agents.",
    )


def _load_agents_config() -> dict:
    global _agents_config_cache
    if _agents_config_cache is None:
        if AGENTS_CONFIG_PATH.exists():
            _agents_config_cache = (
                yaml.safe_load(AGENTS_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            )
        else:
            _agents_config_cache = {"agents": []}
    return _agents_config_cache


class Orchestrator(BaseAgent):
    """
    任务调度器。

    职责：
    1. 接收用户任务
    2. 用 LLM 拆解成子任务
    3. 分发给对应 Agent
    4. 收集结果，汇总返回
    支持 Session Resume（会话恢复继续对话）。
    """

    def __init__(
        self,
        bus: MessageBus,
        provider_registry,  # ProviderRegistry
        session_manager=None,  # SessionManager（可选）
        context_compressor=None,  # ContextCompressor（可选）
    ):
        super().__init__(
            agent_id="orchestrator",
            bus=bus,
            provider=provider_registry.get(),
        )
        self.provider_registry = provider_registry
        self.session_manager = session_manager
        self.context_compressor = context_compressor
        self._pending: Dict[str, dict] = {}
        self._pending_timestamps: Dict[str, float] = {}
        self._events: Dict[str, asyncio.Event] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._event_callbacks: Dict[str, callable] = {}
        self._current_session_id = None
        self._dedup_cache = DeduplicationCache(max_size=5000, ttl=600)
        self._processed_results: Set[str] = set()
        self._correlation_ids: Dict[str, str] = {}
        self._PENDING_TTL = 600
        self._cleanup_task: Optional[asyncio.Task] = None
        self._trace_tracker = get_trace_tracker()
        self._start_cleanup_task()

    def create_event_queue(self, trace_id: str) -> asyncio.Queue:
        """为指定的 trace_id 创建事件队列"""
        q = asyncio.Queue()
        self._event_queues[trace_id] = q
        return q

    def _start_cleanup_task(self):
        """启动 pending 条目 TTL 清理任务"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_pending_loop())
            logger.debug("Pending cleanup task started")

    async def _cleanup_pending_loop(self):
        """定期清理超期 pending 条目"""
        while True:
            await asyncio.sleep(60)
            try:
                await self._cleanup_stale_pending()
            except Exception as e:
                logger.warning(f"Pending cleanup error: {e}")

    async def _cleanup_stale_pending(self):
        """清理超期的 pending 条目"""
        now = time.time()
        stale_trace_ids = [
            trace_id
            for trace_id, timestamp in self._pending_timestamps.items()
            if now - timestamp > self._PENDING_TTL
        ]
        for trace_id in stale_trace_ids:
            logger.warning(f"清理超期 pending 条目: {trace_id[:8]}...")
            self._pending.pop(trace_id, None)
            self._pending_timestamps.pop(trace_id, None)
            self._events.pop(trace_id, None)
            self._event_queues.pop(trace_id, None)
            self._event_callbacks.pop(trace_id, None)

    def set_event_callback(self, trace_id: str, callback: callable):
        """设置事件回调，用于实时事件流推送"""
        self._event_callbacks[trace_id] = callback

    async def _emit_event(self, event):
        """发射事件到队列或回调（可观测化，异常不静默丢失）"""
        trace_id = (
            getattr(event, "trace_id", None) or getattr(event, "task_id", None) or ""
        )
        event_type = getattr(event, "type", None) or (
            event.event_type.value if hasattr(event, "event_type") else "unknown"
        )
        logger.info(
            f"📤 [_emit_event] type={event_type} trace_id={trace_id[:8] if trace_id else 'none'} -> queue={trace_id in self._event_queues}"
        )
        if trace_id in self._event_queues:
            await self._event_queues[trace_id].put(event)
        asyncio.create_task(self._safe_emit_callback(event, trace_id))

    async def _safe_emit_callback(self, event, trace_id: str):
        """安全地调用回调，保证可观测性"""
        event_type = getattr(event, "type", None) or (
            event.event_type.value if hasattr(event, "event_type") else "unknown"
        )
        try:
            if trace_id in self._event_callbacks:
                logger.info(
                    f"📤 [_safe_emit] trace_id={trace_id[:8]} type={event_type} -> event_callbacks"
                )
                callback = self._event_callbacks[trace_id]
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            elif self._event_emitter:
                logger.info(
                    f"📤 [_safe_emit] trace_id={trace_id[:8]} type={event_type} -> _event_emitter"
                )
                if asyncio.iscoroutinefunction(self._event_emitter):
                    await self._event_emitter(event)
                else:
                    self._event_emitter(event)
            else:
                logger.warning(
                    f"📤 [_safe_emit] trace_id={trace_id[:8]} type={event_type} -> 无回调（丢弃）"
                )
        except Exception as e:
            logger.warning(f"Event emit failed (degraded): {type(e).__name__}: {e}")

    def get_event_queue(self, trace_id: str) -> asyncio.Queue:
        """获取指定 trace_id 的事件队列"""
        return self._event_queues.get(trace_id)

    def clear_event_queue(self, trace_id: str):
        """清理指定 trace_id 的事件队列"""
        self._event_queues.pop(trace_id, None)
        self._event_callbacks.pop(trace_id, None)

    # ── 核心入口 ─────────────────────────────────

    async def run(
        self,
        user_input: str,
        session_id: str = None,
        trace_id: str = None,
        memory_scope: str = "session",
    ) -> str:
        """
        支持 Session Resume：
        - session_id=None   → 新会话
        - session_id="xxx"  → 恢复历史会话继续对话
        """
        sm = self.session_manager
        previous_trace_id = self._current_trace_id
        previous_session_id = self._current_session_id
        if trace_id:
            self._current_trace_id = trace_id
        elif not self._current_trace_id:
            self._current_trace_id = str(uuid.uuid4())
        trace_id = self._current_trace_id
        self._current_session_id = session_id

        context_messages = []
        if sm:
            if session_id:
                history = sm.resume_session(session_id)
                logger.info(f"▶️ 恢复会话，历史 {len(history)} 条")
                if (
                    self.context_compressor
                    and len(history) > self.context_compressor.max_messages
                ):
                    history = await self.context_compressor.compress(history)
                    logger.info(f"🗜️ 上下文压缩后: {len(history)} 条")
            else:
                session_id = None
            if self.context_compressor:
                if memory_scope == "global" and sm._memory:
                    context_messages = (
                        await sm._memory.get_context(
                            session_id=sm.current_session_id,
                            query=user_input,
                            max_messages=self.context_compressor.max_messages,
                            global_scope=True,
                        )
                        or []
                    )
                else:
                    context_messages = await sm.get_context() or []

        # 1. 决策并生成任务计划（带上下文）
        decision, plan = await self._plan(user_input, context_messages=context_messages)
        logger.info(f"📋 任务计划: {plan}")

        if sm and not session_id:
            session_kind = "research" if decision.mode == "research" else "chat"
            title = (
                f"Research: {user_input[:40]}"
                if decision.mode == "research"
                else user_input[:40]
            )
            sm.new_session(title=title, kind=session_kind)
            session_id = sm.current_session_id
            self._current_session_id = session_id

        if sm and decision.mode != "research":
            await sm.add_user_message(user_input)

        # 2. trace 已在规划前生成，避免 routing 事件缺少 trace_id
        logger.info(f"🚀 [run] trace_id={trace_id} 开始执行")

        trace_start = time.time()
        self._trace_tracker.start_trace(
            trace_id=trace_id,
            user_input=user_input,
            session_id=self._current_session_id,
            plan=plan,
        )

        try:
            if decision.mode == "clarify_first":
                final = decision.clarification_question or decision.reason
                await self._emit_event(
                    EventEnvelope.final_response(
                        agent_id=self.agent_id,
                        trace_id=trace_id,
                        response=final,
                        session_id=self._current_session_id,
                    )
                )
                if sm:
                    await sm.add_assistant_message(final)
                self._trace_tracker.finish_trace(
                    trace_id=trace_id,
                    status="success",
                    elapsed_ms=int((time.time() - trace_start) * 1000),
                    results_count=0,
                    final_length=len(final or ""),
                )
                return final

            if decision.mode == "research":
                final = await self._run_research_mode(
                    user_input=user_input,
                    session_id=session_id,
                    trace_id=trace_id,
                )
                await self._emit_event(
                    EventEnvelope.final_response(
                        agent_id=self.agent_id,
                        trace_id=trace_id,
                        response=final,
                        session_id=self._current_session_id,
                        namespace="research_runtime",
                    )
                )
                if sm:
                    await sm.add_assistant_message(final)
                self._trace_tracker.finish_trace(
                    trace_id=trace_id,
                    status="success",
                    elapsed_ms=int((time.time() - trace_start) * 1000),
                    results_count=1,
                    final_length=len(final or ""),
                )
                return final

            if not plan:
                from providers.base_provider import ChatMessage

                direct_prompt = (
                    "请以自然对话方式直接回答用户，不要假设这是生信 workflow 任务，"
                    "除非用户明确要求 pipeline/workflow。"
                )
                provider = self.get_provider()
                resp = await provider.chat(
                    messages=[ChatMessage(role="user", content=user_input)],
                    system=direct_prompt,
                    max_tokens=1024,
                )
                final = resp.text
                await self._emit_event(
                    EventEnvelope.final_response(
                        agent_id=self.agent_id,
                        trace_id=trace_id,
                        response=final,
                        session_id=self._current_session_id,
                    )
                )
                if sm:
                    await sm.add_assistant_message(final)
                self._trace_tracker.finish_trace(
                    trace_id=trace_id,
                    status="success",
                    elapsed_ms=int((time.time() - trace_start) * 1000),
                    results_count=0,
                    final_length=len(final or ""),
                )
                return final

            # 3. 按计划分发子任务
            await self._dispatch(
                plan,
                user_input,
                context_messages,
                trace_id,
                session_id=session_id,
            )

            # 4. 等待所有结果（最多 120 秒）
            results = await self._wait_for_results(
                trace_id,
                timeout=120,
                session_id=session_id,
            )

            # 5. 汇总结果（带上下文）
            final = await self._synthesize(
                user_input, results, context_messages=context_messages
            )
            logger.info(f"✅ 任务完成, trace_id={trace_id}")

            logger.info(f"🚀 [run] 准备发射 final_response, trace_id={trace_id}")
            await self._emit_event(
                EventEnvelope.final_response(
                    agent_id=self.agent_id,
                    trace_id=trace_id,
                    response=final,
                    session_id=self._current_session_id,
                )
            )
            logger.info(f"🚀 [run] final_response 已发射, trace_id={trace_id}")

            if sm:
                await sm.add_assistant_message(final)
                for agent_id, result in results.items():
                    sm.store.save_result(
                        session_id=sm.current_session_id,
                        trace_id=trace_id,
                        agent_id=agent_id,
                        result=getattr(result, "output", result),
                    )
                if self.context_compressor:
                    await sm.add_message_async("assistant", final)

            self._trace_tracker.finish_trace(
                trace_id=trace_id,
                status="success",
                elapsed_ms=int((time.time() - trace_start) * 1000),
                results_count=len(results),
                final_length=len(final or ""),
            )

            return final
        except Exception as e:
            self._trace_tracker.finish_trace(
                trace_id=trace_id,
                status="failed",
                elapsed_ms=int((time.time() - trace_start) * 1000),
                results_count=0,
                final_length=0,
                error=f"{type(e).__name__}: {e}",
            )
            raise
        finally:
            self._current_trace_id = previous_trace_id
            self._current_session_id = previous_session_id

    async def run_single_agent(
        self,
        user_input: str,
        agent_id: str,
        session_id: str = None,
        trace_id: str = None,
        runtime_context: Optional[dict] = None,
        emit_final_response: bool = True,
    ) -> str:
        """
        直接运行单个 Agent（不经过 Orchestrator 调度）

        用于独立 Agent 问答模式

        Args:
            user_input: 用户输入
            agent_id: 目标 Agent ID
            session_id: 会话 ID（可选）
            trace_id: 追踪 ID（可选）

        Returns:
            Agent 的响应结果
        """
        sm = self.session_manager
        previous_trace_id = self._current_trace_id
        previous_session_id = self._current_session_id
        if trace_id:
            self._current_trace_id = trace_id
        else:
            trace_id = str(uuid.uuid4())
            self._current_trace_id = trace_id

        if session_id:
            sm.resume_session(session_id)
        else:
            kind = (
                (runtime_context or {}).get("session_kind", "chat")
                if runtime_context
                else "chat"
            )
            sm.new_session(title=user_input[:40], kind=kind)
            session_id = sm.current_session_id
        self._current_session_id = session_id

        await sm.add_user_message(user_input)

        self._pending[trace_id] = {agent_id: None}
        self._pending_timestamps[trace_id] = time.time()
        self._events[trace_id] = asyncio.Event()

        await self._emit_event(
            EventEnvelope.agent_start(
                agent_id=agent_id,
                trace_id=trace_id,
                instruction=user_input,
                session_id=session_id,
                namespace=(runtime_context or {}).get("namespace", ""),
            )
        )

        try:
            await self._send_task_with_retry(
                recipient=agent_id,
                trace_id=trace_id,
                instruction=user_input,
                original_input=user_input,
                runtime_context=runtime_context,
                session_id=session_id,
            )

            results = await self._wait_for_results(
                trace_id,
                timeout=120,
                session_id=session_id,
            )

            final = ""
            if results and agent_id in results:
                final = results[agent_id]
                if hasattr(final, "output"):
                    final = final.output
                elif isinstance(final, dict):
                    final = final.get("output", str(final))

            await self._emit_event(
                EventEnvelope.agent_done(
                    agent_id=agent_id,
                    trace_id=trace_id,
                    result=final,
                    session_id=session_id,
                    namespace=(runtime_context or {}).get("namespace", ""),
                )
            )

            if emit_final_response:
                await self._emit_event(
                    EventEnvelope.final_response(
                        agent_id=agent_id,
                        trace_id=trace_id,
                        response=final,
                        session_id=session_id,
                        namespace=(runtime_context or {}).get("namespace", ""),
                    )
                )

            await sm.add_assistant_message(final)

            return final
        finally:
            self._current_trace_id = previous_trace_id
            self._current_session_id = previous_session_id

    async def run_stream(
        self,
        user_input: str,
        session_id: str = None,
    ) -> AsyncIterator[str]:
        """流式版本，返回异步生成器"""
        sm = self.session_manager

        if sm:
            if session_id:
                history = sm.resume_session(session_id)
                logger.info(f"▶️ 恢复会话，历史 {len(history)} 条")
            else:
                sm.new_session(title=user_input[:40])
            await sm.add_user_message(user_input)

        decision, plan = await self._plan(user_input)
        logger.info(f"📋 任务计划: {plan}")

        if decision.mode in {"research", "clarify_first"}:
            final = (
                await self._run_research_mode(
                    user_input=user_input,
                    session_id=sm.current_session_id if sm else session_id,
                    trace_id=str(uuid.uuid4()),
                )
                if decision.mode == "research"
                else (decision.clarification_question or decision.reason)
            )
            yield final
            if sm:
                await sm.add_assistant_message(final)
            return

        trace_id = await self._dispatch(
            plan, user_input, session_id=sm.current_session_id if sm else None
        )
        results = await self._wait_for_results(
            trace_id,
            timeout=120,
            session_id=sm.current_session_id if sm else None,
        )

        async for chunk in self._synthesize_stream(user_input, results):
            yield chunk

        final_result = ""
        for k, v in results.items():
            if hasattr(v, "output"):
                final_result = v.output
                break
        if sm:
            await sm.add_assistant_message(final_result)

    # ── 任务规划 ─────────────────────────────────

    def _build_research_summary_prompt(self, query: str, raw: str) -> str:
        return (
            "请将以下 research 结果整理成面向用户的中文文本报告。\n\n"
            f"研究问题：{query}\n\n"
            "输出要求：\n"
            "1. 先给简短结论\n"
            "2. 再写 3-6 条关键发现\n"
            "3. 明确不确定性、局限或证据强弱\n"
            "4. 不要输出 JSON\n\n"
            f"原始研究内容：\n{raw}"
        )

    async def _run_research_mode(
        self,
        user_input: str,
        session_id: Optional[str],
        trace_id: str,
    ) -> str:
        runtime_context = {
            "scope_id": f"research::{(user_input or '').strip()[:80]}",
            "knowledge_topic": "research",
            "knowledge_namespace": "research_memory",
            "namespace": "research_runtime",
            "session_kind": "research",
        }
        raw = await self.run_single_agent(
            user_input=user_input,
            agent_id="research_agent",
            session_id=session_id,
            trace_id=trace_id,
            runtime_context=runtime_context,
            emit_final_response=False,
        )
        if "writer_agent" not in self.bus.registered_agents:
            return raw

        summary_prompt = self._build_research_summary_prompt(user_input, raw)
        return await self.run_single_agent(
            user_input=summary_prompt,
            agent_id="writer_agent",
            session_id=session_id,
            trace_id=trace_id,
            runtime_context=runtime_context,
            emit_final_response=False,
        )

    async def _plan(
        self, user_input: str, context_messages: list = None
    ) -> tuple[RuntimeDelegationDecisionContract, list[dict]]:
        """先做 delegation 决策，再决定是否生成多 Agent 任务计划。"""
        available_agents = [
            a for a in self.bus.registered_agents if a != "orchestrator"
        ]

        selected_agents, recommendation, decision_reason = _select_candidate_agents(
            user_input=user_input,
            available_agents=available_agents,
        )

        decision = decide_delegation(
            user_input=user_input,
            available_agents=available_agents,
            selected_agents=selected_agents,
            recommendation=recommendation,
            decision_reason=decision_reason,
        )

        try:
            if self._current_trace_id:
                decision_payload = json.dumps(
                    {"event": "routing_decision", **decision.model_dump()},
                    ensure_ascii=False,
                )
                asyncio.create_task(
                    self._emit_event(
                        EventEnvelope.agent_output(
                            agent_id=self.agent_id,
                            trace_id=self._current_trace_id,
                            output=decision_payload,
                            summary="routing_decision",
                            namespace="chat_runtime",
                        )
                    )
                )
        except Exception:
            pass

        if decision.mode in {"direct_chat", "research", "clarify_first"}:
            logger.info("任务识别为普通对话，跳过多 Agent 协作调度")
            return decision, []

        if not available_agents:
            logger.warning("没有可用的 Agent")
            return decision, []

        config = _load_agents_config()
        agent_descriptions = []
        for agent_id in decision.selected_agents:
            for agent_cfg in config.get("agents", []):
                if agent_cfg.get("id") == agent_id:
                    desc = agent_cfg.get("description", "")
                    name = agent_cfg.get("name", agent_id)
                    agent_descriptions.append(f"- {agent_id}（{name}）：{desc}")
                    break
            else:
                agent_descriptions.append(f"- {agent_id}")

        context_text = ""
        if context_messages:
            ctx_lines = [f"{m.role}: {m.content}" for m in context_messages[-5:]]
            context_text = (
                f"\n\n对话上下文（最近 {len(context_messages)} 条）：\n"
                + "\n".join(ctx_lines)
            )

        prompt = f"""你是一个任务规划器。把用户的任务拆解成子任务，分配给合适的 Agent。

可用的 Agent：
{chr(10).join(agent_descriptions)}
{context_text}

用户任务：{user_input}

输出 JSON 数组，每项包含：
- agent: agent_id
- instruction: 给这个 Agent 的具体指令
- depends_on: []（暂时全部填空数组，并行执行）

只输出 JSON，不要解释。示例：
[
  {{"agent": "research_agent", "instruction": "搜集关于...的信息"}},
  {{"agent": "writer_agent", "instruction": "根据上下文撰写..."}}
]"""

        from providers.base_provider import ChatMessage

        try:
            provider = self.get_provider()
            resp = await provider.chat(
                messages=[ChatMessage(role="user", content=prompt)],
                system="你是一个任务规划专家，输出结构化的 JSON 数组。",
                max_tokens=1024,
            )
            text = resp.text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start == -1 or end == 0:
                logger.error(f"LLM 返回不是有效的 JSON 格式: {text[:200]}")
                return decision, _default_parallel_plan(user_input, available_agents)
            plan = json.loads(text[start:end])
            normalized = []
            for step in plan:
                agent = step.get("agent")
                instruction = step.get("instruction")
                if not agent or not instruction:
                    continue
                normalized.append(
                    {
                        "agent": agent,
                        "instruction": instruction,
                        "depends_on": step.get("depends_on", []),
                    }
                )
            if recommendation and normalized:
                for step in normalized:
                    step["instruction"] = (
                        f"{step['instruction']}\n\n[建议补充给用户]\n{recommendation}"
                    )
            return decision, normalized or _default_parallel_plan(
                user_input, decision.selected_agents
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 原始响应: {text[:500]}")
            return decision, _default_parallel_plan(
                user_input, decision.selected_agents
            )
        except Exception as e:
            logger.error(f"任务规划失败: {e}", exc_info=True)
            return decision, _default_parallel_plan(
                user_input, decision.selected_agents
            )

    # ── 任务分发（带重试） ─────────────────────────

    def _get_agent_config(self, agent_id: str) -> dict:
        """获取 Agent 配置"""
        config = _load_agents_config()
        for agent_cfg in config.get("agents", []):
            if agent_cfg.get("id") == agent_id:
                return agent_cfg.get("rules", {})
        return {}

    async def _send_task_with_retry(
        self,
        recipient: str,
        trace_id: str,
        instruction: str,
        original_input: str,
        runtime_context: Optional[dict] = None,
        session_id: str = None,
        correlation_id: str = None,
    ) -> dict:
        """发送任务带重试，只负责发送，不等待结果"""
        rules = self._get_agent_config(recipient)
        max_retries = rules.get("max_retries", 3)
        base_delay = rules.get("retry_base_delay", 1.0)
        max_delay = rules.get("retry_max_delay", 30.0)

        task_context = {"original_task": original_input, **(runtime_context or {})}
        msg = Message(
            sender="orchestrator",
            recipient=recipient,
            type="task",
            trace_id=trace_id,
            payload=TaskPayload(
                instruction=instruction,
                context=task_context,
            ).model_dump(),
        )
        if correlation_id:
            msg.correlation_id = correlation_id
        else:
            msg.correlation_id = trace_id
        msg.session_id = session_id

        async def send_once():
            await self.bus.send(msg)
            return {"sent": True}

        import random

        actual_base_delay = base_delay * (0.5 + random.random() * 0.5)

        try:
            await retry_with_backoff(
                send_once,
                max_retries=max_retries,
                base_delay=actual_base_delay,
                exponential_base=2.0,
                max_delay=max_delay,
                on_retry=lambda attempt, err: logger.warning(
                    f"🔄 [{recipient}] 第 {attempt} 次重试: {err}"
                ),
            )
            return {"sent": True}
        except RetryError as e:
            logger.error(f"❌ [{recipient}] 重试耗尽: {e}")
            self._pending[trace_id][recipient] = {
                "error": str(e),
                "error_code": "RETRY_EXHAUSTED",
            }
        await self._emit_event(
            EventEnvelope.task_failed(
                agent_id=recipient,
                trace_id=trace_id,
                error_message=str(e),
                error_code="RETRY_EXHAUSTED",
                session_id=session_id,
                namespace=(runtime_context or {}).get("namespace", ""),
            )
        )
        return {"error": str(e)}

    async def _dispatch(
        self,
        plan: List[dict],
        original_input: str,
        context_messages: list = None,
        trace_id: str = None,
        session_id: str = None,
    ) -> str:
        """并行分发所有子任务（带重试机制），返回 trace_id"""
        if not plan:
            logger.warning("任务计划为空")
            return ""

        trace_id = trace_id or str(uuid.uuid4())
        agent_ids = [step["agent"] for step in plan]
        self._pending[trace_id] = {aid: None for aid in agent_ids}
        self._pending_timestamps[trace_id] = time.time()
        self._events[trace_id] = asyncio.Event()

        await self._emit_event(
            EventEnvelope.agent_start(
                agent_id=self.agent_id,
                trace_id=trace_id,
                instruction=original_input,
                session_id=session_id,
                namespace="chat_runtime",
            )
        )

        tasks = []
        for step in plan:
            recipient = step["agent"]
            if recipient not in self.bus.registered_agents:
                logger.warning(f"Agent [{recipient}] 未注册，跳过")
                self._pending[trace_id][recipient] = {
                    "error": f"Agent [{recipient}] 未注册"
                }
                if all(v is not None for v in self._pending[trace_id].values()):
                    self._events[trace_id].set()
                continue

            logger.info(f"📤 分发任务 → [{recipient}]: {step['instruction'][:50]}...")
            self._trace_tracker.log_dispatch(trace_id=trace_id, agent_id=recipient)
            task = self._send_task_with_retry(
                recipient=recipient,
                trace_id=trace_id,
                instruction=step["instruction"],
                original_input=original_input,
                runtime_context=step.get("context"),
                session_id=session_id,
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"📤 已分发 {len(tasks)} 个子任务，trace_id: {trace_id[:8]}...")
        return trace_id

    # ── 结果收集 ─────────────────────────────────

    async def execute(self, instruction: str, context: dict) -> Any:
        return "Orchestrator 不接受直接任务指派"

    async def _handle_task(self, message: Message):
        logger.warning(
            f"Orchestrator received direct task but does not support direct execution: sender={message.sender} trace_id={message.trace_id}"
        )

    async def _listen_loop(self):
        """覆盖父类的监听循环，专门收集子 Agent 的返回"""
        while self._running:
            try:
                envelope = await self.bus.receive(self.agent_id, timeout=1.0)
                if envelope is None:
                    continue

                if hasattr(envelope, "message") and envelope.message:
                    message = envelope.message
                else:
                    message = envelope

                if message.type in ("result", "error"):
                    await self._collect_result(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Orchestrator 异常: {e}", exc_info=True)

    async def _collect_result(self, message: Message):
        """收集子 Agent 的结果（带去重）"""
        trace_id = message.trace_id
        if trace_id not in self._pending:
            return

        dedup_key = f"{trace_id}:{message.sender}:{message.type}"
        if dedup_key in self._processed_results:
            logger.debug(f"🔁 跳过重复结果: {dedup_key}")
            return
        self._processed_results.add(dedup_key)

        if len(self._processed_results) > 10000:
            self._processed_results = set(list(self._processed_results)[-5000:])

        result = (
            ResultPayload(**message.payload)
            if message.type == "result"
            else {
                "error": message.payload.get("message", "Unknown error"),
                "error_code": "AGENT_ERROR",
            }
        )

        self._pending[trace_id][message.sender] = result
        logger.info(f"📩 收到 [{message.sender}] 的结果 (trace: {trace_id[:8]}...)")
        success = message.type == "result"
        self._trace_tracker.log_agent_result(
            trace_id=trace_id,
            agent_id=message.sender,
            success=success,
        )

        if all(v is not None for v in self._pending[trace_id].values()):
            self._events[trace_id].set()

    async def _wait_for_results(
        self, trace_id: str, timeout: float, session_id: str = None
    ) -> dict:
        """等待所有子任务完成"""
        event = self._events.get(trace_id)
        start_time = time.time()
        if event:
            try:
                remaining = timeout
                while remaining > 0 and not event.is_set():
                    try:
                        await asyncio.wait_for(event.wait(), timeout=remaining)
                        break
                    except asyncio.TimeoutError:
                        remaining = timeout - (time.time() - start_time)
                        if remaining <= 0:
                            break
                        elapsed = time.time() - start_time
                        logger.warning(
                            f"⏰ 任务执行中，已等待 {elapsed:.1f}s，继续等待..."
                        )
                        continue
            except asyncio.TimeoutError:
                pass

        elapsed = time.time() - start_time
        if elapsed >= timeout:
            logger.warning(f"⏰ 任务超时: {trace_id[:8]}... (耗时 {elapsed:.1f}s)")
            await self._emit_event(
                EventEnvelope.task_timeout(
                    agent_id=self.agent_id,
                    trace_id=trace_id,
                    timeout_seconds=timeout,
                    session_id=session_id,
                    namespace="chat_runtime",
                )
            )
            if trace_id in self._pending:
                for agent_id, result in self._pending[trace_id].items():
                    if result is None:
                        self._pending[trace_id][agent_id] = {
                            "error": "执行超时",
                            "error_code": "TIMEOUT",
                        }

        results = self._pending.pop(trace_id, {})
        self._pending_timestamps.pop(trace_id, None)
        self._events.pop(trace_id, None)
        return results

    # ── 结果汇总 ─────────────────────────────────

    async def _synthesize(
        self, original_input: str, results: dict, context_messages: list = None
    ) -> str:
        """用 LLM 把所有子任务结果汇总成最终答案"""
        results_text = json.dumps(
            {k: (v.output if hasattr(v, "output") else v) for k, v in results.items()},
            ensure_ascii=False,
            indent=2,
        )

        context_text = ""
        if context_messages:
            ctx_lines = [f"{m.role}: {m.content}" for m in context_messages[-5:]]
            context_text = "\n\n对话上下文：\n" + "\n".join(ctx_lines)

        prompt = f"""原始任务：{original_input}
{context_text}

各 Agent 执行结果：
{results_text}

请把以上结果整合成一份清晰、完整的最终答案，直接回答用户的问题。"""

        from providers.base_provider import ChatMessage

        provider = self.get_provider()
        resp = await provider.chat(
            messages=[ChatMessage(role="user", content=prompt)],
            system="你是一个总结专家，输出结构清晰、表达流畅的总结。",
            max_tokens=2048,
        )
        return resp.text

    async def _synthesize_stream(
        self, original_input: str, results: dict
    ) -> AsyncIterator[str]:
        """流式汇总结果"""
        results_text = json.dumps(
            {k: (v.output if hasattr(v, "output") else v) for k, v in results.items()},
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""原始任务：{original_input}

各 Agent 执行结果：
{results_text}

请把以上结果整合成一份清晰、完整的最终答案，直接回答用户的问题。"""

        from providers.base_provider import ChatMessage

        provider = self.get_provider()

        if hasattr(provider, "chat_stream"):
            async for chunk in provider.chat_stream(
                messages=[ChatMessage(role="user", content=prompt)],
                system="你是一个总结专家，输出结构清晰、表达流畅的总结。",
                max_tokens=2048,
            ):
                yield chunk
        else:
            resp = await provider.chat(
                messages=[ChatMessage(role="user", content=prompt)],
                system="你是一个总结专家，输出结构清晰、表达流畅的总结。",
                max_tokens=2048,
            )
            yield resp.text
