# tests/test_hooks.py

import pytest
import asyncio
from core.hooks import (
    HookRegistry,
    BaseHook,
    HookPhase,
    HookResult,
    ToolUseEvent,
    ToolUseResult,
    LoggingHook,
    RateLimitHook,
)


class CountingHook(BaseHook):
    def __init__(self, name="counting_hook", priority=100, delay=0):
        self._name = name
        self._priority = priority
        self._delay = delay
        self.call_count = 0
        self.call_order = []

    @property
    def name(self):
        return self._name

    @property
    def priority(self):
        return self._priority

    async def pre_tool(self, event):
        self.call_count += 1
        self.call_order.append(self.name)
        if self._delay:
            await asyncio.sleep(self._delay)
        return HookResult.allow()

    async def post_tool(self, event, result):
        self.call_count += 1
        self.call_order.append(self.name)
        if self._delay:
            await asyncio.sleep(self._delay)
        return HookResult.allow()

    async def on_error(self, event, error):
        self.call_count += 1
        self.call_order.append(self.name)
        if self._delay:
            await asyncio.sleep(self._delay)
        return HookResult.allow()


class TestHookRegistry:
    @pytest.mark.asyncio
    async def test_register_and_list_hooks(self):
        registry = HookRegistry()
        hook = CountingHook(name="test_hook")
        registry.register(hook)
        hooks = registry.list_hooks()
        assert len(hooks) == 1
        assert hooks[0]["name"] == "test_hook"

    @pytest.mark.asyncio
    async def test_unregister_hook(self):
        registry = HookRegistry()
        hook = CountingHook(name="test_hook")
        registry.register(hook)
        assert registry.unregister("test_hook") is True
        assert registry.unregister("nonexistent") is False

    @pytest.mark.asyncio
    async def test_pre_hooks_sequential_different_priorities(self):
        registry = HookRegistry()
        hook1 = CountingHook(name="low_priority", priority=100)
        hook2 = CountingHook(name="high_priority", priority=10)
        registry.register(hook1)
        registry.register(hook2)

        event = ToolUseEvent(tool_name="test_tool", tool_input={}, agent_id="test")
        await registry.run_pre_hooks(event)

        assert hook1.call_count == 1
        assert hook2.call_count == 1
        assert hook2.call_order[0] == "high_priority"
        assert hook1.call_order[0] == "low_priority"

    @pytest.mark.asyncio
    async def test_pre_hooks_concurrent_same_priority(self):
        registry = HookRegistry()
        hook1 = CountingHook(name="hook1", priority=50)
        hook2 = CountingHook(name="hook2", priority=50)
        registry.register(hook1)
        registry.register(hook2)

        event = ToolUseEvent(tool_name="test_tool", tool_input={}, agent_id="test")
        await registry.run_pre_hooks(event)

        assert hook1.call_count == 1
        assert hook2.call_count == 1

    @pytest.mark.asyncio
    async def test_pre_hooks_denied_stops_execution(self):
        registry = HookRegistry()
        hook1 = CountingHook(name="hook1", priority=10)
        hook2 = CountingHook(name="hook2", priority=50)
        registry.register(hook1)
        registry.register(hook2)

        class DenyHook(BaseHook):
            def __init__(self):
                self.call_count = 0

            @property
            def name(self):
                return "deny_hook"

            @property
            def priority(self):
                return 30

            async def pre_tool(self, event):
                self.call_count += 1
                return HookResult.deny("denied")

        deny_hook = DenyHook()
        registry.register(deny_hook)

        event = ToolUseEvent(tool_name="test_tool", tool_input={}, agent_id="test")
        result = await registry.run_pre_hooks(event)

        assert result.allowed is False
        assert hook2.call_count == 0
        assert deny_hook.call_count == 1

    @pytest.mark.asyncio
    async def test_post_hooks_sequential_different_priorities(self):
        registry = HookRegistry()
        hook1 = CountingHook(name="post_hook1", priority=10)
        hook2 = CountingHook(name="post_hook2", priority=50)
        registry.register(hook1)
        registry.register(hook2)

        event = ToolUseEvent(tool_name="test_tool", tool_input={}, agent_id="test")
        result = ToolUseResult(tool_name="test_tool", success=True)
        await registry.run_post_hooks(event, result)

        assert hook1.call_count == 1
        assert hook2.call_count == 1

    @pytest.mark.asyncio
    async def test_error_hooks_sequential_different_priorities(self):
        registry = HookRegistry()
        hook1 = CountingHook(name="error_hook1", priority=10)
        hook2 = CountingHook(name="error_hook2", priority=50)
        registry.register(hook1)
        registry.register(hook2)

        event = ToolUseEvent(tool_name="test_tool", tool_input={}, agent_id="test")
        error = ValueError("test error")
        await registry.run_error_hooks(event, error)

        assert hook1.call_count == 1
        assert hook2.call_count == 1

    @pytest.mark.asyncio
    async def test_critical_hook_denies_execution(self):
        registry = HookRegistry()
        hook1 = CountingHook(name="hook1", priority=10)

        class CriticalDenyHook(BaseHook):
            @property
            def name(self):
                return "critical_deny"

            @property
            def priority(self):
                return 50

            @property
            def critical(self):
                return True

            async def pre_tool(self, event):
                return HookResult.deny("critical denial")

        deny_hook = CriticalDenyHook()
        registry.register(hook1)
        registry.register(deny_hook)

        event = ToolUseEvent(tool_name="test_tool", tool_input={}, agent_id="test")
        result = await registry.run_pre_hooks(event)

        assert result.allowed is False
        assert "critical denial" in result.error_message


