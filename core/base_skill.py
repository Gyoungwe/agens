# core/base_skill.py
"""
技能基类

参考 Claude Managed Agents 的技能系统设计

技能应:
1. 继承 BaseSkill 并实现 run() 方法
2. 通过 SKILL.md 定义元数据
3. 返回结构化输出
4. 支持 Hook 拦截
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional
import time


class SkillInput(BaseModel):
    """所有技能的输入基类"""

    instruction: str
    context: Dict[str, Any] = Field(default_factory=dict)


class SkillOutput(BaseModel):
    """所有技能的统一输出格式"""

    success: bool
    result: Any = None
    error: str = ""
    elapsed_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
            "metadata": self.metadata,
        }


class ToolUseEvent(BaseModel):
    """工具调用事件（用于 Hook）"""

    tool_name: str
    tool_input: Dict[str, Any] = Field(default_factory=dict)
    agent_id: str = ""
    session_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class ToolUseResult(BaseModel):
    """工具执行结果"""

    tool_name: str
    tool_output: Any = None
    elapsed_ms: int = 0
    success: bool = True
    error: str = ""


class BaseSkill(ABC):
    """
    所有技能的基类

    技能开发指南:
    1. 创建 skills/<skill_id>/SKILL.md - 定义元数据
    2. 创建 skills/<skill_id>/skill.py - 实现技能逻辑

    示例 SKILL.md:
    ```yaml
    ---
    skill_id: web_search
    name: 网页搜索
    description: 使用搜索引擎搜索互联网信息
    version: 0.02
    tools: [bash, read]
    permissions:
      network: true
      filesystem: false
    agents: [research_agent]
    ---
    ```

    示例 skill.py:
    ```python
    from core.base_skill import BaseSkill, SkillInput

    class Skill(BaseSkill):
        skill_id = "web_search"
        name = "网页搜索"
        description = "使用搜索引擎搜索互联网信息"

        async def run(self, input_data: SkillInput) -> Any:
            query = input_data.instruction
            # 实现搜索逻辑
            return {"results": [...]}
    ```
    """

    skill_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "0.02"
    author: str = ""
    tags: List[str] = []

    def __init__(self):
        self._enabled = True
        self._hooks = []

    async def execute(self, input_data: SkillInput) -> SkillOutput:
        """
        统一执行入口

        执行流程:
        1. 检查是否启用
        2. 创建 ToolUseEvent
        3. 执行 pre_tool hooks
        4. 调用 run() 方法
        5. 执行 post_tool hooks
        6. 返回 SkillOutput
        """
        if not self._enabled:
            return SkillOutput(
                success=False,
                result=None,
                error=f"技能 [{self.skill_id}] 已被禁用",
            )

        start = time.monotonic()

        # 创建工具使用事件
        event = ToolUseEvent(
            tool_name=self.skill_id,
            tool_input={
                "instruction": input_data.instruction,
                "context": input_data.context,
            },
        )

        # 执行 pre_tool hooks
        for hook in self._hooks:
            if hasattr(hook, "pre_tool"):
                result = await hook.pre_tool(event)
                if not result.allowed:
                    return SkillOutput(
                        success=False,
                        result=None,
                        error=result.error_message or "Hook 阻止执行",
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                    )

        # 执行技能
        tool_result = ToolUseResult(tool_name=self.skill_id)
        try:
            result = await self.run(input_data)
            tool_result.success = True
            tool_result.tool_output = result
        except Exception as e:
            tool_result.success = False
            tool_result.error = f"{type(e).__name__}: {e}"

            # 执行 error hooks
            for hook in self._hooks:
                if hasattr(hook, "on_error"):
                    await hook.on_error(event, e)

        tool_result.elapsed_ms = int((time.monotonic() - start) * 1000)

        # 执行 post_tool hooks
        for hook in self._hooks:
            if hasattr(hook, "post_tool"):
                hook_result = await hook.post_tool(event, tool_result)
                if hook_result.modified_output is not None:
                    tool_result.tool_output = hook_result.modified_output

        return SkillOutput(
            success=tool_result.success,
            result=tool_result.tool_output,
            error=tool_result.error,
            elapsed_ms=tool_result.elapsed_ms,
        )

    @abstractmethod
    async def run(self, input_data: SkillInput) -> Any:
        """子类在这里实现具体逻辑"""
        ...

    def add_hook(self, hook):
        """添加 Hook"""
        self._hooks.append(hook)

    def remove_hook(self, hook_name: str):
        """移除 Hook"""
        self._hooks = [h for h in self._hooks if getattr(h, "name", "") != hook_name]

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "enabled": self._enabled,
        }

    def __repr__(self):
        status = "✅" if self._enabled else "❌"
        return f"{status} Skill[{self.skill_id}] v{self.version}"
