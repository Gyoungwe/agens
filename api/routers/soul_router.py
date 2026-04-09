# api/routers/soul_router.py
# Soul 文档 API 路由

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

from core.soul_parser import SoulParser, SoulDocument, SoulMeta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/soul", tags=["soul"])

_soul_parser: Optional[SoulParser] = None


def get_soul_parser() -> SoulParser:
    global _soul_parser
    if _soul_parser is None:
        _soul_parser = SoulParser()
    return _soul_parser


@router.get("/list")
async def list_soul_files():
    """列出所有 Soul 文件"""
    try:
        parser = get_soul_parser()
        agents = parser.list_agents()
        return {
            "success": True,
            "agents": agents,
            "total": len(agents),
        }
    except Exception as e:
        logger.error(f"Failed to list souls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def get_soul(agent_id: str):
    """获取 Soul 文档"""
    try:
        parser = get_soul_parser()
        doc = parser.parse_file(agent_id)

        if not doc:
            return {
                "success": True,
                "exists": False,
                "agent_id": agent_id,
            }

        return {
            "success": True,
            "exists": True,
            "agent_id": agent_id,
            "meta": doc.meta.to_dict(),
            "body": doc.body,
        }
    except Exception as e:
        logger.error(f"Failed to get soul {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}")
async def save_soul(agent_id: str, data: dict):
    """保存 Soul 文档"""
    try:
        parser = get_soul_parser()

        meta_dict = data.get("meta", {})
        body = data.get("body", "")

        soul_meta = SoulMeta.from_dict(meta_dict)
        new_doc = SoulDocument(meta=soul_meta, body=body)

        old_doc = parser.parse_file(agent_id)
        diff = None
        if old_doc:
            diff = parser.diff(old_doc, new_doc)
            if diff.is_empty():
                return {
                    "success": True,
                    "changed": False,
                    "message": "No changes detected",
                }

        file_path = parser.write_file(agent_id, new_doc)

        return {
            "success": True,
            "changed": True,
            "file_path": file_path,
            "diff": {
                "added": diff.added if diff else {},
                "removed": diff.removed if diff else {},
                "modified": diff.modified if diff else {},
                "body_changed": diff.body_changed if diff else False,
                "summary": diff.summary if diff else "",
            }
            if diff
            else None,
        }
    except Exception as e:
        logger.error(f"Failed to save soul {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/backup")
async def create_soul_backup(agent_id: str):
    """手动创建 Soul 备份"""
    try:
        parser = get_soul_parser()
        soul_path = parser.get_soul_path(agent_id)

        if not soul_path:
            raise HTTPException(
                status_code=404, detail=f"Agent {agent_id} has no soul file"
            )

        from pathlib import Path
        from datetime import datetime
        import shutil

        source = Path(soul_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.stem}_manual_{timestamp}{source.suffix}"
        backup_path = parser.snapshot_dir / agent_id / backup_name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup_path)

        return {
            "success": True,
            "backup_path": str(backup_path),
            "backup_name": backup_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to backup soul {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/backups")
async def list_soul_backups(agent_id: str):
    """列出 Soul 备份"""
    try:
        parser = get_soul_parser()
        backups = parser.list_backups(agent_id)
        return {
            "success": True,
            "backups": backups,
            "total": len(backups),
        }
    except Exception as e:
        logger.error(f"Failed to list backups for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/backups/{backup_name}/restore")
async def restore_soul_backup(agent_id: str, backup_name: str):
    """恢复 Soul 备份"""
    try:
        parser = get_soul_parser()
        file_path = parser.restore_backup(agent_id, backup_name)

        doc = parser.parse_file(agent_id)
        return {
            "success": True,
            "file_path": file_path,
            "restored": {
                "meta": doc.meta.to_dict() if doc else {},
                "body": doc.body if doc else "",
            },
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to restore soul {agent_id} from {backup_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}/backups/{backup_name}")
async def delete_soul_backup(agent_id: str, backup_name: str):
    """删除 Soul 备份"""
    try:
        parser = get_soul_parser()
        success = parser.delete_backup(agent_id, backup_name)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Backup {backup_name} not found"
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backup {backup_name} for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