class TestLoggingHook:
    @pytest.mark.asyncio
    async def test_logging_hook_pre(self, caplog):
        caplog.set_level("INFO")
        hook = LoggingHook()
        event = ToolUseEvent(
            tool_name="shell",
            tool_input={"cmd": "ls"},
            agent_id="test_agent",
        )
        result = await hook.pre_tool(event)
        assert result.allowed is True
        assert "PRE" in caplog.text or "logging" in caplog.text

    @pytest.mark.asyncio
    async def test_logging_hook_post(self, caplog):
        caplog.set_level("INFO")
        hook = LoggingHook()
        event = ToolUseEvent(tool_name="shell", tool_input={}, agent_id="test")
        tool_result = ToolUseResult(tool_name="shell", success=True, elapsed_ms=100)
        result = await hook.post_tool(event, tool_result)
        assert result.allowed is True
        assert "POST" in caplog.text or "logging" in caplog.text

    @pytest.mark.asyncio
    async def test_logging_hook_error(self, caplog):
        hook = LoggingHook()
        event = ToolUseEvent(tool_name="shell", tool_input={}, agent_id="test")
        error = ValueError("test error")
        result = await hook.on_error(event, error)
        assert result.allowed is True
        assert "ERROR" in caplog.text


class TestRateLimitHook:
    @pytest.mark.asyncio
    async def test_rate_limit_allows_within_limit(self):
        hook = RateLimitHook(max_calls_per_minute=10)
        event = ToolUseEvent(tool_name="shell", tool_input={}, agent_id="test")
        for _ in range(5):
            result = await hook.pre_tool(event)
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_denies_over_limit(self):
        hook = RateLimitHook(max_calls_per_minute=3)
        event = ToolUseEvent(tool_name="shell", tool_input={}, agent_id="test")
        for _ in range(3):
            await hook.pre_tool(event)
        result = await hook.pre_tool(event)
        assert result.allowed is False
        assert "Rate limit exceeded" in result.error_message


class TestHookResult:
    def test_allow(self):
        result = HookResult.allow({"key": "value"})
        assert result.allowed is True
        assert result.metadata == {"key": "value"}

    def test_deny(self):
        result = HookResult.deny("denied reason", {"key": "value"})
        assert result.allowed is False
        assert result.error_message == "denied reason"
        assert result.metadata == {"key": "value"}

    def test_modify(self):
        result = HookResult.modify({"new": "output"}, {"key": "value"})
        assert result.allowed is True
        assert result.modified_output == {"new": "output"}

    def test_timeout(self):
        result = HookResult.timeout("test_hook", 5000)
        assert result.allowed is True
        assert "timed out" in result.error_message
        assert result.metadata["timeout"] is True
