import logging
import os
import re
from typing import Any

from core.hooks import BaseHook, HookResult, ToolUseEvent, ToolUseResult

logger = logging.getLogger(__name__)


class SafetyGuardHook(BaseHook):
    """Optional safety guard for agent/tool outputs."""

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self.strict = os.getenv("GUARDRAILS_STRICT", "false").lower() == "true"
        self.enabled = os.getenv("ENABLE_GUARDRAILS", "true").lower() == "true"
        self._guard = None
        self._toxic_regex = re.compile(
            r"\b(kill\s+yourself|suicide|bomb\s+making|credit\s+card\s+fraud)\b",
            re.IGNORECASE,
        )

        if not self.enabled:
            return

        try:
            from guardrails import Guard
            from guardrails.hub import ToxicLanguage

            self._guard = Guard().use(ToxicLanguage, threshold=self.threshold)
            logger.info("🛡️ SafetyGuardHook: Guardrails validator enabled")
        except Exception as e:
            logger.info(
                f"🛡️ SafetyGuardHook: Guardrails unavailable, using fallback filters ({e})"
            )

    @property
    def name(self) -> str:
        return "safety_guard_hook"

    @property
    def description(self) -> str:
        return "Guardrails-based output safety validation"

    @property
    def priority(self) -> int:
        return 95

    def _fallback_check(self, text: str) -> bool:
        return bool(self._toxic_regex.search(text or ""))

    def _guardrails_check(self, text: str) -> bool:
        if not self._guard:
            return False
        try:
            if hasattr(self._guard, "validate"):
                result = self._guard.validate(text)
                if hasattr(result, "validation_passed"):
                    return not bool(result.validation_passed)
                return False
        except Exception as e:
            logger.debug(f"SafetyGuardHook guardrails check failed, fallback used: {e}")
        return self._fallback_check(text)

    async def post_tool(self, event: ToolUseEvent, result: ToolUseResult) -> HookResult:
        if not self.enabled or not result.success:
            return HookResult.allow({"hook": self.name, "enabled": self.enabled})

        output: Any = result.tool_output
        if not isinstance(output, str):
            return HookResult.allow({"hook": self.name, "checked": False})

        unsafe = self._guardrails_check(output)
        if not unsafe:
            return HookResult.allow(
                {"hook": self.name, "checked": True, "unsafe": False}
            )

        logger.warning(
            f"[SafetyGuardHook] potential unsafe output detected agent={event.agent_id} tool={event.tool_name}"
        )
        if self.strict:
            return HookResult.deny(
                "Output blocked by SafetyGuardHook",
                {"hook": self.name, "unsafe": True, "strict": True},
            )

        safe_output = "[Content filtered by safety policy]"
        return HookResult.modify(
            safe_output,
            {"hook": self.name, "unsafe": True, "strict": False},
        )


class MLflowHook(BaseHook):
    """Optional MLflow tracking for tool/agent execution."""

    def __init__(self):
        self.enabled = os.getenv("ENABLE_MLFLOW", "false").lower() == "true"
        self._mlflow = None
        if not self.enabled:
            return

        try:
            import mlflow

            self._mlflow = mlflow
            tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
            experiment = os.getenv("MLFLOW_EXPERIMENT", "agens-agent-system")
            if tracking_uri:
                self._mlflow.set_tracking_uri(tracking_uri)
            self._mlflow.set_experiment(experiment)
            logger.info(
                f"📈 MLflowHook enabled (experiment={experiment}, tracking_uri={tracking_uri or 'default'})"
            )
        except Exception as e:
            self.enabled = False
            logger.warning(f"MLflowHook disabled: {e}")

    @property
    def name(self) -> str:
        return "mlflow_hook"

    @property
    def description(self) -> str:
        return "MLflow metrics logging for agent executions"

    @property
    def priority(self) -> int:
        return 200

    async def post_tool(self, event: ToolUseEvent, result: ToolUseResult) -> HookResult:
        if not self.enabled or not self._mlflow:
            return HookResult.allow({"hook": self.name, "enabled": self.enabled})

        try:
            with self._mlflow.start_run(run_name=f"{event.agent_id}:{event.tool_name}"):
                self._mlflow.log_params(
                    {
                        "agent_id": event.agent_id,
                        "tool_name": event.tool_name,
                        "success": str(result.success).lower(),
                    }
                )
                self._mlflow.log_metric("elapsed_ms", float(result.elapsed_ms))
                output_len = (
                    len(str(result.tool_output))
                    if result.tool_output is not None
                    else 0
                )
                self._mlflow.log_metric("output_length", float(output_len))
            return HookResult.allow({"hook": self.name, "logged": True})
        except Exception as e:
            logger.warning(f"MLflowHook post_tool degraded: {e}")
            return HookResult.allow(
                {"hook": self.name, "logged": False, "error": str(e)}
            )

    async def on_error(self, event: ToolUseEvent, error: Exception) -> HookResult:
        if not self.enabled or not self._mlflow:
            return HookResult.allow({"hook": self.name, "enabled": self.enabled})

        try:
            with self._mlflow.start_run(
                run_name=f"{event.agent_id}:{event.tool_name}:error"
            ):
                self._mlflow.log_params(
                    {
                        "agent_id": event.agent_id,
                        "tool_name": event.tool_name,
                        "error_type": type(error).__name__,
                    }
                )
                self._mlflow.log_metric("error_count", 1.0)
            return HookResult.allow({"hook": self.name, "error_logged": True})
        except Exception as e:
            logger.warning(f"MLflowHook on_error degraded: {e}")
            return HookResult.allow(
                {"hook": self.name, "error_logged": False, "error": str(e)}
            )
