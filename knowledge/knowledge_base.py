# knowledge/knowledge_base.py

import logging
import os
import random
from typing import Any, Dict, List, Optional
from uuid import uuid4

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
    """

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
                    ("agent_ids", pa.string()),
                    ("topic", pa.string()),
                    ("source", pa.string()),
                    ("metadata", pa.string()),
                    ("vector", pa.list_(pa.float32(), VECTOR_SIZE)),
                    ("created_at", pa.string()),
                ]
            )

            try:
                self._lance_table = db.create_table(
                    COLLECTION_NAME,
                    schema=schema,
                    exist_ok=True,
                )
            except Exception:
                self._lance_table = db.open_table(COLLECTION_NAME)

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
        metadata: dict = None,
    ) -> str:
        """写入一条知识，返回 point_id"""
        if agent_ids is None:
            agent_ids = []
        if metadata is None:
            metadata = {}

        point_id = str(uuid4())
        vector = await self._embed(text)

        if self._lance_table is not None:
            import pyarrow as pa
            import json

            arrays = [
                pa.array([point_id], type=pa.string()),
                pa.array([text], type=pa.string()),
                pa.array([json.dumps(agent_ids)], type=pa.string()),
                pa.array([topic], type=pa.string()),
                pa.array([source], type=pa.string()),
                pa.array([json.dumps(metadata)], type=pa.string()),
                pa.array([vector], type=pa.list_(pa.float32(), VECTOR_SIZE)),
                pa.array([""], type=pa.string()),
            ]
            schema = pa.schema(
                [
                    ("id", pa.string()),
                    ("text", pa.string()),
                    ("agent_ids", pa.string()),
                    ("topic", pa.string()),
                    ("source", pa.string()),
                    ("metadata", pa.string()),
                    ("vector", pa.list_(pa.float32(), VECTOR_SIZE)),
                    ("created_at", pa.string()),
                ]
            )
            data = pa.table(arrays, schema=schema)
            self._lance_table.add(data)
        else:
            self._in_memory.append(
                {
                    "id": point_id,
                    "text": text,
                    "agent_ids": agent_ids,
                    "topic": topic,
                    "source": source,
                    "metadata": metadata,
                    "vector": vector,
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
        """语义检索"""
        try:
            vector = await self._embed(query)
        except Exception:
            return []

        if self._lance_table is not None:
            return await self._search_lance(vector, agent_id, topic, top_k, min_score)
        else:
            return self._search_in_memory(vector, agent_id, topic, top_k)

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
                r_agent_ids = json.loads(r.get("agent_ids", "[]"))
                r_topic = r.get("topic", "")
                r_score = r.get("score", 0)

                if r_score < min_score:
                    continue
                if topic and r_topic != topic:
                    continue
                if r_agent_ids and agent_id not in r_agent_ids:
                    continue

                filtered.append(
                    {
                        "id": r.get("id"),
                        "score": round(r_score, 4),
                        "text": r.get("text", ""),
                        "topic": r_topic,
                        "source": r.get("source", ""),
                    }
                )

                if len(filtered) >= top_k:
                    break

            return filtered
        except Exception as e:
            logger.warning(f"LanceDB search failed: {e}")
            return []

    def _search_in_memory(self, vector, agent_id: str, topic: str, top_k: int) -> list:
        import numpy as np

        def cosine_sim(a, b):
            a = np.array(a)
            b = np.array(b)
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

        results = []
        for item in self._in_memory:
            if topic and item.get("topic") != topic:
                continue
            agent_ids = item.get("agent_ids", [])
            if agent_ids and agent_id not in agent_ids:
                continue

            score = cosine_sim(vector, item["vector"])
            results.append(
                {
                    "id": item["id"],
                    "score": round(float(score), 4),
                    "text": item["text"],
                    "topic": item.get("topic", ""),
                    "source": item.get("source", ""),
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def delete(self, point_id: str):
        if self._lance_table is not None:
            try:
                self._lance_table.delete(f'id = "{point_id}"')
            except Exception as e:
                logger.warning(f"LanceDB delete failed: {e}")
        else:
            self._in_memory = [x for x in self._in_memory if x["id"] != point_id]

    async def count(self) -> int:
        if self._lance_table is not None:
            try:
                return len(self._lance_table.to_arrow())
            except Exception:
                return 0
        else:
            return len(self._in_memory)

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
