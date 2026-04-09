# core/base_agent.py

import asyncio
import logging
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional, Union

from core.message import Message, TaskPayload, ResultPayload, ErrorPayload
from core.hooks import ToolUseEvent, ToolUseResult
from core.events import AgentEvent
from bus.message_bus import MessageBus
from utils.retry import retry_with_backoff, RetryError

logger = logging.getLogger(__name__)


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
        config: dict = {},
        registry=None,  # SkillRegistry
        knowledge=None,  # KnowledgeBase
        provider=None,  # BaseProvider
        provider_registry=None,  # ProviderRegistry（优先使用，支持动态切换）
        auto_installer=None,  # AutoInstaller（自我进化）
    ):
        self.agent_id = agent_id
        self.bus = bus
        self.skills = skills or []
        self.description = description
        self.config = config
        self.registry = registry
        self.knowledge = knowledge
        self.provider = provider
        self.provider_registry = provider_registry
        self.auto_installer = auto_installer
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._hook_registry = None
        self._event_emitter = None  # 事件发射回调 (emit_fn)
        self._current_trace_id = None
        self._current_session_id = None

    def set_event_emitter(self, emit_fn):
        """设置事件发射回调，用于实时事件流"""
        self._event_emitter = emit_fn

    def _emit(self, event):
        """发射事件到回调"""
        if self._event_emitter and callable(self._event_emitter):
            try:
                import asyncio

                cb = self._event_emitter
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(event))
                else:
                    cb(event)
            except Exception:
                pass

    def get_provider(self):
        """获取当前活跃的 Provider，优先从 provider_registry 取"""
        if self.provider_registry:
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
        """从 AGENT.yaml 加载身份文档并初始化 Agent"""
        config = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
        instance = cls(
            agent_id=config["id"],
            bus=bus,
            skills=config.get("skills", []),
            description=config.get("description", ""),
            config=config,
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
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
                message = await self.bus.receive(self.agent_id, timeout=1.0)
                if message is None:
                    continue

                if message.type == "task":
                    await self._handle_task(message)
                elif message.type == "status":
                    await self._handle_status(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Agent [{self.agent_id}] 消息循环异常: {e}", exc_info=True
                )

    async def _handle_task(self, message: Message):
        """处理 task 类型消息（带重试、自我进化机制）"""
        task = TaskPayload(**message.payload)
        logger.info(f"🎯 [{self.agent_id}] 收到任务: {task.instruction[:60]}...")

        self._current_trace_id = message.trace_id

        self._emit(
            AgentEvent.agent_start(
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
                        payload=ErrorPayload(
                            error_type="HookDenied",
                            message=f"Hook 阻止执行: {pre_result.error_message}",
                            retryable=False,
                        ).model_dump(),
                    )
                )
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
                    payload=ResultPayload(
                        success=True,
                        output=result,
                        summary=str(result)[:200],
                    ).model_dump(),
                )
            )

            self._emit(
                AgentEvent.agent_done(
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
                    payload=ErrorPayload(
                        error_type=type(e).__name__,
                        message=str(e),
                        retryable=isinstance(e, (TimeoutError, ConnectionError)),
                    ).model_dump(),
                )
            )

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
                AgentEvent.agent_tool_call(
                    agent_id=self.agent_id,
                    trace_id=self._current_trace_id or "",
                    skill_id=skill_id,
                    instruction=instruction,
                    session_id=self._current_session_id,
                )
            )

            self._emit(
                AgentEvent.agent_thinking(
                    agent_id=self.agent_id,
                    trace_id=self._current_trace_id or "",
                    message=f"Executing skill: {skill_id}",
                    session_id=self._current_session_id,
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
                AgentEvent.agent_output(
                    agent_id=self.agent_id,
                    trace_id=self._current_trace_id or "",
                    output=str(output)[:500],
                    summary=str(output)[:100],
                    session_id=self._current_session_id,
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

    # ── 知识库检索 ───────────────────────────────

    async def retrieve_context(
        self,
        query: str,
        topic: str = None,
        top_k: int = 3,
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
            )
        except RuntimeError as e:
            if "未初始化" in str(e) or "连接失败" in str(e):
                return ""
            raise

    # ── LLM 调用 ─────────────────────────────────

    async def _execute_with_llm(
        self,
        instruction: str,
        context: dict = {},
        max_tokens: int = None,
        system: str = None,
    ) -> str:
        """通用的 LLM 调用逻辑，供子类组合使用"""
        knowledge_ctx = await self.retrieve_context(instruction, top_k=3)

        prompt_system = system or self.get_system_prompt()
        if knowledge_ctx:
            prompt_system += "\n\n" + knowledge_ctx

        prov = self.get_provider()
        if not prov:
            raise RuntimeError("没有可用 LLM Provider")

        from providers.base_provider import ChatMessage

        cfg = self.config.get("llm", {})
        tokens = max_tokens or cfg.get("max_tokens", 2048)

        resp = await prov.chat(
            messages=[ChatMessage(role="user", content=instruction)],
            system=prompt_system,
            max_tokens=tokens,
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
        knowledge_ctx = await self.retrieve_context(instruction, top_k=3)

        prompt_system = system or self.get_system_prompt()
        if knowledge_ctx:
            prompt_system += "\n\n" + knowledge_ctx

        prov = self.get_provider()
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
        """从配置里取 system_prompt，没有就用默认"""
        return self.config.get("llm", {}).get(
            "system_prompt", f"你是 {self.agent_id}，请完成分配的任务。"
        )
