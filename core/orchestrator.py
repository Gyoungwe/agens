# core/orchestrator.py

import asyncio
import logging
import json
import uuid
import yaml
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

from core.message import Message, TaskPayload, ResultPayload
from core.base_agent import BaseAgent
from core.events import AgentEvent, AgentEventType
from bus.message_bus import MessageBus
from utils.retry import retry_with_backoff, RetryError

logger = logging.getLogger(__name__)

AGENTS_CONFIG_PATH = Path("config/agents.yaml")
_agents_config_cache = None


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
        self._events: Dict[str, asyncio.Event] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._event_callbacks: Dict[str, callable] = {}
        self._current_session_id = None

    def create_event_queue(self, trace_id: str) -> asyncio.Queue:
        """为指定的 trace_id 创建事件队列"""
        q = asyncio.Queue()
        self._event_queues[trace_id] = q
        return q

    def set_event_callback(self, trace_id: str, callback: callable):
        """设置事件回调，用于实时事件流推送"""
        self._event_callbacks[trace_id] = callback

    async def _emit_event(self, event: AgentEvent):
        """发射事件到队列或回调"""
        trace_id = event.trace_id
        if trace_id in self._event_queues:
            await self._event_queues[trace_id].put(event)
        if trace_id in self._event_callbacks:
            callback = self._event_callbacks[trace_id]
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
        elif self._event_emitter:
            try:
                if asyncio.iscoroutinefunction(self._event_emitter):
                    await self._event_emitter(event)
                else:
                    self._event_emitter(event)
            except Exception as e:
                logger.error(f"Event emitter error: {e}")

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
    ) -> str:
        """
        支持 Session Resume：
        - session_id=None   → 新会话
        - session_id="xxx"  → 恢复历史会话继续对话
        """
        sm = self.session_manager
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
                sm.new_session(title=user_input[:40])
                session_id = sm.current_session_id
                self._current_session_id = session_id
            await sm.add_user_message(user_input)
            if self.context_compressor:
                context_messages = await sm.get_context() or []

        # 1. 用 LLM 拆解任务（带上下文）
        plan = await self._plan(user_input, context_messages=context_messages)
        logger.info(f"📋 任务计划: {plan}")

        # 2. 生成 trace_id（如果还没有的话）
        # 注意：chat_stream 会先设置 _current_trace_id
        trace_id = (
            self._current_trace_id if self._current_trace_id else str(uuid.uuid4())
        )

        # 3. 按计划分发子任务
        await self._dispatch(plan, user_input, context_messages, trace_id)

        # 3. 等待所有结果（最多 120 秒）
        results = await self._wait_for_results(trace_id, timeout=120)

        # 4. 汇总结果（带上下文）
        final = await self._synthesize(
            user_input, results, context_messages=context_messages
        )
        logger.info(f"✅ 任务完成")

        await self._emit_event(
            AgentEvent.final_response(
                agent_id=self.agent_id,
                trace_id=trace_id,
                response=final,
                session_id=self._current_session_id,
            )
        )

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

        return final

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

        plan = await self._plan(user_input)
        logger.info(f"📋 任务计划: {plan}")

        trace_id = await self._dispatch(plan, user_input)
        results = await self._wait_for_results(trace_id, timeout=120)

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

    async def _plan(self, user_input: str, context_messages: list = None) -> list[dict]:
        """用 LLM 把用户任务拆解成子任务列表"""
        available_agents = [
            a for a in self.bus.registered_agents if a != "orchestrator"
        ]

        if not available_agents:
            logger.warning("没有可用的 Agent")
            return []

        config = _load_agents_config()
        agent_descriptions = []
        for agent_id in available_agents:
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
                return []
            return json.loads(text[start:end])
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 原始响应: {text[:500]}")
            return []
        except Exception as e:
            logger.error(f"任务规划失败: {e}", exc_info=True)
            return []

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
    ) -> dict:
        """发送任务带重试，只负责发送，不等待结果"""
        rules = self._get_agent_config(recipient)
        max_retries = rules.get("max_retries", 3)

        msg = Message(
            sender="orchestrator",
            recipient=recipient,
            type="task",
            trace_id=trace_id,
            payload=TaskPayload(
                instruction=instruction,
                context={"original_task": original_input},
            ).model_dump(),
        )

        async def send_once():
            await self.bus.send(msg)
            return {"sent": True}

        try:
            await retry_with_backoff(
                send_once,
                max_retries=max_retries,
                base_delay=1.0,
                exponential_base=2.0,
                max_delay=30.0,
                on_retry=lambda attempt, err: logger.warning(
                    f"🔄 [{recipient}] 第 {attempt} 次重试: {err}"
                ),
            )
            return {"sent": True}
        except RetryError as e:
            logger.error(f"❌ [{recipient}] 重试耗尽: {e}")
            self._pending[trace_id][recipient] = {"error": str(e)}
            return {"error": str(e)}

    async def _dispatch(
        self,
        plan: List[dict],
        original_input: str,
        context_messages: list = None,
        trace_id: str = None,
    ) -> str:
        """并行分发所有子任务（带重试机制），返回 trace_id"""
        if not plan:
            logger.warning("任务计划为空")
            return ""

        trace_id = trace_id or str(uuid.uuid4())
        agent_ids = [step["agent"] for step in plan]
        self._pending[trace_id] = {aid: None for aid in agent_ids}
        self._events[trace_id] = asyncio.Event()

        await self._emit_event(
            AgentEvent.agent_start(
                agent_id=self.agent_id,
                trace_id=trace_id,
                instruction=original_input,
                session_id=self._current_session_id,
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
            task = self._send_task_with_retry(
                recipient=recipient,
                trace_id=trace_id,
                instruction=step["instruction"],
                original_input=original_input,
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
        pass

    async def _listen_loop(self):
        """覆盖父类的监听循环，专门收集子 Agent 的返回"""
        while self._running:
            try:
                message = await self.bus.receive(self.agent_id, timeout=1.0)
                if message is None:
                    continue

                if message.type in ("result", "error"):
                    await self._collect_result(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Orchestrator 异常: {e}", exc_info=True)

    async def _collect_result(self, message: Message):
        """收集子 Agent 的结果"""
        trace_id = message.trace_id
        if trace_id not in self._pending:
            return

        result = (
            ResultPayload(**message.payload)
            if message.type == "result"
            else {"error": message.payload.get("message")}
        )

        self._pending[trace_id][message.sender] = result
        logger.info(f"📩 收到 [{message.sender}] 的结果 (trace: {trace_id[:8]}...)")

        if all(v is not None for v in self._pending[trace_id].values()):
            self._events[trace_id].set()

    async def _wait_for_results(self, trace_id: str, timeout: float) -> dict:
        """等待所有子任务完成"""
        event = self._events.get(trace_id)
        if event:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"⏰ 任务超时: {trace_id[:8]}...")
                # 标记未完成的任务为超时
                if trace_id in self._pending:
                    for agent_id, result in self._pending[trace_id].items():
                        if result is None:
                            self._pending[trace_id][agent_id] = {"error": "执行超时"}

        results = self._pending.pop(trace_id, {})
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
