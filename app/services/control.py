"""Bound work admission, serialize sessions and suppress repeatedly failing models."""
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import monotonic

from app.runtime import RuntimeSettings, runtime


class BusyError(RuntimeError):
    pass


class RoutingTimeout(RuntimeError):
    pass


class RequestGate:
    def __init__(self, config: RuntimeSettings = runtime) -> None:
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._pending = 0

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        # These updates have no await between them: admission is atomic on
        # the process's single asyncio event loop, including cancellation.
        if self._pending >= self.config.max_pending:
            raise BusyError("Router is busy; retry later.")
        self._pending += 1
        acquired = False
        try:
            try:
                await asyncio.wait_for(
                    self._semaphore.acquire(), self.config.queue_timeout_s,
                )
            except TimeoutError as exc:
                raise BusyError("Router queue wait expired; retry later.") from exc
            acquired = True
            yield
        finally:
            if acquired:
                self._semaphore.release()
            self._pending -= 1


class SessionLocks:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[asyncio.Lock, int]] = {}

    @asynccontextmanager
    async def hold(self, session_id: str) -> AsyncIterator[None]:
        lock, users = self._entries.get(session_id, (asyncio.Lock(), 0))
        self._entries[session_id] = lock, users + 1
        try:
            async with lock:
                yield
        finally:
            _, users = self._entries[session_id]
            if users == 1:
                del self._entries[session_id]
            else:
                self._entries[session_id] = lock, users - 1


class CircuitBreaker:
    def __init__(self, config: RuntimeSettings = runtime) -> None:
        self.config = config
        self._failures: dict[str, tuple[int, float]] = {}

    def available(self, key: str) -> bool:
        count, when = self._failures.get(key, (0, 0.0))
        if count < self.config.breaker_failures:
            return True
        if monotonic() - when >= self.config.breaker_cooldown_s:
            self._failures.pop(key, None)
            return True
        return False

    def failure(self, key: str) -> None:
        count, _ = self._failures.get(key, (0, 0.0))
        self._failures[key] = count + 1, monotonic()

    def success(self, key: str) -> None:
        self._failures.pop(key, None)
