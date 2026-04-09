# bus/message_bus.py

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from core.message import Message

logger = logging.getLogger(__name__)

MAX_DEDUP_CACHE_SIZE = 10000
DEDUP_TTL_SECONDS = 300


@dataclass
class MessageEnvelope:
    """
    消息统一封装
    增加可靠性语义：event_id, task_id, session_id, correlation_id, created_at
    """

    event_id: str = ""
    task_id: str = ""
    session_id: Optional[str] = None
    correlation_id: str = ""
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    message: Message = None


class DeduplicationCache:
    """
    短期去重缓存，防止重复消费
    使用 LRU 策略清理过期条目
    """

    def __init__(
        self, max_size: int = MAX_DEDUP_CACHE_SIZE, ttl: int = DEDUP_TTL_SECONDS
    ):
        self._cache: Dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl
        self._lock = asyncio.Lock()

    async def is_duplicate(self, event_id: str) -> bool:
        """检查是否重复，返回 True 表示重复"""
        now = time.time()
        async with self._lock:
            if event_id in self._cache:
                if now - self._cache[event_id] < self._ttl:
                    return True
                del self._cache[event_id]

            self._cache[event_id] = now

            if len(self._cache) > self._max_size:
                oldest_keys = sorted(self._cache.items(), key=lambda x: x[1])[
                    : self._max_size // 2
                ]
                for k in oldest_keys:
                    del self._cache[k[0]]

            return False

    async def mark_processed(self, event_id: str):
        """标记已处理"""
        await self.is_duplicate(event_id)


class MessageBus:
    """
    基于 asyncio.Queue 的消息总线。

    每个 Agent 注册一个专属队列，发消息时按 recipient 路由到对应队列。
    支持广播（recipient="*"）。

    可靠性特性：
    - 消息统一封装（MessageEnvelope）
    - 发送方可在 payload 中携带 correlation_id 用于关联
    - 内置去重缓存防止重复消费
    """

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._history: deque = deque(maxlen=1000)
        self._lock = asyncio.Lock()
        self._dedup = DeduplicationCache()

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

    def _wrap_message(self, message: Message) -> MessageEnvelope:
        """将消息包装为统一封装"""
        return MessageEnvelope(
            event_id=message.id,
            task_id=message.trace_id,
            session_id=getattr(message, "session_id", None),
            correlation_id=getattr(message, "correlation_id", ""),
            created_at=time.time(),
            retry_count=getattr(message, "retry_count", 0),
            message=message,
        )

    async def send(self, message: Message):
        """发送消息，自动路由"""
        self._history.append(message)

        envelope = self._wrap_message(message)

        if message.recipient == "*":
            for agent_id, queue in self._queues.items():
                if agent_id != message.sender:
                    await queue.put(envelope)
            logger.debug(f"📢 广播 [{message.type}] {message.sender} → ALL")
        else:
            queue = self._queues.get(message.recipient)
            if queue is None:
                logger.error(f"❌ 目标 Agent [{message.recipient}] 未注册，消息丢弃")
                return
            await queue.put(envelope)
            logger.debug(f"📨 [{message.type}] {message.sender} → {message.recipient}")

    async def receive(
        self, agent_id: str, timeout: float = None
    ) -> Optional[MessageEnvelope]:
        """
        Agent 调用此方法取消息。
        timeout=None  表示一直等待
        timeout=0    表示非阻塞，没有消息立即返回 None
        """
        queue = self._queues.get(agent_id)
        if queue is None:
            raise RuntimeError(f"Agent [{agent_id}] 未注册")

        try:
            if timeout == 0:
                envelope = queue.get_nowait()
            else:
                envelope = await asyncio.wait_for(queue.get(), timeout=timeout)

            if envelope and hasattr(envelope, "message"):
                return envelope
            return envelope

        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None

    async def check_duplicate(self, event_id: str) -> bool:
        """检查是否重复消息"""
        return await self._dedup.is_duplicate(event_id)

    async def mark_processed(self, event_id: str):
        """标记消息已处理"""
        await self._dedup.mark_processed(event_id)

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
