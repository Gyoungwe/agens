# core/skill_registry.py
"""
技能注册中心

技能系统参考 Claude Managed Agents SKILL.md 格式

标准化 SKILL.md 格式:
```yaml
---
skill_id: web_search
name: 网页搜索
description: 使用搜索引擎搜索互联网信息
version: 0.02
author: system
tags: [search, internet, research]

# 推荐模型（可选）
model: claude-sonnet-4-6

# 所需工具（可选）
tools:
  - bash
  - read
  - write

# 输入schema（可选）
input:
  type: object
  properties:
    query:
      type: string
      description: 搜索查询词

# 输出schema（可选）
output:
  type: object
  properties:
    results:
      type: array

# 权限要求（可选）
permissions:
  network: true
  filesystem: false
  shell: false

# 代理可用（可选）
agents: [research_agent, executor_agent]

# 是否启用
enabled: true

# 来源
source: local
---

# 技能详细说明

这里可以写更详细的技能描述、使用示例、注意事项等。
Markdown 格式。
```
"""

import sqlite3
import importlib.util
import logging
import json
import re
import yaml
import asyncio
from pathlib import Path
from typing import Type, Dict, List, Optional, Any

from core.base_skill import BaseSkill

logger = logging.getLogger(__name__)

DB_PATH = Path("./data/skills.db")
SKILLS_DIR = Path("./skills")

_POOL_SIZE = 5


class SkillMetadata:
    """
    标准化技能元数据
    参考 Claude Managed Agents SKILL.md 格式
    """

    def __init__(self, data: dict):
        self.skill_id = data.get("skill_id", "")
        self.name = data.get("name", self.skill_id)
        self.description = data.get("description", "")
        self.version = data.get("version", "0.02")
        self.author = data.get("author", "")
        self.tags = data.get("tags", [])

        # 推荐模型
        self.model = data.get("model", None)

        # 所需工具
        self.tools = data.get("tools", [])

        # 输入输出 schema
        self.input_schema = data.get("input", {})
        self.output_schema = data.get("output", {})

        # 权限要求
        self.permissions = data.get("permissions", {})

        # 允许使用的 Agent
        self.agents = data.get("agents", [])

        # 启用状态
        self.enabled = data.get("enabled", True)

        # 来源
        self.source = data.get("source", "local")

        # 详细说明（SKILL.md 的正文部分）
        self.readme = data.get("_readme", "")

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "model": self.model,
            "tools": self.tools,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permissions": self.permissions,
            "agents": self.agents,
            "enabled": self.enabled,
            "source": self.source,
        }

    def matches_agent(self, agent_id: str) -> bool:
        """检查技能是否适用于指定 Agent"""
        if not self.agents:
            return True  # 无限制，所有 Agent 可用
        return agent_id in self.agents

    def requires_network(self) -> bool:
        """是否需要网络权限"""
        return self.permissions.get("network", False)

    def requires_filesystem(self) -> bool:
        """是否需要文件系统权限"""
        return self.permissions.get("filesystem", False)

    def requires_shell(self) -> bool:
        """是否需要 shell 权限"""
        return self.permissions.get("shell", False)


