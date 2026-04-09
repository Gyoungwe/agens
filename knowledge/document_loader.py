# knowledge/document_loader.py

import logging
import re
import httpx
from pathlib import Path
from typing import List, Union
from knowledge.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


class DocumentLoader:
    """文档导入器，支持 URL / PDF / Markdown / 纯文本"""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    async def from_url(
        self,
        url: str,
        agent_ids: List[str] = [],
        topic: str = "general",
    ) -> int:
        """抓取 URL 内容并导入"""
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            raw = resp.text

        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return await self._ingest(text, agent_ids, topic, source=url)

    async def from_markdown(
        self,
        path: Union[str, Path],
        agent_ids: List[str] = [],
        topic: str = "general",
    ) -> int:
        text = Path(path).read_text(encoding="utf-8")
        return await self._ingest(text, agent_ids, topic, source=str(path))

    async def from_pdf(
        self,
        path: Union[str, Path],
        agent_ids: List[str] = [],
        topic: str = "general",
    ) -> int:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("请先安装: pip install pypdf")

        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return await self._ingest(text, agent_ids, topic, source=str(path))

    async def from_text(
        self,
        text: str,
        agent_ids: List[str] = [],
        topic: str = "general",
        source: str = "manual",
    ) -> int:
        return await self._ingest(text, agent_ids, topic, source)

    async def _ingest(
        self,
        text: str,
        agent_ids: List[str],
        topic: str,
        source: str,
    ) -> int:
        chunks = self._split(text)
        if not chunks:
            logger.warning(f"文档内容为空，跳过: {source}")
            return 0

        items = [
            {
                "text": chunk,
                "agent_ids": agent_ids,
                "topic": topic,
                "source": source,
            }
            for chunk in chunks
        ]

        await self.kb.add_batch(items)
        logger.info(f"✅ 导入完成: {len(chunks)} 个 chunk ← {source}")
        return len(chunks)

    @staticmethod
    def _split(text: str) -> list[str]:
        """滑动窗口切块，优先在句号/换行处断开"""
        text = text.strip()
        chunks = []
        start = 0

        while start < len(text):
            end = start + CHUNK_SIZE

            if end >= len(text):
                chunks.append(text[start:].strip())
                break

            boundary = max(
                text.rfind("。", start, end),
                text.rfind("\n", start, end),
                text.rfind(". ", start, end),
            )
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - CHUNK_OVERLAP

        return chunks
