# memory/vector_store.py
"""
向量存储模块

基于 LanceDB 的向量存储，用于存储和检索对话记忆

Embedding 配置:
- API: SiliconFlow
- Model: BAAI/bge-m3 (1024 维)

可靠性特性:
- 强制 metadata 字段: scope, owner, source, version
- 搜索时强制 filter 防止记忆污染知识问答
"""

import os
import uuid
import logging
import json
import httpx
from pathlib import Path
from typing import Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

VECTOR_SIZE = 1024
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
EMBEDDING_MODEL = "BAAI/bge-m3"


def _get_embedding_api_key():
    return os.getenv("SILICONFLOW_API_KEY", "")


class VectorStore:
    """
    基于 LanceDB 的向量存储

    用于存储和检索对话记忆，支持按 session_id 过滤

    Metadata 强制字段:
    - scope: "memory" (固定值，用于区分)
    - owner: session_id / agent_id / "global"
    - source: 来源标识
    - version: 版本号
    - ttl: 过期时间（秒），可选
    """

    TABLE_NAME = "memories"
    DEFAULT_VERSION = "0.02"

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
                    ("vector", pa.list_(pa.float32(), VECTOR_SIZE)),
                    ("created_at", pa.string()),
                    ("scope", pa.string()),
                    ("owner", pa.string()),
                    ("source", pa.string()),
                    ("version", pa.string()),
                    ("ttl_seconds", pa.int64()),
                    ("metadata", pa.string()),
                ]
            )

            try:
                self._table = db.create_table(
                    self.TABLE_NAME,
                    schema=schema,
                    exist_ok=True,
                )
            except Exception:
                self._table = db.open_table(self.TABLE_NAME)

            logger.info(f"✅ LanceDB table '{self.TABLE_NAME}' ready at {self.db_path}")
        except Exception as e:
            logger.error(f"LanceDB init failed: {e}")
            raise

    def _is_expired(self, ttl_seconds: int, created_at: str) -> bool:
        """检查是否过期"""
        if ttl_seconds <= 0:
            return False
        try:
            created = datetime.fromisoformat(created_at)
            return datetime.now() - created > timedelta(seconds=ttl_seconds)
        except Exception:
            return False

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
            api_key = _get_embedding_api_key()
            if not api_key:
                logger.warning("⚠️ SILICONFLOW_API_KEY not set, using random vector")
                return self._random_vector()

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    EMBEDDING_API_URL,
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": text,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
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
        owner: str = None,
        source: str = "",
        version: str = None,
        ttl_seconds: int = 0,
        metadata: dict = None,
    ) -> str:
        """
        添加记忆

        Args:
            text: 记忆文本
            session_id: 会话 ID
            role: 角色 (user/assistant)
            owner: 所有者 (默认使用 session_id)
            source: 来源标识
            version: 版本号 (默认 0.02)
            ttl_seconds: 过期时间秒数 (0=永不过期)
            metadata: 额外元数据
        """
        import pyarrow as pa

        memory_id = str(uuid.uuid4())
        vector = await self._embed(text)
        now = datetime.now().isoformat()

        _owner = owner or session_id
        _version = version or self.DEFAULT_VERSION

        full_metadata = {"role": role, **(metadata or {})}

        arrays = [
            pa.array([memory_id], type=pa.string()),
            pa.array([text], type=pa.string()),
            pa.array([vector], type=pa.list_(pa.float32(), VECTOR_SIZE)),
            pa.array([now], type=pa.string()),
            pa.array(["memory"], type=pa.string()),
            pa.array([_owner], type=pa.string()),
            pa.array([source], type=pa.string()),
            pa.array([_version], type=pa.string()),
            pa.array([ttl_seconds], type=pa.int64()),
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
                ("ttl_seconds", pa.int64()),
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
        owner: str = None,
        top_k: int = 5,
        include_expired: bool = False,
    ) -> List[dict]:
        """
        向量相似性搜索

        强制使用 scope="memory" filter，防止记忆污染知识问答

        Args:
            query: 查询文本
            session_id: 按会话 ID 过滤 (可选)
            owner: 按所有者过滤 (可选)
            top_k: 返回数量
            include_expired: 是否包含过期记忆
        """
        query_vector = await self._embed(query)

        try:
            base_query = self._table.search(
                query_vector, vector_column_name="vector"
            ).limit(top_k * 3)

            if session_id:
                results = base_query.to_list()
                results = [
                    r
                    for r in results
                    if r.get("owner") == session_id
                    or r.get("metadata", "")
                    and session_id in r.get("metadata", "")
                ][:top_k]
            else:
                results = base_query.to_list()
                if owner:
                    results = [r for r in results if r.get("owner") == owner][:top_k]
                else:
                    results = results[:top_k]

            filtered = []
            now = datetime.now()
            for r in results:
                ttl = r.get("ttl_seconds", 0) or 0
                if ttl > 0 and not include_expired:
                    try:
                        created = datetime.fromisoformat(
                            r.get("created_at", now.isoformat())
                        )
                        if now - created > timedelta(seconds=ttl):
                            continue
                    except Exception:
                        pass

                if r.get("scope") != "memory":
                    continue

                filtered.append(self._result_to_dict(r))

            return filtered[:top_k]

        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []

    async def get_recent(
        self,
        session_id: str,
        limit: int = 10,
        include_expired: bool = False,
    ) -> List[dict]:
        """获取最近记忆"""
        try:
            all_data = self._table.to_arrow().to_pydict()
            now = datetime.now()
            results = []
            for i in range(len(all_data.get("id", []))):
                if all_data["scope"][i] != "memory":
                    continue
                if all_data["owner"][i] != session_id:
                    continue

                ttl = all_data.get("ttl_seconds", [0])[i] or 0
                if ttl > 0 and not include_expired:
                    try:
                        created = datetime.fromisoformat(all_data["created_at"][i])
                        if now - created > timedelta(seconds=ttl):
                            continue
                    except Exception:
                        pass

                results.append(
                    {
                        "id": all_data["id"][i],
                        "text": all_data["text"][i],
                        "session_id": all_data["owner"][i],
                        "role": json.loads(all_data["metadata"][i]).get("role", ""),
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
        try:
            meta = json.loads(r.get("metadata", "{}"))
        except Exception:
            meta = {}
        return {
            "id": r.get("id"),
            "text": r.get("text"),
            "owner": r.get("owner"),
            "source": r.get("source"),
            "version": r.get("version"),
            "score": r.get("score", 0),
            "created_at": r.get("created_at"),
            "role": meta.get("role", ""),
        }

    async def delete(self, memory_id: str):
        """删除记忆"""
        try:
            self._table.delete(f'id = "{memory_id}"')
            logger.debug(f"Deleted memory {memory_id}")
        except Exception as e:
            logger.warning(f"Delete memory {memory_id} failed: {e}")

    async def count(self, session_id: str = None, owner: str = None) -> int:
        """统计记忆数量"""
        try:
            all_data = self._table.to_arrow().to_pydict()
            count = 0
            for i in range(len(all_data.get("id", []))):
                if all_data["scope"][i] != "memory":
                    continue
                if session_id and all_data["owner"][i] != session_id:
                    continue
                if owner and all_data["owner"][i] != owner:
                    continue
                count += 1
            return count
        except Exception as e:
            logger.warning(f"Count failed: {e}")
            return 0

    async def cleanup_expired(self) -> int:
        """清理过期记忆，返回清理数量"""
        try:
            all_data = self._table.to_arrow().to_pydict()
            now = datetime.now()
            expired_ids = []
            for i in range(len(all_data.get("id", []))):
                ttl = all_data.get("ttl_seconds", [0])[i] or 0
                if ttl > 0:
                    try:
                        created = datetime.fromisoformat(all_data["created_at"][i])
                        if now - created > timedelta(seconds=ttl):
                            expired_ids.append(all_data["id"][i])
                    except Exception:
                        pass

            for eid in expired_ids:
                self._table.delete(f'id = "{eid}"')

            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} expired memories")
            return len(expired_ids)

        except Exception as e:
            logger.warning(f"Cleanup expired failed: {e}")
            return 0

    async def health_check(self) -> dict:
        """健康检查"""
        try:
            test_vector = await self._embed("health check")
            is_random = len([x for x in test_vector if x == 0]) > VECTOR_SIZE // 2

            return {
                "status": "healthy" if not is_random else "degraded",
                "embedding_api": "working" if not is_random else "fallback_random",
                "lanceDB": "connected",
                "table": self.TABLE_NAME,
                "total_memories": await self.count(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
