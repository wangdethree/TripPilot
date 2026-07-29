"""Idempotent command execution for the local runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import TypeVar, cast

from trippilot.domain.enums import ErrorCode
from trippilot.domain.errors import DomainError

T = TypeVar("T")


class InMemoryIdempotencyStore:
    """Cache command results by a hashed key and canonical request digest."""

    def __init__(self) -> None:
        self._results: dict[tuple[str, str], tuple[str, object]] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        *,
        scope: str,
        key: str | None,
        request: Mapping[str, object],
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        if key is None:
            return await operation()
        normalized_key = key.strip()
        if not normalized_key or len(normalized_key) > 200:
            raise ValueError("Idempotency-Key 长度必须在 1 到 200 之间")
        key_hash = hashlib.sha256(normalized_key.encode()).hexdigest()
        request_hash = hashlib.sha256(
            json.dumps(
                request,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()
        cache_key = (scope, key_hash)
        async with self._lock:
            cached = self._results.get(cache_key)
            if cached is not None:
                cached_request_hash, cached_result = cached
                if cached_request_hash != request_hash:
                    raise DomainError(
                        ErrorCode.VERSION_CONFLICT,
                        "同一 Idempotency-Key 不能用于不同请求",
                    )
                return cast(T, cached_result)
            result = await operation()
            self._results[cache_key] = (request_hash, result)
            return result
