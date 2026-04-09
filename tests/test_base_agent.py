# tests/test_base_agent.py

import pytest
import tempfile
import os
from pathlib import Path
from pydantic import ValidationError
from core.base_agent import (
    AgentConfig,
    LLMConfig,
    RulesConfig,
    MetaConfig,
    KnowledgeConfig,
    BaseAgent,
)
from bus.message_bus import MessageBus


class TestAgentConfig:
    def test_valid_config(self):
        config = AgentConfig(
            id="test_agent",
            name="Test Agent",
            version="0.02",
            description="A test agent",
            skills=["skill1", "skill2"],
            llm=LLMConfig(model="claude-sonnet-4-5", max_tokens=2048),
            rules=RulesConfig(max_retries=3, timeout_seconds=60),
        )
        assert config.id == "test_agent"
        assert config.name == "Test Agent"
        assert config.skills == ["skill1", "skill2"]

    def test_empty_id_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(id="   ", name="Test")
        assert "id cannot be empty" in str(exc_info.value).lower()

    def test_whitespace_id_trimmed(self):
        config = AgentConfig(id="  agent1  ", name="Test")
        assert config.id == "agent1"

    def test_default_values(self):
        config = AgentConfig(id="test")
        assert config.name == ""
        assert config.version == "0.02"
        assert config.description == ""
        assert config.skills == []
        assert config.llm.model == "claude-sonnet-4-5"
        assert config.rules.max_retries == 3
        assert config.meta.enabled is True

    def test_nested_configs(self):
        config = AgentConfig(
            id="test",
            llm=LLMConfig(temperature=0.9),
            rules=RulesConfig(timeout_seconds=120, can_delegate=True),
            knowledge=KnowledgeConfig(topics=["ai", "ml"], max_results=10),
            meta=MetaConfig(tags=["test", "dev"], enabled=False),
        )
        assert config.llm.temperature == 0.9
        assert config.rules.can_delegate is True
        assert config.rules.timeout_seconds == 120
        assert config.knowledge.topics == ["ai", "ml"]
        assert config.meta.enabled is False

    def test_invalid_llm_config(self):
        with pytest.raises(ValidationError):
            LLMConfig(model=123)

    def test_invalid_rules_config(self):
        with pytest.raises(ValidationError):
            RulesConfig(max_retries="not_an_int")


class TestBaseAgentFromYaml:
    def test_from_yaml_loads_valid_config(self, tmp_path):
        yaml_content = """
id: test_agent
name: Test Agent
version: "0.02"
description: A test agent
skills:
  - skill1
  - skill2
llm:
  model: claude-sonnet-4-5
  max_tokens: 2048
rules:
  max_retries: 3
  timeout_seconds: 60
"""
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(yaml_content)

        bus = MessageBus()

        class ConcreteAgent(BaseAgent):
            async def execute(self, instruction, context):
                return "done"

        agent = ConcreteAgent.from_yaml(
            yaml_path=yaml_file,
            bus=bus,
        )
        assert agent.agent_id == "test_agent"
        assert agent.description == "A test agent"

    def test_from_yaml_invalid_schema_raises(self, tmp_path):
        yaml_content = """
name: No ID Agent
skills: not_a_list
"""
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(yaml_content)

        bus = MessageBus()

        class ConcreteAgent(BaseAgent):
            async def execute(self, instruction, context):
                return "done"

        with pytest.raises(ValueError) as exc_info:
            ConcreteAgent.from_yaml(yaml_path=yaml_file, bus=bus)
        assert "validation failed" in str(exc_info.value).lower()
