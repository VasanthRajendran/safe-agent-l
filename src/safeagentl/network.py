"""Pillar 4 — Network Awareness.

Invariant: safety controls must remain operational even when the
underlying network experiences degradation, partition, or failure.
Pillars 1-3 assume constraints, logs, and control signals are delivered
reliably; this module supplies the three network-layer requirements
SAFE-AGENT-L specifies to make that assumption safe to drop:
priority routing, timeout-to-safe-default, and partition tolerance.
"""

from __future__ import annotations

import heapq
import itertools
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Optional, Tuple


class Priority(IntEnum):
    """Lower value dispatches first. Safety-critical control signals — constraint
    updates, recall orders, circuit breaker triggers — must outrank routine traffic.
    """

    CRITICAL = 0
    HIGH = 1
    ROUTINE = 2


@dataclass(order=True)
class _QueueItem:
    priority: int
    seq: int
    message: Any = field(compare=False)


class PriorityRouter:
    """A priority queue guaranteeing CRITICAL control signals dispatch before
    routine agent-to-agent traffic, regardless of submission order.
    """

    def __init__(self) -> None:
        self._heap: list = []
        self._counter = itertools.count()

    def submit(self, message: Any, priority: Priority = Priority.ROUTINE) -> None:
        heapq.heappush(self._heap, _QueueItem(int(priority), next(self._counter), message))

    def dispatch_next(self) -> Optional[Any]:
        if not self._heap:
            return None
        return heapq.heappop(self._heap).message

    def drain(self):
        while self._heap:
            yield self.dispatch_next()

    def __len__(self) -> int:
        return len(self._heap)


class TimeoutToSafeDefault:
    """Wraps a safety-relevant call so that if it does not complete within
    ``timeout`` seconds, the system falls back to ``safe_default`` instead of
    proceeding without verification — a deny-by-default under degraded network
    conditions rather than a fail-open.
    """

    def __init__(self, timeout: float, safe_default: Any = False, max_workers: int = 4) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.timeout = timeout
        self.safe_default = safe_default
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Tuple[Any, bool]:
        """Run ``fn`` under the timeout. Returns ``(result, timed_out)``."""
        future = self._executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=self.timeout), False
        except FutureTimeoutError:
            return self.safe_default, True

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    def __enter__(self) -> "TimeoutToSafeDefault":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.shutdown()


class PartitionTolerantCache:
    """Keeps the last-known-good safety policy available locally so an agent
    can keep enforcing it during a network partition, then resynchronizes
    once connectivity is restored.

    ``get()`` deliberately still returns a stale value rather than raising,
    because the read path (an agent checking "is this still allowed?")
    must keep functioning during a partition; callers that need to react to
    staleness inspect the returned flag.
    """

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._value: Optional[Any] = None
        self._fetched_at: Optional[float] = None

    @property
    def is_stale(self) -> bool:
        if self._fetched_at is None:
            return True
        return (time.time() - self._fetched_at) > self.ttl_seconds

    def get(self) -> Tuple[Optional[Any], bool]:
        """Returns ``(value, is_stale)``."""
        return self._value, self.is_stale

    def sync(self, fetch_fn: Callable[[], Any]) -> bool:
        """Attempt to refresh from the source of truth.

        Returns ``True`` on success. On failure (e.g. the fetch raises
        because the network is partitioned) the previously cached value is
        left untouched, so the agent keeps operating on it.
        """
        try:
            self._value = fetch_fn()
            self._fetched_at = time.time()
            return True
        except Exception:
            return False
