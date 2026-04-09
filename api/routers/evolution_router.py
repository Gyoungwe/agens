# api/routers/evolution_router.py
# Agent 进化审批 API 路由

import logging
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evolution", tags=["evolution"])


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


_evolution_store: List[EvolutionApproval] = []


@router.get("/approvals")
async def list_approvals(status: Optional[str] = None):
    """获取进化审批列表"""
    try:
        if status:
            filtered = [a for a in _evolution_store if a.status == status]
            return {
                "success": True,
                "approvals": [_approval_to_dict(a) for a in filtered],
                "total": len(filtered),
            }
        return {
            "success": True,
            "approvals": [_approval_to_dict(a) for a in _evolution_store],
            "total": len(_evolution_store),
        }
    except Exception as e:
        logger.error(f"Failed to list approvals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request")
async def create_evolution_request(request: dict):
    """创建进化请求"""
    try:
        approval = EvolutionApproval(
            request_id=request.get(
                "request_id",
                f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(_evolution_store)}",
            ),
            agent_id=request["agent_id"],
            changes=request.get("proposed_changes", {}),
            reason=request.get("reason", ""),
            status="pending",
            created_at=datetime.now().isoformat(),
        )
        _evolution_store.append(approval)

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
        approval = _find_approval(request_id)
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
        approval = _find_approval(request_id)
        if not approval:
            raise HTTPException(
                status_code=404, detail=f"Approval {request_id} not found"
            )

        if approval.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Approval {request_id} is not pending"
            )

        approval.status = "approved"
        approval.reviewed_at = datetime.now().isoformat()
        approval.reviewer = "admin"
        approval.comment = comment

        return {
            "success": True,
            "request_id": request_id,
            "status": "approved",
            "reviewed_at": approval.reviewed_at,
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
        approval = _find_approval(request_id)
        if not approval:
            raise HTTPException(
                status_code=404, detail=f"Approval {request_id} not found"
            )

        if approval.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Approval {request_id} is not pending"
            )

        approval.status = "rejected"
        approval.reviewed_at = datetime.now().isoformat()
        approval.reviewer = "admin"
        approval.comment = comment

        return {
            "success": True,
            "request_id": request_id,
            "status": "rejected",
            "reviewed_at": approval.reviewed_at,
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
        global _evolution_store
        original_len = len(_evolution_store)
        _evolution_store = [a for a in _evolution_store if a.request_id != request_id]

        if len(_evolution_store) == original_len:
            raise HTTPException(
                status_code=404, detail=f"Approval {request_id} not found"
            )

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete approval {request_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _find_approval(request_id: str) -> Optional[EvolutionApproval]:
    """查找审批记录"""
    for approval in _evolution_store:
        if approval.request_id == request_id:
            return approval
    return None


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
