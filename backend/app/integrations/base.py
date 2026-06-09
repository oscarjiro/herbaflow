"""Shared retry wrapper for external clients (the single retry home)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return isinstance(exc, httpx.TransportError)


async def with_retry[T](
    fn: Callable[[], Awaitable[T]], *, attempts: int = 3, base_delay: float = 0.5
) -> T:
    last: BaseException | None = None
    for i in range(attempts):
        try:
            return await fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            if not _is_retryable(exc) or i == attempts - 1:
                raise
            last = exc
            await asyncio.sleep(base_delay * (2**i))
    if last is not None:
        raise last
    raise RuntimeError("with_retry requires attempts >= 1")
