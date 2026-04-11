# session/session_manager.py

import logging
import os
import uuid
from typing import Optional
from session.session_store import SessionStore
from providers.base_provider import ChatMessage

logger = logging.getLogger(__name__)


class SessionManager:
    """
    会话管理器，支持会话创建、恢复和历史管理。

    可选集成 Memory 系统（向量存储 + 上下文压缩）：
    - 通过 set_memory() 设置 SessionMemory 实例
    - 自动存储和检索向量记忆
    - 支持上下文压缩
    """

    MAX_HISTORY = 20

    def __init__(self, store: SessionStore):
        self.store = store
        self._current_session_id: Optional[str] = None
        self._memory = None

    def set_memory(self, memory):
        """注入 SessionMemory 实例"""
        self._memory = memory
        logger.info("✅ SessionManager 已集成 Memory")

    def new_session(self, title: str = "") -> str:
        session_id = str(uuid.uuid4())
        self.store.create_session(session_id, title=title)
        self._current_session_id = session_id
        logger.info(f"🆕 新会话: {session_id[:8]}... [{title}]")
        return session_id

    def resume_session(self, session_id: str) -> list[ChatMessage]:
        session = self.store.get_session(session_id)
        if not session:
            raise ValueError(f"会话 [{session_id}] 不存在")

        self._current_session_id = session_id
        raw_messages = self.store.get_messages(session_id)

        if len(raw_messages) > self.MAX_HISTORY:
            raw_messages = raw_messages[-self.MAX_HISTORY :]
            logger.info(f"⚡ 会话历史已截断至最近 {self.MAX_HISTORY} 条")

        messages = [
            ChatMessage(role=m["role"], content=m["content"]) for m in raw_messages
        ]
        logger.info(f"▶️ 恢复会话: {session_id[:8]}... ({len(messages)} 条历史消息)")
        return messages

    def close(self):
        if self._current_session_id:
            self.store.close_session(self._current_session_id)
            logger.info(f"🔒 会话已关闭: {self._current_session_id[:8]}...")
            self._current_session_id = None

    async def add_user_message(self, content: str):
        self._ensure_session()
        self.store.append_message(self._current_session_id, "user", content)
        if self._memory:
            await self._memory.add_message(self._current_session_id, "user", content)
            await self._memory.summarize_topic_if_needed(
                self._current_session_id, "user", content
            )
            await self._memory.compress_if_needed(self._current_session_id)

    async def add_assistant_message(self, content: str):
        self._ensure_session()
        self.store.append_message(self._current_session_id, "assistant", content)
        if self._memory:
            await self._memory.add_message(
                self._current_session_id, "assistant", content
            )
            await self._memory.summarize_topic_if_needed(
                self._current_session_id, "assistant", content
            )
            await self._memory.compress_if_needed(self._current_session_id)

    async def add_message_async(self, role: str, content: str):
        """异步添加消息（用于 chat 流程）"""
        self._ensure_session()
        self.store.append_message(self._current_session_id, role, content)
        if self._memory:
            await self._memory.add_message(self._current_session_id, role, content)
            await self._memory.summarize_topic_if_needed(
                self._current_session_id, role, content
            )
            await self._memory.compress_if_needed(self._current_session_id)

    async def get_context(self, query: str = None) -> list[ChatMessage]:
        """获取上下文（优先从 Memory 获取压缩后的上下文）"""
        if self._memory:
            return await self._memory.get_context(self._current_session_id, query=query)
        return self.get_history()

    def get_history(self) -> list[ChatMessage]:
        self._ensure_session()
        raw = self.store.get_messages(self._current_session_id)
        return [ChatMessage(role=m["role"], content=m["content"]) for m in raw]

    def list_sessions(self) -> list[dict]:
        return self.store.list_sessions()

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.store.get_session(session_id)

    def delete_session(self, session_id: str):
        """删除会话"""
        return self.store.delete_session(session_id)

    def _ensure_session(self):
        if not self._current_session_id:
            self.new_session()

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id
