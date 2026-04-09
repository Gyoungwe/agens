# core/soul_parser.py
# Agent Soul 解析器 - agent.md/soul.md ↔ 结构化数据互转

import os
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class SoulMeta:
    """Agent Soul 元数据"""

    name: str = ""
    role: str = ""
    priority: str = "normal"
    tools: list = field(default_factory=list)
    skills: list = field(default_factory=list)
    provider: str = ""
    model: str = ""
    max_tokens: int = 2048
    temperature: float = 0.7
    system_prompt: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> "SoulMeta":
        """从字典创建 SoulMeta"""
        known_fields = {
            "name",
            "role",
            "priority",
            "tools",
            "skills",
            "provider",
            "model",
            "max_tokens",
            "temperature",
            "system_prompt",
        }
        meta = cls()
        for key, value in data.items():
            if key in known_fields:
                setattr(meta, key, value)
            else:
                meta.extra[key] = value
        return meta

    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            "name": self.name,
            "role": self.role,
            "priority": self.priority,
            "tools": self.tools,
            "skills": self.skills,
            "provider": self.provider,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system_prompt": self.system_prompt,
        }
        result.update(self.extra)
        return result


@dataclass
class SoulDocument:
    """完整的 Soul 文档"""

    meta: SoulMeta
    body: str
    raw: str = ""

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        yaml_content = yaml.dump(
            self.meta.to_dict(), allow_unicode=True, default_flow_style=False
        )
        return f"---\n{yaml_content}---\n{self.body}"


@dataclass
class SoulDiff:
    """Soul 变更差异"""

    added: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)  # key: (old, new)
    removed: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    modified: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    body_changed: bool = False
    summary: str = ""

    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.modified or self.body_changed)


class SoulParser:
    """Soul 文档解析器"""

    FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
    SNAPSHOT_DIR = "data/soul_snapshots"

    def __init__(self, base_dir: str = "config/agents"):
        self.base_dir = Path(base_dir)
        self.snapshot_dir = Path(self.SNAPSHOT_DIR)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def parse_file(self, agent_id: str) -> Optional[SoulDocument]:
        """解析 agent 的 soul 文件"""
        soul_path = self._get_soul_path(agent_id)
        if not soul_path.exists():
            return None

        content = soul_path.read_text(encoding="utf-8")
        return self.parse_content(content)

    def parse_content(self, content: str) -> Optional[SoulDocument]:
        """解析 Markdown 内容"""
        match = self.FRONTMATTER_PATTERN.match(content)
        if not match:
            return None

        yaml_str, body = match.groups()
        try:
            meta_dict = yaml.safe_load(yaml_str) or {}
            meta = SoulMeta.from_dict(meta_dict)
            return SoulDocument(meta=meta, body=body.strip(), raw=content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}")

    def write_file(
        self, agent_id: str, doc: SoulDocument, create_backup: bool = True
    ) -> str:
        """写入 soul 文件"""
        soul_path = self._get_soul_path(agent_id)
        soul_path.parent.mkdir(parents=True, exist_ok=True)

        if create_backup and soul_path.exists():
            self._create_backup(soul_path)

        content = doc.to_markdown()
        soul_path.write_text(content, encoding="utf-8")
        return str(soul_path)

    def _get_soul_path(self, agent_id: str) -> Path:
        """获取 soul 文件路径"""
        return self.base_dir / agent_id / "soul.md"

    def _create_backup(self, path: Path) -> str:
        """创建备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.stem}_{timestamp}{path.suffix}"
        backup_path = self.snapshot_dir / path.parent.name / backup_name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        return str(backup_path)

    def diff(self, old: SoulDocument, new: SoulDocument) -> SoulDiff:
        """比较两个文档的差异"""
        diff = SoulDiff()

        old_dict = old.meta.to_dict()
        new_dict = new.meta.to_dict()

        all_keys = set(old_dict.keys()) | set(new_dict.keys())

        for key in all_keys:
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)
            if key not in old_dict:
                diff.added[key] = (None, new_val)
            elif key not in new_dict:
                diff.removed[key] = (old_val, None)
            elif old_val != new_val:
                diff.modified[key] = (old_val, new_val)

        if old.body != new.body:
            diff.body_changed = True

        diff.summary = self._generate_diff_summary(diff)
        return diff

    def _generate_diff_summary(self, diff: SoulDiff) -> str:
        """生成差异摘要"""
        parts = []
        if diff.added:
            parts.append(f"新增 {len(diff.added)} 个字段")
        if diff.removed:
            parts.append(f"移除 {len(diff.removed)} 个字段")
        if diff.modified:
            parts.append(f"修改 {len(diff.modified)} 个字段")
        if diff.body_changed:
            parts.append("正文有变更")
        return ", ".join(parts) if parts else "无变更"

    def list_agents(self) -> list:
        """列出所有 Agent"""
        agents = []
        if not self.base_dir.exists():
            return agents

        for agent_dir in self.base_dir.iterdir():
            if agent_dir.is_dir():
                soul_path = agent_dir / "soul.md"
                agents.append(
                    {
                        "agent_id": agent_dir.name,
                        "has_soul": soul_path.exists(),
                        "soul_path": str(soul_path) if soul_path.exists() else None,
                    }
                )
        return agents

    def get_soul_path(self, agent_id: str) -> Optional[str]:
        """获取 Agent soul 文件路径"""
        soul_path = self._get_soul_path(agent_id)
        return str(soul_path) if soul_path.exists() else None

    def delete_backup(self, agent_id: str, backup_name: str) -> bool:
        """删除指定备份"""
        backup_path = self.snapshot_dir / agent_id / backup_name
        if backup_path.exists():
            backup_path.unlink()
            return True
        return False

    def list_backups(self, agent_id: str) -> list:
        """列出 Agent 的所有备份"""
        backup_path = self.snapshot_dir / agent_id
        if not backup_path.exists():
            return []

        backups = []
        for f in sorted(backup_path.iterdir(), reverse=True):
            stat = f.stat()
            backups.append(
                {
                    "name": f.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        return backups

    def restore_backup(self, agent_id: str, backup_name: str) -> str:
        """恢复备份"""
        backup_path = self.snapshot_dir / agent_id / backup_name
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")

        current_path = self._get_soul_path(agent_id)
        if current_path.exists():
            self._create_backup(current_path)

        content = backup_path.read_text(encoding="utf-8")
        doc = self.parse_content(content)
        if doc:
            return self.write_file(agent_id, doc, create_backup=False)
        raise ValueError("Invalid backup content")


def parse_soul_file(path: str) -> Optional[SoulDocument]:
    """便捷函数：解析 soul 文件"""
    parser = SoulParser()
    content = Path(path).read_text(encoding="utf-8")
    return parser.parse_content(content)


def write_soul_file(path: str, meta: Dict, body: str) -> str:
    """便捷函数：写入 soul 文件"""
    parser = SoulParser()
    doc = SoulDocument(meta=SoulMeta.from_dict(meta), body=body)
    parsed = (
        parser.parse_content(Path(path).read_text(encoding="utf-8"))
        if Path(path).exists()
        else None
    )

    if parsed:
        diff = parser.diff(parsed, doc)
        if not diff.is_empty():
            print(f"Changes: {diff.summary}")

    return parser.write_file(Path(path).stem, doc)


def diff_soul(old: SoulDocument, new: SoulDocument) -> SoulDiff:
    """便捷函数：比较两个文档差异"""
    parser = SoulParser()
    return parser.diff(old, new)