class SkillRegistry:
    """
    技能注册中心

    职责：
    1. 维护 SQLite 技能元数据表
    2. 动态加载 / 卸载技能 Python 类
    3. 按 agent_id 过滤返回可用技能
    4. 热重载（无需重启）
    5. 技能搜索和发现

    可靠性优化：
    - WAL 模式提升并发读性能
    - 共享连接 + 锁减少连接竞争
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, BaseSkill] = {}
        self._meta_cache: List[dict] = []
        self._write_lock = asyncio.Lock()
        self._init_db()
        self._scan_and_register()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                skill_id     TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT,
                version      TEXT,
                author       TEXT,
                tags         TEXT,
                model        TEXT,
                tools        TEXT,
                input_schema TEXT,
                output_schema TEXT,
                permissions  TEXT,
                agent_ids    TEXT,
                enabled      INTEGER DEFAULT 1,
                source       TEXT,
                install_path TEXT,
                installed_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self, "_shared_conn") or self._shared_conn is None:
            self._shared_conn = sqlite3.connect(self.db_path, timeout=30.0)
            self._shared_conn.row_factory = sqlite3.Row
            self._shared_conn.execute("PRAGMA journal_mode=WAL")
        return self._shared_conn

    def _conn(self) -> sqlite3.Connection:
        return self._get_conn()

    # ══════════════════════════════════════════════
    # 扫描 & 注册
    # ══════════════════════════════════════════════

    def _scan_and_register(self):
        if not SKILLS_DIR.exists():
            SKILLS_DIR.mkdir(parents=True)
            logger.info(f"📦 技能目录不存在，已创建: {SKILLS_DIR}")
            return

        count = 0
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            skill_py = skill_dir / "skill.py"
            if skill_md.exists() and skill_py.exists():
                try:
                    self._register_from_dir(skill_dir)
                    count += 1
                except Exception as e:
                    logger.error(f"注册技能 [{skill_dir.name}] 失败: {e}")

        logger.info(f"📦 扫描完成，共注册 {count} 个技能")

    def _register_from_dir(self, skill_dir: Path):
        meta = self._parse_skill_md(skill_dir / "SKILL.md")
        skill_id = meta.get("skill_id", skill_dir.name)

        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO skills
                (skill_id, name, description, version, author,
                 tags, model, tools, input_schema, output_schema,
                 permissions, agent_ids, enabled, source, install_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    skill_id,
                    meta.get("name", skill_id),
                    meta.get("description", ""),
                    meta.get("version", "0.02"),
                    meta.get("author", ""),
                    json.dumps(meta.get("tags", []), ensure_ascii=False),
                    meta.get("model", ""),
                    json.dumps(meta.get("tools", []), ensure_ascii=False),
                    json.dumps(meta.get("input", {}), ensure_ascii=False),
                    json.dumps(meta.get("output", {}), ensure_ascii=False),
                    json.dumps(meta.get("permissions", {}), ensure_ascii=False),
                    json.dumps(meta.get("agents", []), ensure_ascii=False),
                    1 if meta.get("enabled", True) else 0,
                    meta.get("source", "local"),
                    str(skill_dir.resolve()),
                ),
            )
        logger.debug(f"  ✅ 注册技能: [{skill_id}]")

    @staticmethod
    def _parse_skill_md(path: Path) -> dict:
        """
        解析 SKILL.md 文件
        支持 YAML frontmatter 格式
        """
        raw = path.read_text(encoding="utf-8")

        # 提取 YAML frontmatter
        match = re.match(r"^---\n(.*?)\n---(.*)$", raw, re.DOTALL)
        if not match:
            return {}

        frontmatter = match.group(1)
        readme = match.group(2).strip() if match.group(2) else ""

        data = yaml.safe_load(frontmatter) or {}
        data["_readme"] = readme

        return data

    def parse_metadata(self, path: Path) -> SkillMetadata:
        """解析技能元数据为 SkillMetadata 对象"""
        data = self._parse_skill_md(path)
        return SkillMetadata(data)

    # ══════════════════════════════════════════════
    # 技能加载（动态 import）
    # ══════════════════════════════════════════════

    def _load_skill_class(self, skill_id: str) -> Optional[Type[BaseSkill]]:
        row = self._get_row(skill_id)
        if not row:
            return None

        skill_py = Path(row["install_path"]) / "skill.py"
        if not skill_py.exists():
            logger.error(f"技能文件不存在: {skill_py}")
            return None

        spec = importlib.util.spec_from_file_location(f"skill_{skill_id}", skill_py)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        skill_class = getattr(module, "Skill", None)
        if skill_class is None:
            logger.error(f"skill.py 中未找到 Skill 类: {skill_py}")
            return None

        return skill_class

    # ══════════════════════════════════════════════
    # 公开 API
    # ══════════════════════════════════════════════

    def get(self, skill_id: str) -> Optional[BaseSkill]:
        """获取技能实例（带缓存）"""
        if skill_id in self._cache:
            return self._cache[skill_id]

        skill_class = self._load_skill_class(skill_id)
        if skill_class is None:
            return None

        instance = skill_class()
        self._cache[skill_id] = instance
        return instance

    def get_metadata(self, skill_id: str) -> Optional[SkillMetadata]:
        """获取技能元数据（不加载类）"""
        row = self._get_row(skill_id)
        if not row:
            return None

        return SkillMetadata(
            {
                "skill_id": row["skill_id"],
                "name": row["name"],
                "description": row["description"],
                "version": row["version"],
                "author": row["author"],
                "tags": json.loads(row["tags"] or "[]"),
                "model": row["model"],
                "tools": json.loads(row["tools"] or "[]"),
                "input": json.loads(row["input_schema"] or "{}"),
                "output": json.loads(row["output_schema"] or "{}"),
                "permissions": json.loads(row["permissions"] or "{}"),
                "agents": json.loads(row["agent_ids"] or "[]"),
                "enabled": bool(row["enabled"]),
                "source": row["source"],
            }
        )

    def get_for_agent(self, agent_id: str) -> List[BaseSkill]:
        """返回某个 Agent 有权使用的所有技能实例"""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM skills WHERE enabled = 1").fetchall()

        result = []
        for row in rows:
            agent_ids = json.loads(row["agent_ids"] or "[]")
            if not agent_ids or agent_id in agent_ids:
                skill = self.get(row["skill_id"])
                if skill:
                    result.append(skill)
        return result

    def get_for_agent_metadata(self, agent_id: str) -> List[SkillMetadata]:
        """返回某个 Agent 有权使用的所有技能元数据"""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM skills WHERE enabled = 1").fetchall()

        result = []
        for row in rows:
            agent_ids = json.loads(row["agent_ids"] or "[]")
            if not agent_ids or agent_id in agent_ids:
                meta = self.get_metadata(row["skill_id"])
                if meta:
                    result.append(meta)
        return result

    def list_all(self) -> list[dict]:
        """列出所有技能"""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM skills").fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, tags: List[str] = None) -> List[dict]:
        """
        搜索技能

        Args:
            query: 搜索关键词（匹配 name, description, tags）
            tags: 过滤标签
        """
        skills = self.list_all()
        results = []

        for skill in skills:
            matched = False

            # 关键词匹配
            if query:
                q = query.lower()
                if (
                    q in skill.get("name", "").lower()
                    or q in skill.get("description", "").lower()
                ):
                    matched = True

                # 匹配 tags
                skill_tags = json.loads(skill.get("tags") or "[]")
                if any(q in tag.lower() for tag in skill_tags):
                    matched = True

            else:
                matched = True

            # 标签过滤
            if matched and tags:
                skill_tags = json.loads(skill.get("tags") or "[]")
                if not any(tag in skill_tags for tag in tags):
                    matched = False

            if matched:
                results.append(skill)

        return results

    def enable(self, skill_id: str):
        """启用技能"""
        self._set_enabled(skill_id, True)
        if skill_id in self._cache:
            self._cache[skill_id].enable()

    def disable(self, skill_id: str):
        """禁用技能"""
        self._set_enabled(skill_id, False)
        if skill_id in self._cache:
            self._cache[skill_id].disable()

    def reload(self, skill_id: str):
        """热重载：清除缓存，下次 get() 时重新加载"""
        self._cache.pop(skill_id, None)
        row = self._get_row(skill_id)
        if row:
            self._register_from_dir(Path(row["install_path"]))
        logger.info(f"🔄 技能 [{skill_id}] 已热重载")

    def install(self, skill_id: str, source: str = "local") -> bool:
        """
        安装技能

        Args:
            skill_id: 技能 ID
            source: 来源 (local/remote/marketplace)
        """
        # TODO: 实现远程技能安装
        logger.info(f"📦 安装技能: {skill_id} (source: {source})")
        return True

    def uninstall(self, skill_id: str):
        """卸载技能"""
        self._cache.pop(skill_id, None)
        with self._conn() as conn:
            conn.execute("DELETE FROM skills WHERE skill_id = ?", (skill_id,))
        logger.info(f"🗑️ 技能 [{skill_id}] 已卸载")

    # ── 内部工具 ─────────────────────────────────

    def _set_enabled(self, skill_id: str, enabled: bool):
        with self._conn() as conn:
            conn.execute(
                "UPDATE skills SET enabled=? WHERE skill_id=?",
                (1 if enabled else 0, skill_id),
            )

    def _get_row(self, skill_id: str) -> Optional[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM skills WHERE skill_id=?", (skill_id,)
            ).fetchone()

    # ══════════════════════════════════════════════
    # 热重载功能
    # ══════════════════════════════════════════════

    def set_event_emitter(self, emitter):
        """设置事件发射器（用于 SSE 推送）"""
        self._event_emitter = emitter

    def _emit_skill_event(self, event_type: str, skill_id: str, data: dict = None):
        """发射技能事件到 SSE"""
        if hasattr(self, "_event_emitter") and self._event_emitter:
            event_data = {
                "type": event_type,
                "skill_id": skill_id,
                "data": data or {},
            }
            try:
                self._event_emitter(event_data)
            except Exception as e:
                logger.warning(f"Failed to emit skill event: {e}")

    def reload_skill(self, skill_id: str) -> bool:
        """热重载单个技能"""
        old_skill = self._cache.get(skill_id)

        self._cache.pop(skill_id, None)

        skill_class = self._load_skill_class(skill_id)
        if skill_class is None:
            logger.error(f"Failed to reload skill {skill_id}: cannot load class")
            if old_skill:
                self._cache[skill_id] = old_skill
            return False

        new_instance = skill_class()
        self._cache[skill_id] = new_instance

        self._emit_skill_event(
            "skill_reloaded",
            skill_id,
            {
                "skill_id": skill_id,
                "name": getattr(new_instance, "name", skill_id),
            },
        )

        logger.info(f"🔄 技能 [{skill_id}] 已热重载")
        return True

    def reload_all(self):
        """热重载所有技能"""
        skill_ids = list(self._cache.keys())
        for skill_id in skill_ids:
            self.reload_skill(skill_id)
        logger.info(f"🔄 已重载 {len(skill_ids)} 个技能")

    def get_stats(self, skill_id: str) -> dict:
        """获取技能调用统计"""
        row = self._get_row(skill_id)
        if not row:
            return {}

        return {
            "skill_id": skill_id,
            "name": row["name"],
            "call_count": getattr(self._cache.get(skill_id), "call_count", 0)
            if skill_id in self._cache
            else 0,
            "last_called": getattr(self._cache.get(skill_id), "last_called", None)
            if skill_id in self._cache
            else None,
            "enabled": bool(row["enabled"]),
            "source": row["source"],
            "installed_at": row["installed_at"],
        }

    def track_call(self, skill_id: str):
        """追踪技能调用"""
        if skill_id in self._cache:
            skill = self._cache[skill_id]
            if hasattr(skill, "call_count"):
                skill.call_count += 1
            if hasattr(skill, "last_called"):
                skill.last_called = datetime.now().isoformat()
