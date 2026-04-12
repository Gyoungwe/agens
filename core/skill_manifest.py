from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class SkillManifest(BaseModel):
    skill_id: str
    name: str
    description: str = ""
    version: str = "0.02"
    author: str = ""
    license: str = ""
    tags: List[str] = Field(default_factory=list)
    model: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    permissions: Dict[str, Any] = Field(default_factory=dict)
    agents: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    source: str = "local"
    entrypoint: str = "entry.py"
    readme: str = "README.md"

    def to_registry_row(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "license": self.license,
            "tags": self.tags,
            "model": self.model,
            "tools": self.tools,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permissions": self.permissions,
            "agents": self.agents,
            "metadata": self.metadata,
            "enabled": self.enabled,
            "source": self.source,
            "entrypoint": self.entrypoint,
            "readme": self.readme,
        }


def load_skill_manifest(skill_dir: Path) -> SkillManifest:
    manifest_path = skill_dir / "skill.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"skill.yaml not found in {skill_dir}")

    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if "skill_id" not in data:
        data["skill_id"] = skill_dir.name
    if "name" not in data:
        data["name"] = data["skill_id"]

    return SkillManifest(**data)
