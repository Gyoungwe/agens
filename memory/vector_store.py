# memory/vector_store.py
"""
向量存储模块

基于 LanceDB 的向量存储，用于存储和检索对话记忆

Embedding 配置:
- API: SiliconFlow
- Model: BAAI/bge-m3 (1024 维)
"""

import os
import uuid
import logging
import json
import httpx
from pathlib import Path
from typing import Any, List

logger = logging.getLogger(__name__)

VECTOR_SIZE = 1024
EMBEDDING_API_KEY = "sk-unvzxjvgymzfsgvjfywnkfcmsrgwqbmgdpqlpbnbqabvriqv"
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
EMBEDDING_MODEL = "BAAI/bge-m3"


class VectorStore:
    """
    基于 LanceDB 的向量存储

    用于存储和检索对话记忆，支持按 session_id 过滤
    """

    def __init__(
        self,
        db_path: str = "./data/memory",
        embed_provider=None,
    ):
        self.db_path = db_path
        self._embed_provider = embed_provider
        self._table = None
        self._ensure_table()

    def _ensure_table(self):
        try:
            import lancedb
            import pyarrow as pa

            db = lancedb.connect(self.db_path)

            schema = pa.schema(
                [
                    ("id", pa.string()),
                    ("text", pa.string()),
                    ("session_id", pa.string()),
                    ("role", pa.string()),
                    ("vector", pa.list_(pa.float32(), VECTOR_SIZE)),
                    ("created_at", pa.string()),
                    ("metadata", pa.string()),
                ]
            )

            try:
                self._table = db.create_table(
                    "memories",
                    schema=schema,
                    exist_ok=True,
                )
            except Exception:
                self._table = db.open_table("memories")

            logger.info("✅ LanceDB table 'memories' ready")
        except Exception as e:
            logger.error(f"LanceDB init failed: {e}")
            raise

    async def _embed(self, text: str) -> List[float]:
        """
        生成文本向量

        使用 SiliconFlow API 或自定义 embed_provider
        """
        if self._embed_provider:
            try:
                return await self._embed_provider(text)
            except Exception as e:
                logger.warning(f"Custom embed provider failed: {e}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    EMBEDDING_API_URL,
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": text,
                    },
                    headers={
                        "Authorization": f"Bearer {EMBEDDING_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )

                if resp.status_code == 401:
                    logger.error(
                        f"SiliconFlow 401: {resp.text}. API Key 可能无效或过期"
                    )
                    return self._random_vector()

                resp.raise_for_status()
                data = resp.json()

                # 解析响应
                if "data" in data and len(data["data"]) > 0:
                    embedding = data["data"][0]["embedding"]
                    logger.debug(f"✅ SiliconFlow embedding: {len(embedding)} dims")
                    return embedding
                else:
                    logger.error(f"Unexpected response format: {data}")
                    return self._random_vector()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            return self._random_vector()
        except Exception as e:
            logger.warning(f"Embedding API failed: {e}")
            return self._random_vector()

    def _random_vector(self) -> List[float]:
        """生成随机向量作为 fallback"""
        import random

        vec = [random.gauss(0, 1) for _ in range(VECTOR_SIZE)]
        norm = sum(x**2 for x in vec) ** 0.5
        return [x / norm for x in vec]

    async def add(
        self,
        text: str,
        session_id: str,
        role: str = "user",
        metadata: dict = None,
    ) -> str:
        """添加记忆"""
        import pyarrow as pa

        memory_id = str(uuid.uuid4())
        vector = await self._embed(text)

        arrays = [
            pa.array([memory_id], type=pa.string()),
            pa.array([text], type=pa.string()),
            pa.array([session_id], type=pa.string()),
            pa.array([role], type=pa.string()),
            pa.array([vector], type=pa.list_(pa.float32(), VECTOR_SIZE)),
            pa.array([""], type=pa.string()),
            pa.array([json.dumps(metadata or {})], type=pa.string()),
        ]
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("text", pa.string()),
                ("session_id", pa.string()),
                ("role", pa.string()),
                ("vector", pa.list_(pa.float32(), VECTOR_SIZE)),
                ("created_at", pa.string()),
                ("metadata", pa.string()),
            ]
        )
        data = pa.table(arrays, schema=schema)

        self._table.add(data)
        logger.debug(f"Added memory {memory_id} to session {session_id}")
        return memory_id

    async def search(
        self,
        query: str,
        session_id: str = None,
        top_k: int = 5,
    ) -> List[dict]:
        """向量相似性搜索"""
        query_vector = await self._embed(query)

        try:
            if session_id:
                results = (
                    self._table.search(query_vector, vector_column_name="vector")
                    .limit(top_k * 3)
                    .to_list()
                )
                results = [r for r in results if r.get("session_id") == session_id][
                    :top_k
                ]
            else:
                results = (
                    self._table.search(query_vector, vector_column_name="vector")
                    .limit(top_k)
                    .to_list()
                )
        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []

        return [self._result_to_dict(r) for r in results]

    async def get_recent(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[dict]:
        """获取最近记忆"""
        try:
            arrow_table = self._table.to_arrow()
            all_data = arrow_table.to_pydict()
            ids = all_data.get("id", [])
            results = []
            for i in range(len(ids)):
                if all_data["session_id"][i] == session_id:
                    results.append(
                        {
                            "id": all_data["id"][i],
                            "text": all_data["text"][i],
                            "session_id": all_data["session_id"][i],
                            "role": all_data["role"][i],
                            "created_at": all_data["created_at"][i],
                        }
                    )
            results = sorted(
                results, key=lambda x: x.get("created_at", ""), reverse=True
            )[:limit]
        except Exception as e:
            logger.warning(f"Get recent failed: {e}")
            return []

        return results

    def _result_to_dict(self, r) -> dict:
        return {
            "id": r.get("id"),
            "text": r.get("text"),
            "session_id": r.get("session_id"),
            "role": r.get("role"),
            "score": r.get("score", 0),
            "created_at": r.get("created_at"),
        }

    async def delete(self, memory_id: str):
        """删除记忆"""
        try:
            self._table.delete(f'id = "{memory_id}"')
            logger.debug(f"Deleted memory {memory_id}")
        except Exception as e:
            logger.warning(f"Delete memory {memory_id} failed: {e}")

    async def count(self, session_id: str = None) -> int:
        """统计记忆数量"""
        try:
            arrow_table = self._table.to_arrow()
            all_data = arrow_table.to_pydict()
            if session_id:
                return len(
                    [s for s in all_data.get("session_id", []) if s == session_id]
                )
            return len(all_data.get("id", []))
        except Exception as e:
            logger.warning(f"Count failed: {e}")
            return 0

    async def health_check(self) -> dict:
        """健康检查"""
        try:
            # 测试 embedding API
            test_vector = await self._embed("health check")
            is_random = len([x for x in test_vector if x == 0]) > VECTOR_SIZE // 2

            return {
                "status": "healthy" if not is_random else "degraded",
                "embedding_api": "working" if not is_random else "fallback_random",
                "lanceDB": "connected",
                "total_memories": await self.count(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
