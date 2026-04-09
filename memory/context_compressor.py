# memory/context_compressor.py
"""
上下文压缩器
参考 Claude Managed Agents 的上下文管理策略

压缩策略:
1. 保留最近 N 条完整消息
2. 早期消息生成结构化摘要
3. 摘要使用 <summary> 标签标记，便于前端折叠
"""

import logging
from typing import Any, List, Optional
from dataclasses import dataclass

from core.message import ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class CompressionConfig:
    """压缩配置"""

    max_messages: int = 10  # 保留的最近消息数
    compress_threshold: int = 20  # 触发压缩的消息数
    summary_model: str = "local"  # 摘要模型 (local/minimix)
    summary_max_tokens: int = 200  # 摘要最大 token 数


@dataclass
class MessageSummary:
    """
    消息摘要结构
    参考 Claude Managed Agents 的结构化输出格式
    """

    messages_count: int  # 被摘要的消息数量
    time_range: str  # 时间范围: "最近X小时" 或 "今天"
    summary: str  # 摘要文本
    key_points: List[str]  # 关键点列表
    decisions: List[str]  # 决定列表
    pending_topics: List[str]  # 待处理话题

    def to_xml(self) -> str:
        """转换为 XML 格式，便于前端渲染和折叠"""
        points_xml = "\n".join(f"      <point>{p}</point>" for p in self.key_points)
        decisions_xml = "\n".join(
            f"      <decision>{d}</decision>" for d in self.decisions
        )
        pending_xml = "\n".join(
            f"      <topic>{t}</topic>" for t in self.pending_topics
        )

        return f"""<summary count="{self.messages_count}" time_range="{self.time_range}">
  <abstract>{self.summary}</abstract>
  <key_points>
{points_xml}
  </key_points>
  <decisions>
{decisions_xml}
  </decisions>
  <pending_topics>
{pending_xml}
  </pending_topics>
</summary>"""

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        lines = [
            f"### 📋 上下文摘要 ({self.messages_count} 条消息)",
            f"**时间范围**: {self.time_range}",
            "",
            f"**摘要**: {self.summary}",
            "",
        ]

        if self.key_points:
            lines.append("**关键点**:")
            for p in self.key_points:
                lines.append(f"- {p}")
            lines.append("")

        if self.decisions:
            lines.append("**决定**:")
            for d in self.decisions:
                lines.append(f"- {d}")
            lines.append("")

        if self.pending_topics:
            lines.append("**待处理**:")
            for t in self.pending_topics:
                lines.append(f"- {t}")

        return "\n".join(lines)


