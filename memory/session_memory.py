# memory/session_memory.py

import logging
from typing import Optional

from providers.base_provider import ChatMessage
from memory.vector_store import VectorStore
from memory.context_compressor import ContextCompressor

logger = logging.getLogger(__name__)


class SessionMemory:
    """
    会话记忆管理器。

    整合 VectorStore 和 ContextCompressor，
    提供添加记忆、检索上下文、自动压缩功能。
    """

    def __init__(
        self,
        vector_store: VectorStore,
        compressor: ContextCompressor,
        max_messages: int = 10,
        compress_threshold: int = 20,
    ):
        self.vector_store = vector_store
        self.compressor = compressor
        self.max_messages = max_messages
        self.compress_threshold = compress_threshold

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> str:
        """添加一条消息到记忆"""
        memory_id = await self.vector_store.add(
            text=f"{role}: {content}",
            session_id=session_id,
            role=role,
        )
        logger.debug(f"Added message to session {session_id}: {role}")
        return memory_id

    async def get_context(
        self,
        session_id: str,
        query: str = None,
        max_messages: int = None,
    ) -> list[ChatMessage]:
        """
        获取对话上下文。

        - 如果有 query：使用向量检索找到相关记忆
        - 如果没有 query：返回最近的 max_messages 条
        """
        limit = max_messages or self.max_messages

        if query:
            memories = await self.vector_store.search(
                query=query,
                session_id=session_id,
                top_k=limit,
            )
        else:
            memories = await self.vector_store.get_recent(
                session_id=session_id,
                limit=limit,
            )

        messages = []
        for m in memories:
            text = m.get("text", "")
            if ": " in text:
                role, content = text.split(": ", 1)
            else:
                role, content = m.get("role", "unknown"), text
            messages.append(ChatMessage(role=role, content=content))

        return messages

    async def compress_if_needed(self, session_id: str) -> bool:
        """检查并执行压缩"""
        count = await self.vector_store.count(session_id)

        if count >= self.compress_threshold:
            messages = await self.get_context(session_id, max_messages=count)
            compressed = await self.compressor.compress(messages)
            logger.info(
                f"Compressed session {session_id}: "
                f"{count} -> {len(compressed)} messages"
            )
            return True
        return False

    async def get_or_create_compressed(
        self,
        session_id: str,
    ) -> list[ChatMessage]:
        """获取压缩后的上下文"""
        messages = await self.get_context(session_id)
        return await self.compressor.compress(messages)

    async def clear_session(self, session_id: str):
        """清除某个会话的所有记忆"""
        memories = await self.vector_store.get_recent(session_id, limit=1000)
        for m in memories:
            await self.vector_store.delete(m["id"])
        logger.info(f"Cleared all memories for session {session_id}")
