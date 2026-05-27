"""Exponential backoff retry for external API calls.

Retries on 429 (rate limit) and 5xx (server error) only.
Non-retriable errors (4xx except 429) are re-raised immediately.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceUnavailableError(Exception):
    """Raised when an external service fails after all retries."""

    def __init__(self, service: str, last_status: int | None = None):
        self.service = service
        self.last_status = last_status
        super().__init__(
            f"{service} is temporarily unavailable "
            f"(status {last_status}). Please try again later."
        )


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 32.0,
    service_name: str = "External service",
) -> T:
    """Execute fn with exponential backoff retry.

    Retries on:
    - HTTP 429 (rate limit)
    - HTTP 500, 502, 503, 504 (server errors)

    Does NOT retry on other 4xx errors.
    Raises ServiceUnavailableError after max_retries exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429 or status >= 500:
                last_exc = exc
                if attempt < max_retries:
                    delay = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(-0.5, 0.5)
                    sleep_for = max(0.0, delay + jitter)
                    logger.warning(
                        "%s returned %d on attempt %d/%d — retrying in %.1fs",
                        service_name,
                        status,
                        attempt + 1,
                        max_retries,
                        sleep_for,
                    )
                    await asyncio.sleep(sleep_for)
                    continue
                # Last attempt exhausted — fall through to raise ServiceUnavailableError
            else:
                raise  # non-retriable 4xx — re-raise immediately
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = min(base_delay * (2**attempt), max_delay)
                await asyncio.sleep(delay)
                continue
            raise

    raise ServiceUnavailableError(service_name) from last_exc
