# utils/logging.py
"""
结构化日志工具

全链路日志字段:
- timestamp: ISO 格式时间戳
- level: 日志级别
- trace_id: 追踪 ID
- session_id: 会话 ID
- correlation_id: 关联 ID
- agent_id: Agent ID
- event: 事件类型
- message: 日志消息
- duration_ms: 耗时（毫秒）
- extra: 额外字段
"""

import json
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def __init__(self):
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id
        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        if hasattr(record, "agent_id"):
            log_data["agent_id"] = record.agent_id
        if hasattr(record, "event"):
            log_data["event"] = record.event
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ContextLogger:
    """
    上下文日志记录器

    自动注入 trace_id, session_id, correlation_id 等上下文字段
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}

    def set_context(self, **kwargs):
        """设置日志上下文"""
        self._context.update(kwargs)

    def clear_context(self):
        """清除日志上下文"""
        self._context = {}

    def _log_with_context(self, level: int, msg: str, exc_info=None, **kwargs):
        extra = {**self._context, **kwargs}
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown)",
            0,
            msg,
            (),
            exc_info,
        )
        for k, v in extra.items():
            if v is not None:
                setattr(record, k, v)
        self._logger.handle(record)

    def debug(self, msg: str, **kwargs):
        self._log_with_context(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log_with_context(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log_with_context(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, exc_info=None, **kwargs):
        self._log_with_context(logging.ERROR, msg, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, exc_info=None, **kwargs):
        self._log_with_context(logging.CRITICAL, msg, exc_info=exc_info, **kwargs)


class TimedLogger:
    """
    带计时的日志记录器

    示例:
        with TimedLogger(logger, "operation_name") as timed:
            timed.agent_id = "my_agent"
            # do something
        # 自动记录耗时
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        trace_id: str = None,
        session_id: str = None,
    ):
        self._logger = logger
        self._operation = operation
        self._start_time = time.time()
        self._record = None

    def __enter__(self):
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self._start_time) * 1000)

        if exc_type is not None:
            self._logger.error(
                f"{self._operation} failed after {duration_ms}ms",
                exc_info=(exc_type, exc_val, exc_tb),
            )
        else:
            self._logger.info(f"{self._operation} completed in {duration_ms}ms")

        return False

    def log(self, level: int, msg: str, **kwargs):
        duration_ms = int((time.time() - self._start_time) * 1000)
        extra = {"duration_ms": duration_ms, "operation": self._operation, **kwargs}
        self._logger.log(level, msg, extra=extra)


def setup_structured_logging(level: str = "INFO"):
    """配置结构化日志"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(handler)

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)


def get_context_logger(name: str) -> ContextLogger:
    """获取带上下文的日志记录器"""
    return ContextLogger(name)
