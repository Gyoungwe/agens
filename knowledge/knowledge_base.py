# knowledge/knowledge_base.py
"""
向量知识库模块

基于 LanceDB 的 RAG 向量知识库，支持 URL / PDF / Markdown 导入

可靠性特性:
- 强制 metadata 字段: scope, owner, source, version
- 与 memory 使用不同表名隔离
- 搜索时强制 filter 防止知识污染记忆问答
"""

import logging
import os
import random
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

logger = logging.getLogger(__name__)

VECTOR_SIZE = 1024
COLLECTION_NAME = "agent_knowledge"


class KnowledgeBase:
    """
    向量知识库，基于 LanceDB。

    核心能力：
    1. 按 agent_id + topic 过滤存储
    2. 语义检索，返回最相关的 K 条
    3. 支持 URL / PDF / Markdown 导入

    Metadata 强制字段:
    - scope: "knowledge" (固定值，用于区分)
    - owner: agent_ids 或 "global"
    - source: 来源 (url/file/manual)
    - version: 版本号
    """

    TABLE_NAME = "agent_knowledge"
    DEFAULT_VERSION = "0.02"

    def __init__(
        self,
        embed_provider=None,
        db_path: str = "./data/knowledge",
    ):
        self._embed_provider = embed_provider
        self._db_path = db_path
        self._lance_table = None
        self._in_memory = []
        self._ready = False
        self._init_lance()

    def _init_lance(self):
        try:
            import lancedb
            import pyarrow as pa

            db = lancedb.connect(self._db_path)
            schema = pa.schema(
                [
                    ("id", pa.string()),
                    ("text", pa.string()),
                    ("vector", pa.list_(pa.float32(), VECTOR_SIZE)),
                    ("created_at", pa.string()),
                    ("scope", pa.string()),
                    ("owner", pa.string()),
                    ("source", pa.string()),
                    ("version", pa.string()),
                    ("topic", pa.string()),
                    ("metadata", pa.string()),
                ]
            )

            try:
                self._lance_table = db.create_table(
                    self.TABLE_NAME,
                    schema=schema,
                    exist_ok=True,
                )
            except Exception:
                self._lance_table = db.open_table(self.TABLE_NAME)

            logger.info(f"✅ LanceDB knowledge base ready at {self._db_path}")
            self._ready = True
        except Exception as e:
            logger.warning(f"⚠️ LanceDB init failed: {e}, using in-memory fallback")
            self._in_memory = []
            self._ready = True

    async def init(self):
        """初始化后端，LanceDB 同步初始化，无需额外操作"""
        self._ready = True

    async def add(
        self,
        text: str,
        agent_ids: List[str] = None,
        topic: str = "general",
        source: str = "",
        owner: str = None,
        version: str = None,
        metadata: dict = None,
    ) -> str:
        """
        写入一条知识，返回 point_id

        Args:
            text: 知识文本
            agent_ids: 可访问的 Agent ID 列表
            topic: 主题分类
            source: 来源 (url/file/manual)
            owner: 所有者 (默认使用 agent_ids JSON)
            version: 版本号 (默认 0.02)
            metadata: 额外元数据
        """
        import json

        if agent_ids is None:
            agent_ids = []
        if metadata is None:
            metadata = {}

        point_id = str(uuid4())
        vector = await self._embed(text)
        now = datetime.now().isoformat()

        _owner = owner or json.dumps(agent_ids)
        _version = version or self.DEFAULT_VERSION

        full_metadata = {"agent_ids": agent_ids, "topic": topic, **(metadata or {})}

        if self._lance_table is not None:
            arrays = [
                pa.array([point_id], type=pa.string()),
                pa.array([text], type=pa.string()),
                pa.array([vector], type=pa.list_(pa.float32(), VECTOR_SIZE)),
                pa.array([now], type=pa.string()),
                pa.array(["knowledge"], type=pa.string()),
                pa.array([_owner], type=pa.string()),
                pa.array([source], type=pa.string()),
                pa.array([_version], type=pa.string()),
                pa.array([topic], type=pa.string()),
                pa.array([json.dumps(full_metadata)], type=pa.string()),
            ]
            schema = pa.schema(
                [
                    ("id", pa.string()),
                    ("text", pa.string()),
                    ("vector", pa.list_(pa.float32(), VECTOR_SIZE)),
                    ("created_at", pa.string()),
                    ("scope", pa.string()),
                    ("owner", pa.string()),
                    ("source", pa.string()),
                    ("version", pa.string()),
                    ("topic", pa.string()),
                    ("metadata", pa.string()),
                ]
            )
            data = pa.table(arrays, schema=schema)
            self._lance_table.add(data)
        else:
            self._in_memory.append(
                {
                    "id": point_id,
                    "text": text,
                    "vector": vector,
                    "created_at": now,
                    "scope": "knowledge",
                    "owner": _owner,
                    "source": source,
                    "version": _version,
                    "topic": topic,
                    "metadata": full_metadata,
                }
            )

        return point_id

    async def add_batch(self, items: List[dict]) -> List[str]:
        """批量写入"""
        ids = []
        for item in items:
            point_id = await self.add(
                text=item["text"],
                agent_ids=item.get("agent_ids", []),
                topic=item.get("topic", "general"),
                source=item.get("source", ""),
                owner=item.get("owner"),
                version=item.get("version"),
                metadata=item.get("metadata", {}),
            )
            ids.append(point_id)
        logger.info(f"📦 Batch wrote {len(ids)} knowledge entries")
        return ids

    async def search(
        self,
        query: str,
        agent_id: str,
        topic: str = None,
        top_k: int = 5,
        min_score: float = 0.6,
    ) -> list:
        """
        语义检索

        强制使用 scope="knowledge" filter，防止知识污染记忆问答

        Args:
            query: 查询文本
            agent_id: 当前 Agent ID（用于权限过滤）
            topic: 按主题过滤 (可选)
            top_k: 返回数量
            min_score: 最低相似度分数
        """
        try:
            vector = await self._embed(query)
        except Exception:
            return []

        if self._lance_table is not None:
            return await self._search_lance(vector, agent_id, topic, top_k, min_score)
        else:
            return self._search_in_memory(vector, agent_id, topic, top_k, min_score)

    async def _search_lance(
        self, vector, agent_id: str, topic: str, top_k: int, min_score: float
    ) -> list:
        try:
            import json

            results = (
                self._lance_table.search(vector, vector_column_name="vector")
                .limit(top_k * 3)
                .to_list()
            )

            filtered = []
            for r in results:
                r_scope = r.get("scope", "")
                if r_scope != "knowledge":
                    continue

                r_owner = r.get("owner", "[]")
                try:
                    r_agent_ids = (
                        json.loads(r_owner) if r_owner.startswith("[") else [r_owner]
                    )
                except Exception:
                    r_agent_ids = [r_owner] if r_owner else []

                r_topic = r.get("topic", "")
                r_score = r.get("score", 0)

                if r_score < min_score:
                    continue
                if topic and r_topic != topic:
                    continue
                if (
                    r_agent_ids
                    and "global" not in r_agent_ids
                    and agent_id not in r_agent_ids
                ):
                    continue

                try:
                    meta = json.loads(r.get("metadata", "{}"))
                except Exception:
                    meta = {}

                filtered.append(
                    {
                        "id": r.get("id"),
                        "score": round(r_score, 4),
                        "text": r.get("text", ""),
                        "topic": r_topic,
                        "source": r.get("source", ""),
                        "version": r.get("version", ""),
                        "created_at": r.get("created_at", ""),
                    }
                )

                if len(filtered) >= top_k:
                    break

            return filtered
        except Exception as e:
            logger.warning(f"LanceDB search failed: {e}")
            return []

    def _search_in_memory(
        self, vector, agent_id: str, topic: str, top_k: int, min_score: float
    ) -> list:
        import numpy as np

        def cosine_sim(a, b):
            a = np.array(a)
            b = np.array(b)
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

        results = []
        for item in self._in_memory:
            if item.get("scope") != "knowledge":
                continue
            if topic and item.get("topic") != topic:
                continue

            r_owner = item.get("owner", "[]")
            try:
                r_agent_ids = (
                    json.loads(r_owner)
                    if isinstance(r_owner, str) and r_owner.startswith("[")
                    else [r_owner]
                )
            except Exception:
                r_agent_ids = [r_owner] if r_owner else []

            if (
                r_agent_ids
                and "global" not in r_agent_ids
                and agent_id not in r_agent_ids
            ):
                continue

            score = cosine_sim(vector, item["vector"])
            if score < min_score:
                continue

            results.append(
                {
                    "id": item["id"],
                    "score": round(float(score), 4),
                    "text": item["text"],
                    "topic": item.get("topic", ""),
                    "source": item.get("source", ""),
                    "version": item.get("version", ""),
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def delete(self, point_id: str):
        """删除知识条目"""
        if self._lance_table is not None:
            try:
                self._lance_table.delete(f'id = "{point_id}"')
            except Exception as e:
                logger.warning(f"LanceDB delete failed: {e}")
        else:
            self._in_memory = [x for x in self._in_memory if x["id"] != point_id]

    async def count(self) -> int:
        """统计知识条目数量"""
        if self._lance_table is not None:
            try:
                return len(self._lance_table.to_arrow())
            except Exception:
                return 0
        else:
            return len([x for x in self._in_memory if x.get("scope") == "knowledge"])

    async def _embed(self, text: str) -> list:
        """生成向量"""
        if self._embed_provider:
            resp = await self._embed_provider.embeddings.create(
                model="BAAI/bge-m3",
                input=text,
            )
            return resp.data[0].embedding

        logger.warning("⚠️ Using random vector (development mode)")
        vec = [random.gauss(0, 1) for _ in range(VECTOR_SIZE)]
        norm = sum(x**2 for x in vec) ** 0.5
        return [x / norm for x in vec]
