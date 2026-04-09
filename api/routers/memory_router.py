# api/routers/memory_router.py
# 记忆管理 API 路由

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException

from memory.vector_store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/memory", tags=["memory"])


def get_vector_store() -> VectorStore:
    return VectorStore(db_path="./data/memory")


@router.get("/")
async def get_memories(
    owner: Optional[str] = None,
    scope: Optional[str] = "memory",
    limit: int = 100,
):
    """获取记忆列表"""
    try:
        vs = get_vector_store()
        memories = await vs.list_memories(owner=owner, scope=scope, limit=limit)
        return {
            "success": True,
            "memories": memories,
            "total": len(memories),
        }
    except Exception as e:
        logger.error(f"Failed to list memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_memories(
    query: str,
    owner: Optional[str] = None,
    top_k: int = 10,
):
    """搜索记忆"""
    try:
        vs = get_vector_store()
        results = await vs.search(
            query=query,
            owner=owner,
            top_k=top_k,
        )
        return {
            "success": True,
            "results": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"Failed to search memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def add_memory(
    text: str,
    session_id: str,
    owner: Optional[str] = None,
    source: str = "manual",
    metadata: Optional[dict] = None,
    ttl_seconds: int = 0,
):
    """添加记忆"""
    try:
        vs = get_vector_store()
        memory_id = await vs.add(
            text=text,
            session_id=session_id,
            owner=owner,
            source=source,
            metadata=metadata,
            ttl_seconds=ttl_seconds,
        )
        return {
            "success": True,
            "memory_id": memory_id,
        }
    except Exception as e:
        logger.error(f"Failed to add memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """删除记忆"""
    try:
        vs = get_vector_store()
        success = await vs.delete(memory_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_memory_stats():
    """获取记忆统计"""
    try:
        vs = get_vector_store()
        total = await vs.count()

        stats = {
            "total": total,
            "by_owner": await vs.get_stats_by_owner(),
        }
        return {
            "success": True,
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_memories(owner: Optional[str] = None):
    """清除记忆"""
    try:
        vs = get_vector_store()
        count = await vs.clear(owner=owner)
        return {
            "success": True,
            "cleared_count": count,
        }
    except Exception as e:
        logger.error(f"Failed to clear memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
