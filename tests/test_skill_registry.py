# tests/test_skill_registry.py

import pytest
import tempfile
import sqlite3
from pathlib import Path
from core.skill_registry import SkillRegistry, SkillMetadata


class TestSkillMetadata:
    def test_from_dict(self):
        data = {
            "skill_id": "test_skill",
            "name": "Test Skill",
            "description": "A test skill",
            "version": "0.02",
            "author": "tester",
            "tags": ["test", "demo"],
            "model": "claude-sonnet-4-5",
            "tools": ["bash", "read"],
            "input": {"type": "object", "properties": {"query": {"type": "string"}}},
            "output": {"type": "object"},
            "permissions": {"network": True, "filesystem": False},
            "agents": ["agent1", "agent2"],
            "enabled": True,
            "source": "local",
        }
        meta = SkillMetadata(data)
        assert meta.skill_id == "test_skill"
        assert meta.name == "Test Skill"
        assert meta.tags == ["test", "demo"]
        assert meta.tools == ["bash", "read"]
        assert meta.agents == ["agent1", "agent2"]
        assert meta.requires_network() is True
        assert meta.requires_filesystem() is False
        assert meta.matches_agent("agent1") is True
        assert meta.matches_agent("agent3") is False

    def test_matches_agent_empty_list(self):
        meta = SkillMetadata({"skill_id": "test"})
        assert meta.matches_agent("any_agent") is True

    def test_to_dict(self):
        meta = SkillMetadata({"skill_id": "test", "name": "Test"})
        d = meta.to_dict()
        assert d["skill_id"] == "test"
        assert d["name"] == "Test"


class TestSkillRegistry:
    @pytest.mark.asyncio
    async def test_init_creates_db(self, tmp_path):
        db_path = tmp_path / "test_skills.db"
        registry = SkillRegistry(db_path=db_path)
        assert db_path.exists()

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, tmp_path):
        db_path = tmp_path / "test_skills.db"
        registry = SkillRegistry(db_path=db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()
        assert mode.upper() == "WAL"

    @pytest.mark.asyncio
    async def test_get_conn_returns_persistent_connection(self, tmp_path):
        db_path = tmp_path / "test_skills.db"
        registry = SkillRegistry(db_path=db_path)
        conn1 = registry._get_conn()
        conn2 = registry._get_conn()
        assert conn1 is conn2

    @pytest.mark.asyncio
    async def test_list_all_empty(self, tmp_path):
        db_path = tmp_path / "test_skills_empty.db"
        skills_parent = tmp_path / "skills_empty"
        skills_parent.mkdir(parents=True)
        import core.skill_registry as sr

        original_skills_dir = sr.SKILLS_DIR
        original_db_path = sr.DB_PATH
        try:
            sr.SKILLS_DIR = skills_parent
            sr.DB_PATH = db_path
            registry = SkillRegistry(db_path=db_path)
            registry._scan_and_register()
            skills = registry.list_all()
            assert skills == []
        finally:
            sr.SKILLS_DIR = original_skills_dir
            sr.DB_PATH = original_db_path

    @pytest.mark.asyncio
    async def test_register_skill(self, tmp_path):
        db_path = tmp_path / "test_skills_reg.db"
        skills_parent = tmp_path / "skills"
        skill_dir = skills_parent / "test_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.py").write_text("class Skill: pass")
        (skill_dir / "SKILL.md").write_text("""---
skill_id: test_skill
name: Test Skill
description: Test
---
# Readme""")

        import core.skill_registry as sr

        original_skills_dir = sr.SKILLS_DIR
        original_db_path = sr.DB_PATH
        try:
            sr.SKILLS_DIR = skills_parent
            sr.DB_PATH = db_path
            registry = SkillRegistry(db_path=db_path)
            registry._scan_and_register()

            meta = registry.get_metadata("test_skill")
            assert meta is not None
            assert meta.skill_id == "test_skill"
            assert meta.name == "Test Skill"
        finally:
            sr.SKILLS_DIR = original_skills_dir
            sr.DB_PATH = original_db_path

    @pytest.mark.asyncio
    async def test_enable_disable_skill(self, tmp_path):
        db_path = tmp_path / "test_skills_toggle.db"
        registry = SkillRegistry(db_path=db_path)
        registry._cache = {}
        registry._init_db()
        cursor = registry._get_conn().execute(
            "INSERT INTO skills (skill_id, name, enabled) VALUES (?, ?, ?)",
            ("test_skill", "Test Skill", 1),
        )
        registry._get_conn().commit()

        registry.disable("test_skill")
        meta = registry.get_metadata("test_skill")
        assert meta.enabled is False

        registry.enable("test_skill")
        meta = registry.get_metadata("test_skill")
        assert meta.enabled is True

    @pytest.mark.asyncio
    async def test_uninstall_skill(self, tmp_path):
        db_path = tmp_path / "test_skills_uninstall.db"
        registry = SkillRegistry(db_path=db_path)
        registry._cache = {}
        registry._init_db()
        registry._get_conn().execute(
            "INSERT INTO skills (skill_id, name) VALUES (?, ?)",
            ("test_skill", "Test Skill"),
        )
        registry._get_conn().commit()

        registry.uninstall("test_skill")
        meta = registry.get_metadata("test_skill")
        assert meta is None
