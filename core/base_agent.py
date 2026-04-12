# core/base_agent.py

import asyncio
import collections
import json
import logging
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional, Union
from pydantic import BaseModel, Field, field_validator

from core.message import Message, TaskPayload, ResultPayload, ErrorPayload
from core.hooks import ToolUseEvent, ToolUseResult
from core.events import EventEnvelope
from bus.message_bus import MessageBus
from utils.retry import retry_with_backoff, RetryError

logger = logging.getLogger(__name__)


def _stringify_context(context: dict) -> str:
    if not context:
        return ""

    normalized = {}
    for key, value in context.items():
        if hasattr(value, "to_dict"):
            normalized[key] = value.to_dict()
        elif hasattr(value, "model_dump"):
            normalized[key] = value.model_dump()
        else:
            normalized[key] = value

    try:
        return json.dumps(normalized, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(normalized)


class LLMConfig(BaseModel):
    model: str = "claude-sonnet-4-5"
    max_tokens: int = 2048
    system_prompt: str = ""
    temperature: float = 0.7


class RulesConfig(BaseModel):
    max_retries: int = 3
    timeout_seconds: int = 60
    output_format: str = "markdown"
    can_delegate: bool = False
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0


class MetaConfig(BaseModel):
    created_at: str = ""
    tags: List[str] = []
    enabled: bool = True


class KnowledgeConfig(BaseModel):
    topics: List[str] = []
    max_results: int = 5


class AgentConfig(BaseModel):
    id: str
    name: str = ""
    version: str = "0.02"
    description: str = ""
    skills: List[str] = []
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    meta: MetaConfig = Field(default_factory=MetaConfig)

    @field_validator("id")
    @classmethod
    def id_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Agent id cannot be empty")
        return v.strip()


class BaseAgent(ABC):
    """
    所有 Agent 的基类。

    子类只需要实现 execute() 方法。
    消息收发、错误处理、状态上报全部在这里统一处理。
    支持注入 SkillRegistry、KnowledgeBase、Provider。
    """

    def __init__(
        self,
        agent_id: str,
        bus: MessageBus,
        skills: List[str] = None,
        description: str = "",
        config: Optional[dict] = None,
        registry=None,  # SkillRegistry
        knowledge=None,  # KnowledgeBase
        provider=None,  # BaseProvider
        provider_registry=None,  # ProviderRegistry（优先使用，支持动态切换）
        auto_installer=None,  # AutoInstaller（自我进化）
        memory_store=None,  # VectorStore（Agent 独立记忆）
    ):
        self.agent_id = agent_id
        self.bus = bus
        self.skills = skills or []
        self.description = description
        self.config = dict(config or {})
        self.registry = registry
        self.knowledge = knowledge
        self.provider = provider
        self.provider_registry = provider_registry
        self.auto_installer = auto_installer
        self.memory_store = memory_store
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._hook_registry = None
        self._event_emitter = None  # 事件发射回调 (emit_fn)
        self._trace_emitters = collections.defaultdict(list)
        self._current_trace_id = None
        self._current_session_id = None
        self._current_namespace = ""

    def set_event_emitter(self, emit_fn):
        """设置事件发射回调，用于实时事件流"""
        logger.info(f"🎯 [{self.agent_id}] set_event_emitter 设置了事件回调")
        self._event_emitter = emit_fn

    def register_trace_emitter(self, trace_id: str, emit_fn):
        """为指定 trace 注册事件回调，避免不同流互相覆盖"""
        if trace_id and emit_fn:
            self._trace_emitters[trace_id].append(emit_fn)

    def clear_trace_emitter(self, trace_id: str, emit_fn=None):
        """清理指定 trace 的事件回调"""
        if trace_id not in self._trace_emitters:
            return
        if emit_fn is None:
            self._trace_emitters.pop(trace_id, None)
            return
        self._trace_emitters[trace_id] = [
            cb for cb in self._trace_emitters[trace_id] if cb != emit_fn
        ]
        if not self._trace_emitters[trace_id]:
            self._trace_emitters.pop(trace_id, None)

    def _emit(self, event):
        """发射事件到回调"""
        if hasattr(event, "namespace") and not getattr(event, "namespace", ""):
            event.namespace = self._current_namespace or ""
        event_type = getattr(event, "type", None) or (
            event.event_type.value if hasattr(event, "event_type") else "unknown"
        )
        trace_id = (
            getattr(event, "task_id", None)
            or getattr(event, "trace_id", None)
            or getattr(event, "correlation_id", None)
            or ""
        )
        emitters = []
        if self._event_emitter and callable(self._event_emitter):
            emitters.append(self._event_emitter)
        emitters.extend(self._trace_emitters.get(trace_id, []))

        if emitters:
            logger.info(f"📤 [{self.agent_id}] _emit type={event_type}")
            try:
                for cb in emitters:
                    if asyncio.iscoroutinefunction(cb):
                        asyncio.create_task(cb(event))
                    else:
                        cb(event)
            except Exception:
                pass
        else:
            logger.warning(
                f"📤 [{self.agent_id}] _emit type={event_type} 但无回调（丢弃）"
            )

    def get_provider(self, context: Optional[dict] = None):
        """获取当前活跃的 Provider，优先从 provider_registry 取"""
        if self.provider_registry:
            provider_id = None
            if context:
                provider_id = context.get("provider_id")
            if provider_id:
                return self.provider_registry.get(provider_id)
            return self.provider_registry.get()
        return self.provider

    @classmethod
    def from_yaml(
        cls,
        yaml_path: Union[str, Path],
        bus: MessageBus,
        provider=None,
        registry=None,
        knowledge=None,
        provider_registry=None,
        auto_installer=None,
        hook_registry=None,
    ):
        """从 AGENT.yaml 加载身份文档并初始化 Agent（带 Schema 校验）"""
        raw_config = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
        try:
            config = AgentConfig(**raw_config)
        except Exception as e:
            raise ValueError(f"Agent config validation failed: {e}")

        instance = cls(
            agent_id=config.id,
            bus=bus,
            skills=config.skills,
            description=config.description,
            config=raw_config,
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
            memory_store=None,
        )
        if hook_registry:
            instance.set_hook_registry(hook_registry)
        return instance

    # ── 生命周期 ─────────────────────────────────

    async def start(self):
        """启动 Agent，注册到消息总线并开始监听"""
        await self.bus.register(self.agent_id)
        self._running = True
        self._task = asyncio.create_task(
            self._listen_loop(), name=f"agent-{self.agent_id}"
        )
        logger.info(f"🤖 Agent [{self.agent_id}] 已启动")

    async def stop(self):
        """优雅关闭"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.bus.unregister(self.agent_id)
        logger.info(f"Agent [{self.agent_id}] 已关闭")

    # ── 消息循环 ─────────────────────────────────

    async def _listen_loop(self):
        """持续监听消息队列"""
        while self._running:
            try:
                envelope = await self.bus.receive(self.agent_id, timeout=1.0)
                if envelope is None:
                    continue

                if hasattr(envelope, "message") and envelope.message:
                    message = envelope.message
                else:
                    message = envelope

                if message.type == "task":
                    await self._handle_task(message, envelope)
                elif message.type == "status":
                    await self._handle_status(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Agent [{self.agent_id}] 消息循环异常: {e}", exc_info=True
                )

    async def _handle_task(self, message: Message, envelope=None):
        """处理 task 类型消息（带重试、自我进化机制）"""
        task = TaskPayload(**message.payload)
        logger.info(f"🎯 [{self.agent_id}] 收到任务: {task.instruction[:60]}...")

        previous_trace_id = self._current_trace_id
        previous_session_id = self._current_session_id
        previous_namespace = self._current_namespace
        self._current_trace_id = message.trace_id
        self._current_session_id = message.session_id or task.context.get("session_id")
        self._current_namespace = task.context.get("namespace", "")

        self._emit(
            EventEnvelope.agent_start(
                agent_id=self.agent_id,
                trace_id=message.trace_id,
                instruction=task.instruction,
                session_id=self._current_session_id,
            )
        )

        await self._send_status("running", message.trace_id)

        if self.auto_installer:
            try:
                evolve_result = await self.auto_installer.evolve(
                    agent_id=self.agent_id,
                    instruction=task.instruction,
                )
                if evolve_result.get("submitted"):
                    logger.info(
                        f"📬 [{self.agent_id}] 已提交技能申请: {evolve_result['submitted']}"
                    )
                if evolve_result.get("installed"):
                    logger.info(
                        f"🚀 [{self.agent_id}] 自动安装了技能: {evolve_result['installed']}"
                    )
                if not evolve_result.get("can_proceed"):
                    logger.warning(
                        f"⚠️ [{self.agent_id}] 技能不完整: {evolve_result.get('message')}"
                    )
            except Exception as e:
                logger.warning(f"⚠️ [{self.agent_id}] 自我进化检查失败: {e}")

        rules = self.config.get("rules", {})
        max_retries = rules.get("max_retries", 3)
        timeout_seconds = rules.get("timeout_seconds", 60)

        hook_registry = getattr(self, "_hook_registry", None)

        pre_event = ToolUseEvent(
            tool_name=self.agent_id,
            tool_input={"instruction": task.instruction, "context": task.context},
            agent_id=self.agent_id,
        )
        if hook_registry:
            pre_result = await hook_registry.run_pre_hooks(pre_event)
            if not pre_result.allowed:
                logger.warning(
                    f"[{self.agent_id}] Hook 阻止执行: {pre_result.error_message}"
                )
                await self.bus.send(
                    Message(
                        sender=self.agent_id,
                        recipient=message.sender,
                        type="error",
                        trace_id=message.trace_id,
                        session_id=self._current_session_id,
                        payload=ErrorPayload(
                            error_type="HookDenied",
                            message=f"Hook 阻止执行: {pre_result.error_message}",
                            retryable=False,
                        ).model_dump(),
                    )
                )
            self._current_trace_id = previous_trace_id
            self._current_session_id = previous_session_id
            self._current_namespace = previous_namespace
            return

        import time

        start_time = time.time()

        async def execute_with_context():
            return await self.execute(
                instruction=task.instruction,
                context=task.context,
            )

        try:
            result = await retry_with_backoff(
                execute_with_context,
                max_retries=max_retries,
                base_delay=1.0,
                exponential_base=2.0,
                max_delay=timeout_seconds,
                on_retry=lambda attempt, err: logger.warning(
                    f"🔄 [{self.agent_id}] 第 {attempt}/{max_retries} 次重试: {err}"
                ),
            )

            elapsed_ms = int((time.time() - start_time) * 1000)
            post_event = ToolUseEvent(
                tool_name=self.agent_id,
                tool_input={"instruction": task.instruction, "context": task.context},
                agent_id=self.agent_id,
            )
            tool_result = ToolUseResult(
                tool_name=self.agent_id,
                tool_output=result,
                elapsed_ms=elapsed_ms,
                success=True,
            )
            if hook_registry:
                await hook_registry.run_post_hooks(post_event, tool_result)

            await self.bus.send(
                Message(
                    sender=self.agent_id,
                    recipient=message.sender,
                    type="result",
                    trace_id=message.trace_id,
                    session_id=self._current_session_id,
                    payload=ResultPayload(
                        success=True,
                        output=result,
                        summary=str(result)[:200],
                    ).model_dump(),
                )
            )

            self._emit(
                EventEnvelope.agent_done(
                    agent_id=self.agent_id,
                    trace_id=message.trace_id,
                    result=str(result)[:200],
                    session_id=self._current_session_id,
                )
            )

        except RetryError as e:
            logger.error(f"❌ [{self.agent_id}] 重试耗尽，最终失败: {e}")
            if hook_registry:
                error_event = ToolUseEvent(
                    tool_name=self.agent_id,
                    tool_input={
                        "instruction": task.instruction,
                        "context": task.context,
                    },
                    agent_id=self.agent_id,
                )
                await hook_registry.run_error_hooks(error_event, e)
            await self.bus.send(
                Message(
                    sender=self.agent_id,
                    recipient=message.sender,
                    type="error",
                    trace_id=message.trace_id,
                    session_id=self._current_session_id,
                    payload=ErrorPayload(
                        error_type="RetryExhausted",
                        message=f"执行失败，重试 {e.attempts} 次后仍失败: {e.last_error}",
                        retryable=False,
                    ).model_dump(),
                )
            )
        except Exception as e:
            logger.error(f"[{self.agent_id}] 执行失败: {e}", exc_info=True)
            if hook_registry:
                error_event = ToolUseEvent(
                    tool_name=self.agent_id,
                    tool_input={
                        "instruction": task.instruction,
                        "context": task.context,
                    },
                    agent_id=self.agent_id,
                )
                await hook_registry.run_error_hooks(error_event, e)
            await self.bus.send(
                Message(
                    sender=self.agent_id,
                    recipient=message.sender,
                    type="error",
                    trace_id=message.trace_id,
                    session_id=self._current_session_id,
                    payload=ErrorPayload(
                        error_type=type(e).__name__,
                        message=str(e),
                        retryable=isinstance(e, (TimeoutError, ConnectionError)),
                    ).model_dump(),
                )
            )

        self._current_trace_id = previous_trace_id
        self._current_session_id = previous_session_id
        self._current_namespace = previous_namespace

    async def _handle_status(self, message: Message):
        """处理状态消息（默认忽略，子类可覆盖）"""
        pass

    async def _send_status(self, status: str, trace_id: str):
        """向 Orchestrator 上报状态"""
        await self.bus.send(
            Message(
                sender=self.agent_id,
                recipient="orchestrator",
                type="status",
                trace_id=trace_id,
                session_id=self._current_session_id,
                payload={"status": status, "agent_id": self.agent_id},
            )
        )

    # ── 主动发送任务 ─────────────────────────────

    async def send_task(
        self,
        recipient: str,
        instruction: str,
        context: dict = {},
        trace_id: str = None,
    ) -> str:
        """向另一个 Agent 发送任务，返回 trace_id"""
        msg = Message(
            sender=self.agent_id,
            recipient=recipient,
            type="task",
            session_id=self._current_session_id,
            payload=TaskPayload(
                instruction=instruction,
                context=context,
            ).model_dump(),
        )
        if trace_id:
            msg.trace_id = trace_id
        await self.bus.send(msg)
        return msg.trace_id

    # ── 技能调用（带 Hooks）────────────────────────

    def set_hook_registry(self, registry):
        """设置 Hook 注册中心"""
        self._hook_registry = registry

    async def use_skill(self, skill_id: str, instruction: str, context: dict = {}):
        """Agent 调用技能的统一入口（带 Pre/Post Hooks）"""
        previous_trace_id = self._current_trace_id
        previous_session_id = self._current_session_id
        previous_namespace = self._current_namespace
        if self.registry is None:
            raise RuntimeError("SkillRegistry 未注入")

        skill = self.registry.get(skill_id)
        if skill is None:
            raise ValueError(f"技能 [{skill_id}] 不存在或未安装")

        hook_registry = getattr(self, "_hook_registry", None)

        from core.base_skill import SkillInput
        from core.hooks import HookResult, ToolUseEvent, ToolUseResult

        pre_event = ToolUseEvent(
            tool_name=skill_id,
            tool_input={"instruction": instruction, "context": context},
            agent_id=self.agent_id,
        )

        if hook_registry:
            pre_result = await hook_registry.run_pre_hooks(pre_event)
            if not pre_result.allowed:
                raise PermissionError(
                    f"Hook 阻止执行 [{skill_id}]: {pre_result.error_message}"
                )

        try:
            import time

            self._emit(
                EventEnvelope.agent_tool_call(
                    agent_id=self.agent_id,
                    trace_id=self._current_trace_id or "",
                    skill_id=skill_id,
                    instruction=instruction,
                    session_id=self._current_session_id,
                    namespace=self._current_namespace,
                )
            )

            self._emit(
                EventEnvelope.agent_thinking(
                    agent_id=self.agent_id,
                    trace_id=self._current_trace_id or "",
                    message=f"Executing skill: {skill_id}",
                    session_id=self._current_session_id,
                    namespace=self._current_namespace,
                )
            )

            start_time = time.time()
            output = await skill.execute(
                SkillInput(
                    instruction=instruction,
                    context=context,
                )
            )
            elapsed_ms = int((time.time() - start_time) * 1000)

            self._emit(
                EventEnvelope.agent_output(
                    agent_id=self.agent_id,
                    trace_id=self._current_trace_id or "",
                    output=str(output)[:500],
                    summary=str(output)[:100],
                    session_id=self._current_session_id,
                    namespace=self._current_namespace,
                )
            )

            post_event = ToolUseEvent(
                tool_name=skill_id,
                tool_input={"instruction": instruction, "context": context},
                agent_id=self.agent_id,
            )
            tool_result = ToolUseResult(
                tool_name=skill_id,
                tool_output=output,
                elapsed_ms=elapsed_ms,
                success=True,
            )

            if hook_registry:
                post_result = await hook_registry.run_post_hooks(
                    post_event, tool_result
                )
                if not post_result.allowed:
                    raise PermissionError(
                        f"Hook 阻止执行 [{skill_id}]: {post_result.error_message}"
                    )
                if post_result.modified_output is not None:
                    output = post_result.modified_output

            return output

        except Exception as e:
            if hook_registry:
                error_event = ToolUseEvent(
                    tool_name=skill_id,
                    tool_input={"instruction": instruction, "context": context},
                    agent_id=self.agent_id,
                )
                await hook_registry.run_error_hooks(error_event, e)
            raise
        finally:
            self._current_trace_id = previous_trace_id
            self._current_session_id = previous_session_id
            self._current_namespace = previous_namespace

    # ── 知识库检索 ───────────────────────────────

    async def retrieve_context(
        self,
        query: str,
        topic: str = None,
        top_k: int = 3,
        scope_id: str = None,
        namespace: str = None,
    ) -> str:
        """执行前自动检索相关知识，KB 不可用时静默跳过"""
        if self.knowledge is None:
            return ""
        try:
            from knowledge.retriever import Retriever

            retriever = Retriever(self.knowledge)
            return await retriever.get_context(
                query=query,
                agent_id=self.agent_id,
                topic=topic,
                top_k=top_k,
                scope_id=scope_id,
                namespace=namespace,
            )
        except RuntimeError as e:
            if "未初始化" in str(e) or "连接失败" in str(e):
                return ""
            raise

    async def retrieve_memory_context(
        self,
        query: str,
        top_k: int = 3,
        scope_id: str = None,
        namespace: str = None,
    ) -> str:
        """检索 Agent 独立记忆，KB 不可用时静默跳过"""
        if self.memory_store is None:
            return ""
        try:
            memories = await self.memory_store.search(
                query=query,
                owner=self.agent_id,
                top_k=top_k,
                scope_id=scope_id,
                namespace=namespace,
            )
        except Exception as e:
            logger.warning(f"[{self.agent_id}] memory retrieval failed: {e}")
            return ""

        if not memories:
            return ""

        lines = ["【相关Agent记忆】"]
        for i, item in enumerate(memories, 1):
            lines.append(f"{i}. {item.get('text', '')}")
        return "\n".join(lines)

    # ── LLM 调用 ─────────────────────────────────

    async def _execute_with_llm(
        self,
        instruction: str,
        context: dict = {},
        max_tokens: int = None,
        system: str = None,
    ) -> str:
        """通用的 LLM 调用逻辑，供子类组合使用"""
        self._emit(
            EventEnvelope.agent_thinking(
                agent_id=self.agent_id,
                trace_id=self._current_trace_id or "",
                message="正在思考问题...",
                session_id=self._current_session_id,
                namespace=(context or {}).get("namespace", self._current_namespace),
            )
        )

        scope_id = context.get("scope_id") if context else None
        knowledge_topic = context.get("knowledge_topic") if context else None
        knowledge_namespace = context.get("knowledge_namespace") if context else None
        memory_namespace = context.get("memory_namespace") if context else None
        knowledge_ctx = await self.retrieve_context(
            instruction,
            topic=knowledge_topic,
            top_k=3,
            scope_id=scope_id,
            namespace=knowledge_namespace,
        )
        memory_ctx = await self.retrieve_memory_context(
            instruction,
            top_k=3,
            scope_id=scope_id,
            namespace=memory_namespace,
        )

        prompt_system = system or self.get_system_prompt()
        if knowledge_ctx:
            prompt_system += "\n\n" + knowledge_ctx
        if memory_ctx:
            prompt_system += "\n\n" + memory_ctx

        context_str = _stringify_context(context)
        if context_str:
            prompt_system += (
                "\n\n## Runtime Context\n"
                "Use the following runtime context as the freshest available information. "
                "If search/tool results are present, prefer them over model prior knowledge. "
                "Do not output pseudo tool calls, XML tags, or instructions to yourself; answer directly for the user.\n"
                f"{context_str}"
            )

        prov = self.get_provider(context)
        if not prov:
            raise RuntimeError("没有可用 LLM Provider")

        from providers.base_provider import ChatMessage

        cfg = self.config.get("llm", {})
        tokens = max_tokens or cfg.get("max_tokens", 2048)

        self._emit(
            EventEnvelope.agent_tool_call(
                agent_id=self.agent_id,
                trace_id=self._current_trace_id or "",
                skill_id="llm",
                instruction=instruction[:100],
                session_id=self._current_session_id,
                namespace=(context or {}).get("namespace", self._current_namespace),
            )
        )

        resp = await prov.chat(
            messages=[ChatMessage(role="user", content=instruction)],
            system=prompt_system,
            max_tokens=tokens,
        )

        self._emit(
            EventEnvelope.agent_output(
                agent_id=self.agent_id,
                trace_id=self._current_trace_id or "",
                output=resp.text[:200] if resp.text else "",
                summary=resp.text[:100] if resp.text else "",
                session_id=self._current_session_id,
                namespace=(context or {}).get("namespace", self._current_namespace),
            )
        )

        return resp.text

    async def _chat_stream(
        self,
        instruction: str,
        context: dict = {},
        max_tokens: int = None,
        system: str = None,
    ) -> AsyncIterator[str]:
        """流式 LLM 调用，返回异步生成器"""
        scope_id = context.get("scope_id") if context else None
        knowledge_topic = context.get("knowledge_topic") if context else None
        knowledge_namespace = context.get("knowledge_namespace") if context else None
        memory_namespace = context.get("memory_namespace") if context else None
        knowledge_ctx = await self.retrieve_context(
            instruction,
            topic=knowledge_topic,
            top_k=3,
            scope_id=scope_id,
            namespace=knowledge_namespace,
        )
        memory_ctx = await self.retrieve_memory_context(
            instruction,
            top_k=3,
            scope_id=scope_id,
            namespace=memory_namespace,
        )

        prompt_system = system or self.get_system_prompt()
        if knowledge_ctx:
            prompt_system += "\n\n" + knowledge_ctx
        if memory_ctx:
            prompt_system += "\n\n" + memory_ctx

        context_str = _stringify_context(context)
        if context_str:
            prompt_system += (
                "\n\n## Runtime Context\n"
                "Use the following runtime context as the freshest available information. "
                "If search/tool results are present, prefer them over model prior knowledge. "
                "Do not output pseudo tool calls, XML tags, or instructions to yourself; answer directly for the user.\n"
                f"{context_str}"
            )

        prov = self.get_provider(context)
        if not prov:
            raise RuntimeError("没有可用 LLM Provider")

        from providers.base_provider import ChatMessage

        cfg = self.config.get("llm", {})
        tokens = max_tokens or cfg.get("max_tokens", 2048)

        if hasattr(prov, "chat_stream"):
            async for chunk in prov.chat_stream(
                messages=[ChatMessage(role="user", content=instruction)],
                system=prompt_system,
                max_tokens=tokens,
            ):
                yield chunk
        else:
            resp = await prov.chat(
                messages=[ChatMessage(role="user", content=instruction)],
                system=prompt_system,
                max_tokens=tokens,
            )
            yield resp.text

    # ── 子类必须实现 ─────────────────────────────

    @abstractmethod
    async def execute(self, instruction: str, context: dict) -> Any:
        """子类在这里实现具体业务逻辑"""
        ...

    # ── 配置辅助 ─────────────────────────────────

    def get_system_prompt(self) -> str:
        """从 soul.md 配置构建完整的 system prompt"""
        base_prompt = self.config.get("llm", {}).get(
            "system_prompt", f"你是 {self.agent_id}。"
        )

        parts = [base_prompt]

        if self.skills:
            skills_list = ", ".join(self.skills)
            parts.append(f"\n\n## 可用技能\n你有以下技能可用：{skills_list}")

        soul_body = self.config.get("_soul_body", "")
        if soul_body:
            parts.append(f"\n\n## 角色说明\n{soul_body}")

        agent_desc = self.description
        if agent_desc:
            parts.append(f"\n\n## 职责\n{agent_desc}")

        return "\n".join(parts)
