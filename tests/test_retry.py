# tests/test_retry.py

import pytest
import asyncio
from utils.retry import retry_with_backoff, RetryError, is_retryable


class TestRetry:
    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        call_count = 0

        async def succeed():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(succeed, max_retries=3)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retryable_exception_retries(self):
        call_count = 0

        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "success"

        result = await retry_with_backoff(
            fail_twice,
            max_retries=3,
            base_delay=0.1,
            retryable_exceptions=(TimeoutError,),
        )
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_raises_directly(self):
        call_count = 0

        async def fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            await retry_with_backoff(
                fail,
                max_retries=3,
                base_delay=0.1,
                retryable_exceptions=(TimeoutError,),
            )
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_raises_retry_error(self):
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("always timeout")

        with pytest.raises(RetryError) as exc_info:
            await retry_with_backoff(
                always_fail,
                max_retries=3,
                base_delay=0.05,
                retryable_exceptions=(TimeoutError,),
            )
        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_error, TimeoutError)

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        call_count = 0
        retry_attempts = []

        def on_retry(attempt, error):
            retry_attempts.append(attempt)

        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "success"

        await retry_with_backoff(
            fail_twice,
            max_retries=3,
            base_delay=0.1,
            retryable_exceptions=(TimeoutError,),
            on_retry=on_retry,
        )
        assert retry_attempts == [1, 2]

    def test_is_retryable(self):
        assert (
            is_retryable(TimeoutError("test"), (TimeoutError, ConnectionError)) is True
        )
        assert (
            is_retryable(ValueError("test"), (TimeoutError, ConnectionError)) is False
        )
