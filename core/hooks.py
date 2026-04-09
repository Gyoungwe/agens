# core/hooks.py
"""
Pre/Post ToolUse Hooks 系统
参考 Claude Managed Agents API 的 Hook 机制设计

Hook 生命周期:
1. pre_tool  - 工具执行前调用，可修改参数或阻止执行
2. post_tool - 工具执行后调用，可修改输出
3. on_error  - 工具执行出错时调用

可靠性特性:
- priority: Hook 执行优先级（数字越小越先执行）
- timeout_ms: Hook 超时时间（毫秒）
- critical: 是否为关键 Hook（失败时阻止执行）
- graceful degradation: Hook 失败默认降级继续
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class HookPhase(Enum):
    """Hook 执行阶段"""

    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    ON_ERROR = "on_error"


@dataclass
class ToolUseEvent:
    """
    工具调用事件
    参考 Claude Managed Agents 的 agent.tool_use / agent.custom_tool_use 事件
    """

    tool_name: str  # 工具名称
    tool_input: Dict[str, Any]  # 工具输入参数
    agent_id: str  # 执行 Agent ID
    session_id: Optional[str] = None  # 会话 ID
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolUseResult:
    """
    工具执行结果
    """

    tool_name: str
    tool_output: Any = None
    elapsed_ms: int = 0
    success: bool = True
    error: str = ""


@dataclass
class HookResult:
    """
    Hook 返回结果
    所有 Hook 必须返回此类型
    """

    allowed: bool = True  # 是否允许继续执行
    modified_output: Any = None  # 修改后的输出（post_hook 可用）
    error_message: str = ""  # 错误信息
    metadata: Dict[str, Any] = field(default_factory=dict)
    hook_name: str = ""  # Hook 名称（用于 TimingHook）
    elapsed_ms: int = 0  # Hook 执行耗时

    @classmethod
    def allow(cls, metadata: Dict[str, Any] = None) -> "HookResult":
        return cls(allowed=True, metadata=metadata or {})

    @classmethod
    def deny(cls, message: str, metadata: Dict[str, Any] = None) -> "HookResult":
        return cls(allowed=False, error_message=message, metadata=metadata or {})

    @classmethod
    def modify(cls, output: Any, metadata: Dict[str, Any] = None) -> "HookResult":
        return cls(allowed=True, modified_output=output, metadata=metadata or {})

    @classmethod
    def timeout(cls, hook_name: str, timeout_ms: int) -> "HookResult":
        return cls(
            allowed=True,
            error_message=f"Hook {hook_name} timed out after {timeout_ms}ms",
            metadata={"timeout": True, "timeout_ms": timeout_ms},
        )


class BaseHook(ABC):
    """
    Hook 基类
    所有 Hook 必须继承此类并实现对应的方法

    可靠性属性:
    - priority: 执行优先级（默认 100，数字越小越先执行）
    - timeout_ms: 超时时间（默认 5000ms）
    - critical: 是否为关键 Hook（默认 False，失败时降级继续）
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Hook 名称"""
        pass

    @property
    def description(self) -> str:
        """Hook 描述"""
        return ""

    @property
    def priority(self) -> int:
        """执行优先级（数字越小越先执行）"""
        return 100

    @property
    def timeout_ms(self) -> int:
        """超时时间（毫秒）"""
        return 5000

    @property
    def critical(self) -> bool:
        """是否为关键 Hook（失败时阻止执行）"""
        return False

    async def pre_tool(self, event: ToolUseEvent) -> HookResult:
        """
        工具执行前调用
        返回 HookResult:
        - allowed=True: 允许执行
        - allowed=False: 阻止执行，error_message 作为错误原因
        """
        return HookResult.allow()

    async def post_tool(self, event: ToolUseEvent, result: ToolUseResult) -> HookResult:
        """
        工具执行后调用
        可返回 modified_output 来修改结果
        """
        return HookResult.allow()

    async def on_error(self, event: ToolUseEvent, error: Exception) -> HookResult:
        """
        工具执行出错时调用
        可用于日志记录、告警等
        """
        return HookResult.allow()


class LoggingHook(BaseHook):
    """
    日志记录 Hook
    记录所有工具调用
    """

    @property
    def name(self) -> str:
        return "logging_hook"

    @property
    def description(self) -> str:
        return "记录所有工具调用"

    @property
    def priority(self) -> int:
        return 50

    async def pre_tool(self, event: ToolUseEvent) -> HookResult:
        start = time.time()
        logger.info(
            f"[Hook:logging] PRE  tool={event.tool_name} "
            f"agent={event.agent_id} input_keys={list(event.tool_input.keys())}"
        )
        elapsed = int((time.time() - start) * 1000)
        return HookResult(
            allowed=True,
            metadata={"elapsed_ms": elapsed},
            hook_name=self.name,
            elapsed_ms=elapsed,
        )

    async def post_tool(self, event: ToolUseEvent, result: ToolUseResult) -> HookResult:
        start = time.time()
        status = "✅" if result.success else "❌"
        logger.info(
            f"[Hook:logging] POST tool={event.tool_name} "
            f"{status} elapsed={result.elapsed_ms}ms"
        )
        elapsed = int((time.time() - start) * 1000)
        return HookResult(
            allowed=True,
            metadata={"elapsed_ms": elapsed},
            hook_name=self.name,
            elapsed_ms=elapsed,
        )

    async def on_error(self, event: ToolUseEvent, error: Exception) -> HookResult:
        start = time.time()
        logger.error(
            f"[Hook:logging] ERROR tool={event.tool_name} "
            f"agent={event.agent_id} error={type(error).__name__}: {error}"
        )
        elapsed = int((time.time() - start) * 1000)
        return HookResult(
            allowed=True,
            metadata={"elapsed_ms": elapsed},
            hook_name=self.name,
            elapsed_ms=elapsed,
        )


class RateLimitHook(BaseHook):
    """
    限流 Hook
    限制每个 Agent+工具 的调用频率
    """

    def __init__(self, max_calls_per_minute: int = 60):
        self.max_calls_per_minute = max_calls_per_minute
        self._call_history: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "rate_limit_hook"

    @property
    def description(self) -> str:
        return f"限流: {self.max_calls_per_minute}次/分钟"

    @property
    def priority(self) -> int:
        return 10

    def _make_key(self, agent_id: str, tool_name: str) -> str:
        return f"{agent_id}:{tool_name}"

    def _clean_old_calls(self, history: List[float], now: float) -> List[float]:
        """清除1分钟前的记录"""
        return [t for t in history if now - t < 60]

    async def pre_tool(self, event: ToolUseEvent) -> HookResult:
        key = self._make_key(event.agent_id, event.tool_name)
        now = time.time()

        async with self._lock:
            if key not in self._call_history:
                self._call_history[key] = []

            self._call_history[key] = self._clean_old_calls(
                self._call_history[key], now
            )

            if len(self._call_history[key]) >= self.max_calls_per_minute:
                oldest = self._call_history[key][0]
                wait_time = 60 - (now - oldest)
                logger.warning(
                    f"[Hook:rate_limit] {event.agent_id}:{event.tool_name} "
                    f"rate limited, wait {wait_time:.1f}s"
                )
                return HookResult(
                    allowed=False,
                    error_message=f"Rate limit exceeded, wait {wait_time:.1f}s",
                    metadata={"wait_seconds": wait_time, "hook_name": self.name},
                )

            self._call_history[key].append(now)

        return HookResult(
            allowed=True, hook_name=self.name, metadata={"hook_name": self.name}
        )


class ApprovalHook(BaseHook):
    """
    审批 Hook
    高风险操作需要审批才能执行
    """

    def __init__(self, approval_queue=None):
        self._queue = approval_queue
        self._approved_cache: Dict[str, bool] = {}

    @property
    def name(self) -> str:
        return "approval_hook"

    @property
    def description(self) -> str:
        return "高风险操作需要审批"

    def _is_high_risk(self, tool_name: str, tool_input: Dict[str, Any]) -> bool:
        """判断是否为高风险操作"""
        high_risk_tools = {"shell", "exec", "delete", "format", "rmrf"}
        if tool_name.lower() in high_risk_tools:
            return True
        if tool_name == "file_write" and tool_input.get("path", "").startswith("/etc"):
            return True
        return False

    async def pre_tool(self, event: ToolUseEvent) -> HookResult:
        if not self._is_high_risk(event.tool_name, event.tool_input):
            return HookResult(allowed=True, hook_name=self.name)

        cache_key = f"{event.agent_id}:{event.tool_name}:{hash(str(event.tool_input))}"

        if cache_key in self._approved_cache:
            return HookResult(allowed=True, hook_name=self.name)

        if self._queue:
            has_pending = await self._queue.has_pending(event.agent_id, event.tool_name)
            if has_pending:
                return HookResult(
                    allowed=False,
                    error_message=f"Pending approval for {event.tool_name}",
                    metadata={"pending": True, "hook_name": self.name},
                )

        return HookResult(allowed=True, hook_name=self.name)


class TokenUsageHook(BaseHook):
    """
    Token 使用量统计 Hook
    记录每个 Agent 的 Token 消耗
    """

    def __init__(self):
        self._usage: Dict[str, Dict[str, int]] = {}
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "token_usage_hook"

    @property
    def description(self) -> str:
        return "统计 Token 使用量"

    def get_usage(self, agent_id: str = None) -> Dict[str, Any]:
        if agent_id:
            return self._usage.get(agent_id, {"input": 0, "output": 0, "total": 0})
        return dict(self._usage)

    async def post_tool(self, event: ToolUseEvent, result: ToolUseResult) -> HookResult:
        if not result.success:
            return HookResult(allowed=True, hook_name=self.name)

        metadata = result.tool_output if isinstance(result.tool_output, dict) else {}
        input_tokens = metadata.get("usage", {}).get("input_tokens", 0)
        output_tokens = metadata.get("usage", {}).get("output_tokens", 0)

        async with self._lock:
            if event.agent_id not in self._usage:
                self._usage[event.agent_id] = {"input": 0, "output": 0, "total": 0}

            self._usage[event.agent_id]["input"] += input_tokens
            self._usage[event.agent_id]["output"] += output_tokens
            self._usage[event.agent_id]["total"] += input_tokens + output_tokens

        return HookResult(
            allowed=True,
            hook_name=self.name,
            metadata={
                "hook_name": self.name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )


class ExecutionTimeHook(BaseHook):
    """
    执行时间统计 Hook
    记录每个工具的执行时间
    """

    def __init__(self, warn_threshold_ms: int = 5000):
        self.warn_threshold_ms = warn_threshold_ms
        self._exec_times: Dict[str, List[int]] = {}

    @property
    def name(self) -> str:
        return "execution_time_hook"

    @property
    def description(self) -> str:
        return f"统计执行时间 (警告阈值: {self.warn_threshold_ms}ms)"

    async def post_tool(self, event: ToolUseEvent, result: ToolUseResult) -> HookResult:
        if result.elapsed_ms > self.warn_threshold_ms:
            logger.warning(
                f"[Hook:exec_time] {event.agent_id}:{event.tool_name} "
                f"慢于阈值: {result.elapsed_ms}ms > {self.warn_threshold_ms}ms"
            )
        return HookResult(
            allowed=True,
            hook_name=self.name,
            elapsed_ms=result.elapsed_ms,
            metadata={"hook_name": self.name, "elapsed_ms": result.elapsed_ms},
        )


class HookRegistry:
    """
    Hook 注册中心
    管理所有 Hook 的注册和执行

    可靠性特性:
    - 按 priority 排序执行
    - 超时控制
    - 降级继续（非 critical hook 失败不影响后续）
    """

    def __init__(self):
        self._pre_hooks: List[BaseHook] = []
        self._post_hooks: List[BaseHook] = []
        self._error_hooks: List[BaseHook] = []
        self._hook_names: set = set()
        self._lock = asyncio.Lock()

    def register(self, hook: BaseHook) -> None:
        """注册 Hook"""
        if hook.name in self._hook_names:
            logger.warning(f"Hook {hook.name} 已注册，跳过")
            return

        self._pre_hooks.append(hook)
        self._post_hooks.append(hook)
        self._error_hooks.append(hook)
        self._hook_names.add(hook.name)

        self._pre_hooks.sort(key=lambda h: h.priority)
        self._post_hooks.sort(key=lambda h: h.priority)
        self._error_hooks.sort(key=lambda h: h.priority)

        logger.info(
            f"🔗 Hook [{hook.name}] 已注册: {hook.description} "
            f"(priority={hook.priority}, timeout={hook.timeout_ms}ms, critical={hook.critical})"
        )

    def unregister(self, hook_name: str) -> bool:
        """注销 Hook"""
        if hook_name not in self._hook_names:
            return False

        self._pre_hooks = [h for h in self._pre_hooks if h.name != hook_name]
        self._post_hooks = [h for h in self._post_hooks if h.name != hook_name]
        self._error_hooks = [h for h in self._error_hooks if h.name != hook_name]
        self._hook_names.discard(hook_name)
        logger.info(f"🔗 Hook [{hook_name}] 已注销")
        return True

    def list_hooks(self) -> List[Dict[str, str]]:
        """列出所有已注册的 Hook"""
        return [
            {
                "name": h.name,
                "description": h.description,
                "priority": h.priority,
                "timeout_ms": h.timeout_ms,
                "critical": h.critical,
            }
            for h in self._pre_hooks
        ]

    async def _run_hook_with_timeout(
        self, hook: BaseHook, func: Callable, *args, **kwargs
    ) -> HookResult:
        """带超时的 Hook 执行"""
        hook_name = hook.name
        timeout = hook.timeout_ms / 1000.0

        try:
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            if hasattr(result, "hook_name"):
                result.hook_name = hook_name
            elif isinstance(result, HookResult):
                result.hook_name = hook_name
            return result
        except asyncio.TimeoutError:
            logger.warning(
                f"[HookRegistry] Hook {hook_name} 执行超时 ({hook.timeout_ms}ms)"
            )
            return HookResult.timeout(hook_name, hook.timeout_ms)
        except Exception as e:
            logger.error(f"[HookRegistry] Hook {hook_name} 执行异常: {e}")
            return HookResult(
                allowed=not hook.critical,
                error_message=f"Hook {hook_name} 执行失败: {e}",
                metadata={"hook_name": hook_name, "error": str(e)},
            )

        try:
            coro = func(*args, **kwargs)
            print(f"[DEBUG] coro created: {coro}")
            result = await asyncio.wait_for(coro, timeout=timeout)
            print(f"[DEBUG] result: {result}")
            if hasattr(result, "hook_name"):
                result.hook_name = hook_name
            elif isinstance(result, HookResult):
                result.hook_name = hook_name
            return result
        except asyncio.TimeoutError:
            logger.warning(
                f"[HookRegistry] Hook {hook_name} 执行超时 ({hook.timeout_ms}ms)"
            )
            return HookResult.timeout(hook_name, hook.timeout_ms)
        except Exception as e:
            logger.error(f"[HookRegistry] Hook {hook_name} 执行异常: {e}")
            return HookResult(
                allowed=not hook.critical,
                error_message=f"Hook {hook_name} 执行失败: {e}",
                metadata={"hook_name": hook_name, "error": str(e)},
            )

    async def run_pre_hooks(self, event: ToolUseEvent) -> HookResult:
        """
        执行所有 pre_tool hooks
        相同 priority 的 hooks 并发执行，不同 priority 按顺序执行
        如果关键 hook 返回 allowed=False，立即停止
        非关键 hook 失败会降级继续
        """
        hook_groups: Dict[int, List[BaseHook]] = {}
        for hook in self._pre_hooks:
            hook_groups.setdefault(hook.priority, []).append(hook)

        for priority in sorted(hook_groups.keys()):
            hooks = hook_groups[priority]
            if len(hooks) == 1:
                hook = hooks[0]
                result = await self._run_hook_with_timeout(hook, hook.pre_tool, event)
                if hook.critical and not result.allowed:
                    logger.warning(
                        f"[HookRegistry] 关键 Hook {hook.name} 阻止了 {event.tool_name} 执行: "
                        f"{result.error_message}"
                    )
                    return result
                if not result.allowed:
                    logger.warning(
                        f"[HookRegistry] Hook {hook.name} 阻止了 {event.tool_name} 执行（降级）: "
                        f"{result.error_message}"
                    )
                    return result
            else:
                results = await asyncio.gather(
                    *[
                        self._run_hook_with_timeout(hook, hook.pre_tool, event)
                        for hook in hooks
                    ],
                    return_exceptions=True,
                )
                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        logger.warning(f"[HookRegistry] Hook {hooks[i].name} 异常: {r}")
                        continue
                    hook = hooks[i]
                    if hook.critical and not r.allowed:
                        logger.warning(
                            f"[HookRegistry] 关键 Hook {hook.name} 阻止了 {event.tool_name} 执行: "
                            f"{r.error_message}"
                        )
                        return r
                    if not r.allowed:
                        logger.warning(
                            f"[HookRegistry] Hook {hook.name} 阻止了 {event.tool_name} 执行（降级）: "
                            f"{r.error_message}"
                        )
                        return r

        return HookResult.allow()

    async def run_post_hooks(
        self, event: ToolUseEvent, result: ToolUseResult
    ) -> HookResult:
        """
        执行所有 post_tool hooks
        相同 priority 的 hooks 并发执行，不同 priority 按顺序执行
        后续 hook 可以看到前面 hook 修改后的输出
        非关键 hook 失败会降级继续
        """
        hook_groups: Dict[int, List[BaseHook]] = {}
        for hook in self._post_hooks:
            hook_groups.setdefault(hook.priority, []).append(hook)

        final_result = HookResult.allow()

        for priority in sorted(hook_groups.keys()):
            hooks = hook_groups[priority]
            if len(hooks) == 1:
                hook = hooks[0]
                hook_result = await self._run_hook_with_timeout(
                    hook, hook.post_tool, event, result
                )
                if hook_result.modified_output is not None:
                    result.tool_output = hook_result.modified_output
                    final_result = hook_result
                if not hook_result.allowed and hook.critical:
                    logger.warning(
                        f"[HookRegistry] 关键 Hook {hook.name} 返回失败: "
                        f"{hook_result.error_message}"
                    )
                    final_result = hook_result
            else:

                async def run_hook_with_output_update(hook: BaseHook) -> HookResult:
                    hr = await self._run_hook_with_timeout(
                        hook, hook.post_tool, event, result
                    )
                    if hr.modified_output is not None:
                        async with self._lock:
                            result.tool_output = hr.modified_output
                    return hr

                results = await asyncio.gather(
                    *[run_hook_with_output_update(hook) for hook in hooks],
                    return_exceptions=True,
                )
                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        logger.warning(f"[HookRegistry] Hook {hooks[i].name} 异常: {r}")
                        continue
                    hook = hooks[i]
                    if not r.allowed and hook.critical:
                        logger.warning(
                            f"[HookRegistry] 关键 Hook {hook.name} 返回失败: "
                            f"{r.error_message}"
                        )
                        final_result = r

        return final_result

    async def run_error_hooks(
        self, event: ToolUseEvent, error: Exception
    ) -> HookResult:
        """
        执行所有 on_error hooks
        相同 priority 的 hooks 并发执行，不同 priority 按顺序执行
        即使出错也继续执行后续 hooks（降级继续）
        """
        hook_groups: Dict[int, List[BaseHook]] = {}
        for hook in self._error_hooks:
            hook_groups.setdefault(hook.priority, []).append(hook)

        final_result = HookResult.allow()

        for priority in sorted(hook_groups.keys()):
            hooks = hook_groups[priority]
            if len(hooks) == 1:
                hook = hooks[0]
                hook_result = await self._run_hook_with_timeout(
                    hook, hook.on_error, event, error
                )
                if not hook_result.allowed:
                    logger.warning(
                        f"[HookRegistry] Hook {hook.name} on_error 返回失败（继续）: "
                        f"{hook_result.error_message}"
                    )
            else:
                results = await asyncio.gather(
                    *[
                        self._run_hook_with_timeout(hook, hook.on_error, event, error)
                        for hook in hooks
                    ],
                    return_exceptions=True,
                )
                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        logger.warning(f"[HookRegistry] Hook {hooks[i].name} 异常: {r}")
                        continue
                    if not r.allowed:
                        logger.warning(
                            f"[HookRegistry] Hook {hooks[i].name} on_error 返回失败（继续）: "
                            f"{r.error_message}"
                        )

        return final_result


async def execute_with_hooks(
    registry: HookRegistry,
    event: ToolUseEvent,
    execute_func: Callable,
) -> ToolUseResult:
    """
    使用 Hook 包装的工具执行
    示例:
        result = await execute_with_hooks(
            hook_registry,
            ToolUseEvent(tool_name="shell", tool_input={"cmd": "ls"}),
            lambda: run_shell("ls")
        )
    """
    start_time = time.time()
    result = ToolUseResult(tool_name=event.tool_name)

    pre_result = await registry.run_pre_hooks(event)
    if not pre_result.allowed:
        result.success = False
        result.error = pre_result.error_message
        result.elapsed_ms = int((time.time() - start_time) * 1000)
        await registry.run_error_hooks(event, Exception(pre_result.error_message))
        return result

    try:
        output = await execute_func()
        result.tool_output = output
        result.success = True
    except Exception as e:
        result.success = False
        result.error = f"{type(e).__name__}: {e}"
        await registry.run_error_hooks(event, e)
    finally:
        result.elapsed_ms = int((time.time() - start_time) * 1000)

    post_result = await registry.run_post_hooks(event, result)
    if post_result.modified_output is not None:
        result.tool_output = post_result.modified_output

    return result
