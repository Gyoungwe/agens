# utils/retry.py

import asyncio
import logging
from typing import Callable, Any, Tuple, Type

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """重试耗尽异常"""

    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"重试 {attempts} 次后失败: {last_error}")


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        OSError,
    ),
    on_retry: Callable[[int, Exception], None] = None,
    **kwargs,
) -> Any:
    """
    带指数退避的重试装饰器/函数

    Args:
        func: 异步函数
        *args: 函数参数
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数
        retryable_exceptions: 可重试的异常类型元组
        on_retry: 每次重试前的回调函数 (attempt, error)
        **kwargs: 函数关键字参数

    Returns:
        函数返回值

    Raises:
        RetryError: 重试耗尽后抛出
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except retryable_exceptions as e:
            last_error = e

            if attempt == max_retries:
                logger.error(f"❌ 重试耗尽 ({max_retries}/{max_retries}): {e}")
                raise RetryError(max_retries, e)

            delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)

            if on_retry:
                on_retry(attempt, e)

            logger.warning(
                f"⚠️  第 {attempt}/{max_retries} 次尝试失败: {e}, "
                f"等待 {delay:.1f}s 后重试..."
            )
            await asyncio.sleep(delay)

        except Exception as e:
            last_error = e
            logger.error(f"❌ 不可重试的错误: {e}")
            raise

    raise RetryError(max_retries, last_error)


def is_retryable(
    error: Exception,
    retryable: Tuple[Type[Exception], ...] = (TimeoutError, ConnectionError, OSError),
) -> bool:
    """判断异常是否可重试"""
    return isinstance(error, retryable)