class ContextCompressor:
    """
    上下文压缩器

    当会话消息超过 compress_threshold 时，触发压缩:
    1. 保留最近 max_messages 条完整消息
    2. 早期消息 → LLM 生成结构化摘要
    3. 摘要替换为 <summary> 标签格式的消息
    """

    def __init__(
        self,
        provider=None,  # LLM provider for summarization
        max_messages: int = 10,
        compress_threshold: int = 20,
        summary_max_tokens: int = 200,
    ):
        self.provider = provider
        self.max_messages = max_messages
        self.compress_threshold = compress_threshold
        self.summary_max_tokens = summary_max_tokens

    async def should_compress(self, messages: List[ChatMessage]) -> bool:
        """判断是否需要压缩"""
        return len(messages) >= self.compress_threshold

    async def compress(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """
        压缩消息历史

        Args:
            messages: 原始消息列表

        Returns:
            压缩后的消息列表，格式:
            [
                ChatMessage(role="system", content="[历史摘要]..."),
                ChatMessage(role="user", content="..."),   # 最近的 user 消息
                ChatMessage(role="assistant", content="..."),
                ...
            ]
        """
        if len(messages) < self.compress_threshold:
            return messages

        logger.info(f"开始压缩上下文: {len(messages)} 条消息")

        # 保留最近 max_messages 条
        recent = messages[-self.max_messages :] if self.max_messages > 0 else []
        older = (
            messages[: -self.max_messages] if self.max_messages > 0 else messages[:-10]
        )

        # 生成摘要
        summary = await self._summarize_messages(older)

        # 构建压缩后的消息列表
        compressed = []

        # 添加摘要消息
        summary_content = f"""[历史上下文摘要]

{summary.to_xml()}

---

这是之前对话的摘要，包含 {summary.messages_count} 条消息的关键信息。"""

        compressed.append(
            ChatMessage(
                role="system",
                content=summary_content,
            )
        )

        # 添加最近消息
        compressed.extend(recent)

        logger.info(f"上下文压缩完成: {len(messages)} → {len(compressed)} 条消息")

        return compressed

    async def _summarize_messages(self, older: List[ChatMessage]) -> MessageSummary:
        """
        使用 LLM 生成结构化摘要

        Args:
            older: 需要摘要的消息列表

        Returns:
            MessageSummary 结构
        """
        if not older:
            return MessageSummary(
                messages_count=0,
                time_range="无历史",
                summary="无历史消息",
                key_points=[],
                decisions=[],
                pending_topics=[],
            )

        if not self.provider:
            logger.warning("No LLM provider, using basic summarization")
            return self._basic_summary(older)

        # 构建摘要提示
        conversation_text = self._format_conversation(older)

        summary_prompt = f"""请分析以下对话历史，生成结构化摘要。

要求:
1. 提取关键讨论点和决定
2. 识别未完成的话题或待处理事项
3. 摘要要简洁准确

对话历史:
{conversation_text}

请以 JSON 格式输出:
{{
    "summary": "一段话总结对话主旨",
    "key_points": ["要点1", "要点2", "要点3"],
    "decisions": ["决定1", "决定2"],
    "pending_topics": ["待处理话题1", "待处理话题2"],
    "time_range": "时间范围描述"
}}"""

        try:
            resp = await self.provider.chat(
                messages=[ChatMessage(role="user", content=summary_prompt)],
                system="你是一个对话分析助手，擅长提取关键信息。",
                max_tokens=self.summary_max_tokens,
            )

            import json

            text = resp.text.strip()

            # 尝试解析 JSON
            try:
                # 尝试直接解析
                data = json.loads(text)
            except json.JSONDecodeError:
                # 尝试提取 JSON 块
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    data = json.loads(text[start:end])
                else:
                    raise ValueError("No JSON found in response")

            return MessageSummary(
                messages_count=len(older),
                time_range=data.get("time_range", "最近对话"),
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                decisions=data.get("decisions", []),
                pending_topics=data.get("pending_topics", []),
            )

        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return self._basic_summary(older)

    def _basic_summary(self, older: List[ChatMessage]) -> MessageSummary:
        """基础摘要（当 LLM 不可用时）"""
        if not older:
            return MessageSummary(
                messages_count=0,
                time_range="无",
                summary="无历史消息",
                key_points=[],
                decisions=[],
                pending_topics=[],
            )

        # 简单统计
        user_msgs = [m for m in older if m.role == "user"]
        assistant_msgs = [m for m in older if m.role == "assistant"]

        preview = user_msgs[0].content[:100] if user_msgs else ""
        if len(user_msgs) > 1 and len(preview) > 50:
            preview = preview[:50] + "..."

        return MessageSummary(
            messages_count=len(older),
            time_range="历史对话",
            summary=f"包含 {len(user_msgs)} 条用户消息和 {len(assistant_msgs)} 条助手消息",
            key_points=[f"首条用户消息: {preview}"],
            decisions=[],
            pending_topics=["未分类"],
        )

    def _format_conversation(self, messages: List[ChatMessage]) -> str:
        """格式化对话为文本"""
        lines = []
        for msg in messages:
            role = msg.role.upper()
            content = msg.content[:500] if msg.content else ""
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)

    def get_stats(self, messages: List[ChatMessage]) -> dict:
        """获取消息统计"""
        return {
            "total": len(messages),
            "user": len([m for m in messages if m.role == "user"]),
            "assistant": len([m for m in messages if m.role == "assistant"]),
            "system": len([m for m in messages if m.role == "system"]),
            "should_compress": len(messages) >= self.compress_threshold,
        }
