# api/routers/evolution_router.py
# Agent 进化审批 API 路由

import logging
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Any
from datetime import datetime
from dataclasses import dataclass
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evolution", tags=["evolution"])

DB_PATH = Path("./data/evolution.db")


@dataclass
class EvolutionRequest:
    """进化请求"""

    agent_id: str
    request_id: str
    proposed_changes: dict
    reason: str
    status: str = "pending"
    created_at: str = ""
    reviewed_at: Optional[str] = None
    reviewer: Optional[str] = None
    review_comment: Optional[str] = None


@dataclass
class EvolutionApproval:
    """进化审批记录"""

    request_id: str
    agent_id: str
    changes: dict
    reason: str
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    reviewer: Optional[str] = None
    comment: Optional[str] = None


class EvolutionStore:
    """SQLite 进化审批持久化存储"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS evolution_approvals (
                    request_id  TEXT PRIMARY KEY,
                    agent_id    TEXT NOT NULL,
                    changes     TEXT NOT NULL DEFAULT '{}',
                    reason      TEXT NOT NULL DEFAULT '',
                    status      TEXT NOT NULL DEFAULT 'pending',
                    created_at  TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewer    TEXT,
                    comment     TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_evolution_agent_id
                    ON evolution_approvals(agent_id);
                CREATE INDEX IF NOT EXISTS idx_evolution_status
                    ON evolution_approvals(status);
                CREATE INDEX IF NOT EXISTS idx_evolution_created_at
                    ON evolution_approvals(created_at DESC);
            """)
        logger.info("✅ Evolution 数据库已就绪")

    def append(self, approval: EvolutionApproval):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evolution_approvals
                (request_id, agent_id, changes, reason, status, created_at, reviewed_at, reviewer, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    approval.request_id,
                    approval.agent_id,
                    json.dumps(approval.changes, ensure_ascii=False),
                    approval.reason,
                    approval.status,
                    approval.created_at,
                    approval.reviewed_at,
                    approval.reviewer,
                    approval.comment,
                ),
            )

    def list_all(self) -> List[EvolutionApproval]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM evolution_approvals ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_approval(row) for row in rows]

    def list_by_status(self, status: str) -> List[EvolutionApproval]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM evolution_approvals WHERE status=? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        return [self._row_to_approval(row) for row in rows]

    def get(self, request_id: str) -> Optional[EvolutionApproval]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM evolution_approvals WHERE request_id=?", (request_id,)
            ).fetchone()
        return self._row_to_approval(row) if row else None

    def update_status(
        self,
        request_id: str,
        status: str,
        reviewer: str = "admin",
        comment: Optional[str] = None,
    ):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE evolution_approvals
                SET status=?, reviewed_at=?, reviewer=?, comment=?
                WHERE request_id=?
            """,
                (status, now, reviewer, comment, request_id),
            )

    def delete(self, request_id: str):
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM evolution_approvals WHERE request_id=?", (request_id,)
            )

    def _row_to_approval(self, row: sqlite3.Row) -> EvolutionApproval:
        return EvolutionApproval(
            request_id=row["request_id"],
            agent_id=row["agent_id"],
            changes=json.loads(row["changes"]),
            reason=row["reason"],
            status=row["status"],
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
            reviewer=row["reviewer"],
            comment=row["comment"],
        )


_store: Optional[EvolutionStore] = None
_kb_inject: Optional[Any] = None  # injected knowledge_base from main app


def set_knowledge_base(kb) -> None:
    global _kb_inject
    _kb_inject = kb


def _get_kb():
    if _kb_inject is not None:
        return _kb_inject
    from knowledge.knowledge_base import KnowledgeBase

    return KnowledgeBase(db_path="./data/knowledge")


def get_store() -> EvolutionStore:
    global _store
    if _store is None:
        _store = EvolutionStore()
    return _store


@router.get("/approvals")
async def list_approvals(status: Optional[str] = None):
    """获取进化审批列表"""
    try:
        store = get_store()
        if status:
            approvals = store.list_by_status(status)
        else:
            approvals = store.list_all()
        return {
            "success": True,
            "approvals": [_approval_to_dict(a) for a in approvals],
            "total": len(approvals),
        }
    except Exception as e:
        logger.error(f"Failed to list approvals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request")
async def create_evolution_request(request: dict):
    """创建进化请求"""
    try:
        store = get_store()
        import uuid

        approval = EvolutionApproval(
            request_id=request.get(
                "request_id",
                f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}",
            ),
            agent_id=request["agent_id"],
            changes=request.get("proposed_changes", {}),
            reason=request.get("reason", ""),
            status="pending",
            created_at=datetime.now().isoformat(),
        )
        store.append(approval)

        return {
            "success": True,
            "request_id": approval.request_id,
            "status": approval.status,
            "created_at": approval.created_at,
        }
    except Exception as e:
        logger.error(f"Failed to create evolution request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals/{request_id}")
async def get_approval(request_id: str):
    """获取审批详情"""
    try:
        store = get_store()
        approval = store.get(request_id)
        if not approval:
            raise HTTPException(
                status_code=404, detail=f"Approval {request_id} not found"
            )

        return {
            "success": True,
            "approval": _approval_to_dict(approval),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get approval {request_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{request_id}/approve")
async def approve_evolution(request_id: str, comment: Optional[str] = None):
    """批准进化请求"""
    try:
        store = get_store()
        approval = store.get(request_id)
        if not approval:
            raise HTTPException(
                status_code=404, detail=f"Approval {request_id} not found"
            )

        if approval.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Approval {request_id} is not pending"
            )

        store.update_status(request_id, "approved", "admin", comment)
        updated = store.get(request_id)

        # After approval: apply changes to knowledge base
        try:
            kb = _get_kb()
            changes = approval.changes
            kind = changes.get("kind", "")
            if kind == "workflow_retrospective" and kb is not None:
                text = (
                    f"Workflow retrospective for goal={changes.get('goal', '')}; "
                    f"dataset={changes.get('dataset', '')}; "
                    f"provider={changes.get('provider_id', 'default')}; "
                    f"trace_id={changes.get('workflow_trace_id', '')}.\n\n"
                    f"{changes.get('summary', '')}"
                )
                await kb.add(
                    text=text,
                    agent_ids=["bio_evolution_agent", "bio_planner_agent"],
                    topic="planning",
                    source="bio_workflow_evolution_approved",
                    owner="bio_evolution_agent",
                    metadata={
                        "workflow_trace_id": changes.get("workflow_trace_id", ""),
                        "session_id": changes.get("session_id", ""),
                        "dataset": changes.get("dataset", ""),
                        "goal": changes.get("goal", ""),
                        "kind": "workflow_retrospective_approved",
                    },
                    scope_id=changes.get("scope_id"),
                )
                logger.info(f"evolution_approved_and_stored request_id={request_id}")
        except Exception as kb_e:
            logger.warning(
                f"approve_kb_store_failed request_id={request_id} error={kb_e}"
            )

        return {
            "success": True,
            "request_id": request_id,
            "status": "approved",
            "reviewed_at": updated.reviewed_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve {request_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{request_id}/reject")
async def reject_evolution(request_id: str, comment: Optional[str] = None):
    """拒绝进化请求"""
    try:
        store = get_store()
        approval = store.get(request_id)
        if not approval:
            raise HTTPException(
                status_code=404, detail=f"Approval {request_id} not found"
            )

        if approval.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Approval {request_id} is not pending"
            )

        store.update_status(request_id, "rejected", "admin", comment)
        updated = store.get(request_id)

        return {
            "success": True,
            "request_id": request_id,
            "status": "rejected",
            "reviewed_at": updated.reviewed_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reject {request_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/approvals/{request_id}")
async def delete_approval(request_id: str):
    """删除审批记录"""
    try:
        store = get_store()
        approval = store.get(request_id)
        if not approval:
            raise HTTPException(
                status_code=404, detail=f"Approval {request_id} not found"
            )

        store.delete(request_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete approval {request_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _approval_to_dict(approval: EvolutionApproval) -> dict:
    """转换审批记录为字典"""
    return {
        "request_id": approval.request_id,
        "agent_id": approval.agent_id,
        "changes": approval.changes,
        "reason": approval.reason,
        "status": approval.status,
        "created_at": approval.created_at,
        "reviewed_at": approval.reviewed_at,
        "reviewer": approval.reviewer,
        "comment": approval.comment,
    }
