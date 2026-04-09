# bus/message_bus.py

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional
from core.message import Message

logger = logging.getLogger(__name__)


class MessageBus:
    """
    基于 asyncio.Queue 的消息总线。

    每个 Agent 注册一个专属队列，发消息时按 recipient 路由到对应队列。
    支持广播（recipient="*"）。
    """

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._history: List[Message] = []
        self._lock = asyncio.Lock()

    # ── 注册 / 注销 ─────────────────────────────

    async def register(self, agent_id: str, maxsize: int = 100):
        """Agent 启动时调用，创建专属队列"""
        async with self._lock:
            if agent_id in self._queues:
                logger.warning(f"Agent {agent_id} 已注册，跳过")
                return
            self._queues[agent_id] = asyncio.Queue(maxsize=maxsize)
            logger.info(f"✅ Agent [{agent_id}] 已注册到消息总线")

    async def unregister(self, agent_id: str):
        """Agent 关闭时调用"""
        async with self._lock:
            self._queues.pop(agent_id, None)
            logger.info(f"Agent [{agent_id}] 已从消息总线注销")

    # ── 发送 / 接收 ─────────────────────────────

    async def send(self, message: Message):
        """发送消息，自动路由"""
        self._history.append(message)

        if message.recipient == "*":
            for agent_id, queue in self._queues.items():
                if agent_id != message.sender:
                    await queue.put(message)
            logger.debug(f"📢 广播 [{message.type}] {message.sender} → ALL")
        else:
            queue = self._queues.get(message.recipient)
            if queue is None:
                logger.error(f"❌ 目标 Agent [{message.recipient}] 未注册，消息丢弃")
                return
            await queue.put(message)
            logger.debug(f"📨 [{message.type}] {message.sender} → {message.recipient}")

    async def receive(self, agent_id: str, timeout: float = None) -> Optional[Message]:
        """
        Agent 调用此方法取消息。
        timeout=None  表示一直等待
        timeout=0     表示非阻塞，没有消息立即返回 None
        """
        queue = self._queues.get(agent_id)
        if queue is None:
            raise RuntimeError(f"Agent [{agent_id}] 未注册")

        try:
            if timeout == 0:
                return queue.get_nowait()
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None

    # ── 工具方法 ────────────────────────────────

    def get_history(self, trace_id: str = None) -> list[Message]:
        """获取消息历史，可按 trace_id 过滤"""
        if trace_id:
            return [m for m in self._history if m.trace_id == trace_id]
        return list(self._history)

    def queue_size(self, agent_id: str) -> int:
        """查看某个 Agent 的待处理消息数"""
        q = self._queues.get(agent_id)
        return q.qsize() if q else 0

    @property
    def registered_agents(self) -> list[str]:
        return list(self._queues.keys())
