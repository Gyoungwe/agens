# installer/skill_installer.py

import logging
import shutil
import httpx
from pathlib import Path
from typing import List, Optional
from core.skill_registry import SKILLS_DIR

logger = logging.getLogger(__name__)

CLAWHUB_API = "https://api.clawhub.io/v1"


class SkillInstaller:
    """技能安装器，支持从 ClawHub 搜索和安装"""

    def __init__(self, registry):
        self.registry = registry

    async def search(self, query: str) -> list[dict]:
        """搜索 ClawHub 公开技能库"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{CLAWHUB_API}/search", params={"q": query, "limit": 10}
                )
                resp.raise_for_status()
                return resp.json().get("skills", [])
        except Exception as e:
            logger.warning(f"ClawHub 搜索失败，使用本地模拟数据: {e}")
            return self._mock_search(query)

    def _mock_search(self, query: str) -> list[dict]:
        """离线模拟搜索结果"""
        mock_db = [
            {
                "skill_id": "github_api",
                "name": "GitHub API",
                "description": "操作 GitHub 仓库、Issues、PR",
                "version": "2.1.0",
                "author": "clawhub-official",
                "tags": ["github", "git", "devops"],
                "downloads": 1240,
            },
            {
                "skill_id": "weather",
                "name": "天气查询",
                "description": "查询全球城市实时天气和预报",
                "version": "1.3.0",
                "author": "community",
                "tags": ["weather", "api"],
                "downloads": 890,
            },
            {
                "skill_id": "pdf_reader",
                "name": "PDF 阅读器",
                "description": "解析 PDF 文件，提取文字和结构",
                "version": "1.0.0",
                "author": "community",
                "tags": ["pdf", "document", "research"],
                "downloads": 560,
            },
        ]
        return [
            s
            for s in mock_db
            if query.lower() in s["name"].lower()
            or query.lower() in s["description"].lower()
            or any(query.lower() in t for t in s["tags"])
        ]

    async def install(
        self, skill_id: str, agent_ids: Optional[List[str]] = None
    ) -> bool:
        """安装指定技能"""
        target_dir = SKILLS_DIR / skill_id
        if target_dir.exists():
            logger.warning(f"技能 [{skill_id}] 已存在，执行热重载")
            self.registry.reload(skill_id)
            return True

        try:
            downloaded = await self._download_from_clawhub(skill_id, target_dir)
            if not downloaded:
                self._scaffold(skill_id, target_dir, agent_ids or [])
            self.registry._register_from_dir(target_dir)
            logger.info(f"✅ 技能 [{skill_id}] 安装成功")
            return True
        except Exception as e:
            logger.error(f"❌ 技能 [{skill_id}] 安装失败: {e}")
            if target_dir.exists():
                shutil.rmtree(target_dir)
            return False

    async def _download_from_clawhub(self, skill_id: str, target_dir: Path) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{CLAWHUB_API}/skills/{skill_id}/download")
                if resp.status_code == 404:
                    return False
                resp.raise_for_status()
                import zipfile, io

                target_dir.mkdir(parents=True)
                with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                    z.extractall(target_dir)
                return True
        except Exception:
            return False

    def _scaffold(self, skill_id: str, target_dir: Path, agent_ids: List[str]):
        target_dir.mkdir(parents=True)
        agents_str = "[" + ", ".join(agent_ids) + "]" if agent_ids else "[]"

        (target_dir / "SKILL.md").write_text(
            f"""---
skill_id:    {skill_id}
name:        {skill_id}
description: （请填写技能描述）
version:     1.0.0
author:      local
tags:        []
agents:      {agents_str}
enabled:     true
source:      local
---

## {skill_id}

（请填写技能说明）
""",
            encoding="utf-8",
        )

        (target_dir / "skill.py").write_text(
            f"""# skills/{skill_id}/skill.py

from core.base_skill import BaseSkill, SkillInput
from typing import Any


class Skill(BaseSkill):

    skill_id    = "{skill_id}"
    name        = "{skill_id}"
    description = "（请填写描述）"
    version     = "1.0.0"
    tags        = []

    async def run(self, input_data: SkillInput) -> Any:
        return f"技能 {skill_id} 收到指令: {{input_data.instruction}}"
""",
            encoding="utf-8",
        )
        logger.info(f"📝 已生成技能脚手架: {target_dir}")

    def uninstall(self, skill_id: str, delete_files: bool = False):
        self.registry.uninstall(skill_id)
        if delete_files:
            skill_dir = SKILLS_DIR / skill_id
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
                logger.info(f"🗑️ 已删除技能文件: {skill_dir}")
