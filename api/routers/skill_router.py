# api/routers/skill_router.py
# 技能管理 API 路由

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from core.skill_registry import SkillRegistry
from installer.claude_skill_adapter import (
    ClaudeSkillAdapter,
    create_claude_skill_adapter,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/skills", tags=["skills"])

_skill_adapter: Optional[ClaudeSkillAdapter] = None


def get_skill_adapter() -> ClaudeSkillAdapter:
    global _skill_adapter
    if _skill_adapter is None:
        _skill_adapter = create_claude_skill_adapter()
    return _skill_adapter


@router.get("/")
async def list_skills(agent_id: Optional[str] = None):
    """获取技能列表"""
    try:
        registry = SkillRegistry()
        if agent_id:
            metas = registry.get_for_agent_metadata(agent_id)
            return {
                "success": True,
                "skills": [m.to_dict() for m in metas],
                "total": len(metas),
            }
        else:
            skills = registry.list_all()
            return {
                "success": True,
                "skills": skills,
                "total": len(skills),
            }
    except Exception as e:
        logger.error(f"Failed to list skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """获取技能详情"""
    try:
        registry = SkillRegistry()
        meta = registry.get_metadata(skill_id)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")

        return {
            "success": True,
            "skill": {
                **meta.to_dict(),
                "stats": registry.get_stats(skill_id),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}/stats")
async def get_skill_stats(skill_id: str):
    """获取技能调用统计"""
    try:
        registry = SkillRegistry()
        stats = registry.get_stats(skill_id)
        if not stats:
            raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
        return {"success": True, "stats": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill stats {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/claude")
async def import_claude_skill(schema: dict):
    """导入 Claude Skill（JSON Schema）"""
    try:
        adapter = get_skill_adapter()
        draft_id, draft = adapter.create_draft(schema)

        return {
            "success": True,
            "draft_id": draft_id,
            "preview": {
                "tool_name": draft.tool_name,
                "description": draft.description,
                "parameters": draft.parameters,
                "execute_template": draft.execute_template,
                "warnings": draft.validation_warnings,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to import Claude skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts/{draft_id}")
async def get_skill_draft(draft_id: str):
    """获取技能草稿预览"""
    try:
        adapter = get_skill_adapter()
        preview = adapter.preview_draft(draft_id)
        if not preview:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        return {"success": True, "draft": preview}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/drafts/{draft_id}")
async def update_skill_draft(draft_id: str, updates: dict):
    """更新技能草稿（用户编辑后）"""
    try:
        adapter = get_skill_adapter()
        success = adapter.update_draft(draft_id, updates)
        if not success:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts/{draft_id}/install")
async def install_skill_draft(draft_id: str):
    """安装技能草稿"""
    try:
        adapter = get_skill_adapter()
        result = adapter.install_draft(draft_id)

        if not result.success:
            return {
                "success": False,
                "error": result.error,
                "warnings": result.warnings,
            }

        registry = SkillRegistry()
        registry.reload(result.skill_id)

        return {
            "success": True,
            "skill_id": result.skill_id,
            "warnings": result.warnings,
        }
    except Exception as e:
        logger.error(f"Failed to install draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload/{skill_id}")
async def reload_skill(skill_id: str):
    """热重载技能"""
    try:
        registry = SkillRegistry()
        success = registry.reload_skill(skill_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Skill {skill_id} not found or reload failed"
            )
        return {"success": True, "skill_id": skill_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reload skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload-all")
async def reload_all_skills():
    """热重载所有技能"""
    try:
        registry = SkillRegistry()
        registry.reload_all()
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to reload all skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{skill_id}")
async def uninstall_skill(skill_id: str):
    """卸载技能"""
    try:
        registry = SkillRegistry()
        registry.uninstall(skill_id)
        return {"success": True, "skill_id": skill_id}
    except Exception as e:
        logger.error(f"Failed to uninstall skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable/{skill_id}")
async def enable_skill(skill_id: str):
    """启用技能"""
    try:
        registry = SkillRegistry()
        registry.enable(skill_id)
        return {"success": True, "skill_id": skill_id}
    except Exception as e:
        logger.error(f"Failed to enable skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable/{skill_id}")
async def disable_skill(skill_id: str):
    """禁用技能"""
    try:
        registry = SkillRegistry()
        registry.disable(skill_id)
        return {"success": True, "skill_id": skill_id}
    except Exception as e:
        logger.error(f"Failed to disable skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
