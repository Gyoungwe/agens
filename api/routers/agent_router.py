# api/routers/agent_router.py
# Agent 管理 API 路由

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

from core.soul_parser import SoulParser, SoulDocument
from core.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])

_soul_parser: Optional[SoulParser] = None


def get_soul_parser() -> SoulParser:
    global _soul_parser
    if _soul_parser is None:
        _soul_parser = SoulParser()
    return _soul_parser


@router.get("/")
async def list_agents():
    """获取 Agent 列表"""
    try:
        parser = get_soul_parser()
        agents = parser.list_agents()

        registry = SkillRegistry()
        all_skills = registry.list_all()

        result = []
        for agent in agents:
            agent_id = agent["agent_id"]
            skills = registry.get_for_agent_metadata(agent_id)
            result.append(
                {
                    **agent,
                    "skill_count": len(skills),
                    "skills": [s.name or s.skill_id for s in skills],
                }
            )

        return {
            "success": True,
            "agents": result,
            "total": len(result),
        }
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """获取 Agent 详情"""
    try:
        parser = get_soul_parser()
        doc = parser.parse_file(agent_id)

        registry = SkillRegistry()
        skills = registry.get_for_agent_metadata(agent_id)

        if doc:
            return {
                "success": True,
                "agent": {
                    "agent_id": agent_id,
                    "meta": doc.meta.to_dict(),
                    "body": doc.body,
                    "skills": [s.to_dict() for s in skills],
                    "has_soul": True,
                },
            }
        else:
            return {
                "success": True,
                "agent": {
                    "agent_id": agent_id,
                    "meta": {},
                    "body": "",
                    "skills": [s.to_dict() for s in skills],
                    "has_soul": False,
                },
            }
    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/soul")
async def get_agent_soul(agent_id: str):
    """获取 Agent Soul 文档"""
    try:
        parser = get_soul_parser()
        doc = parser.parse_file(agent_id)

        if not doc:
            raise HTTPException(
                status_code=404, detail=f"Agent {agent_id} has no soul file"
            )

        return {
            "success": True,
            "soul": {
                "meta": doc.meta.to_dict(),
                "body": doc.body,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent soul {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}/soul")
async def update_agent_soul(agent_id: str, data: dict):
    """更新 Agent Soul 文档"""
    try:
        parser = get_soul_parser()

        meta = data.get("meta", {})
        body = data.get("body", "")

        from core.soul_parser import SoulMeta

        soul_meta = SoulMeta.from_dict(meta)
        doc = SoulDocument(meta=soul_meta, body=body)

        old_doc = parser.parse_file(agent_id)
        diff = None
        if old_doc:
            diff = parser.diff(old_doc, doc)

        file_path = parser.write_file(agent_id, doc)

        result = {
            "success": True,
            "file_path": file_path,
        }

        if diff:
            result["diff"] = {
                "added": diff.added,
                "removed": diff.removed,
                "modified": diff.modified,
                "body_changed": diff.body_changed,
                "summary": diff.summary,
            }

        return result
    except Exception as e:
        logger.error(f"Failed to update agent soul {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/skills")
async def get_agent_skills(agent_id: str):
    """获取 Agent 的技能列表"""
    try:
        registry = SkillRegistry()
        skills = registry.get_for_agent_metadata(agent_id)
        return {
            "success": True,
            "skills": [s.to_dict() for s in skills],
            "total": len(skills),
        }
    except Exception as e:
        logger.error(f"Failed to get agent skills {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/skills/all")
async def get_agent_all_skills(agent_id: str):
    """获取 Agent 可配置的所有技能（含是否已绑定）"""
    try:
        registry = SkillRegistry()
        skills = registry.list_all()
        result = []
        for skill in skills:
            agent_ids = []
            try:
                import json

                agent_ids = json.loads(skill.get("agent_ids") or "[]")
            except Exception:
                agent_ids = []

            result.append(
                {
                    "skill_id": skill.get("skill_id"),
                    "name": skill.get("name", skill.get("skill_id")),
                    "description": skill.get("description", ""),
                    "enabled": bool(skill.get("enabled", 0)),
                    "assigned": (not agent_ids) or (agent_id in agent_ids),
                    "agent_ids": agent_ids,
                }
            )

        return {"success": True, "skills": result, "total": len(result)}
    except Exception as e:
        logger.error(f"Failed to get all skills for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/skills/{skill_id}/assign")
async def assign_skill_to_agent(agent_id: str, skill_id: str):
    """将技能绑定给指定 Agent"""
    try:
        registry = SkillRegistry()
        if not registry.get_metadata(skill_id):
            raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
        registry.assign_to_agent(skill_id, agent_id)
        return {"success": True, "agent_id": agent_id, "skill_id": skill_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign skill {skill_id} to {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/skills/{skill_id}/unassign")
async def unassign_skill_from_agent(agent_id: str, skill_id: str):
    """将技能从指定 Agent 解绑"""
    try:
        registry = SkillRegistry()
        if not registry.get_metadata(skill_id):
            raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
        registry.unassign_from_agent(skill_id, agent_id)
        return {"success": True, "agent_id": agent_id, "skill_id": skill_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unassign skill {skill_id} from {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/backups")
async def list_agent_backups(agent_id: str):
    """获取 Agent Soul 的备份列表"""
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
async def restore_agent_backup(agent_id: str, backup_name: str):
    """恢复 Agent Soul 备份"""
    try:
        parser = get_soul_parser()
        file_path = parser.restore_backup(agent_id, backup_name)
        return {
            "success": True,
            "file_path": file_path,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to restore backup {backup_name} for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/soul/path")
async def get_agent_soul_path(agent_id: str):
    """获取 Agent Soul 文件路径"""
    try:
        parser = get_soul_parser()
        path = parser.get_soul_path(agent_id)
        if not path:
            raise HTTPException(
                status_code=404, detail=f"Agent {agent_id} has no soul file"
            )
        return {
            "success": True,
            "path": path,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get soul path for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
