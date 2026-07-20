"""Pillar 3 — Safety Controls (Defense in Depth).

Invariant: no single point of failure can allow an unsafe action to reach
production. ``SafetyStack`` composes independent safety layers with a
``CircuitBreaker`` so that when a preventive control fails repeatedly, the
agent halts before cascading damage occurs.
"""

from __future__ import annotations

import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

SafetyLayer = Callable[[Dict[str, Any]], bool]


class CircuitState(str, Enum):
    CLOSED = "closed"          #: normal operation
    OPEN = "open"               #: tripped; actions are denied
    HALF_OPEN = "half_open"    #: reset window elapsed; next check may re-close the breaker


class CircuitBreaker:
    """Trips after consecutive failures and denies actions until a cool-down elapses.

    This is the last line of defense in the safety stack: independent of
    what any individual layer decides, repeated failure trips the breaker
    and further actions are denied outright until ``reset_timeout`` passes.
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 30.0) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if time.time() - self._opened_at >= self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.time()

    def allow(self) -> bool:
        return self.state != CircuitState.OPEN


class AnomalyDetector:
    """A rolling z-score detector used as one independent safety layer.

    Flags a value as anomalous once enough samples have been observed to
    establish a baseline; the current value is always folded into the
    window afterward so the baseline adapts over time.
    """

    def __init__(self, window_size: int = 20, z_threshold: float = 3.0, min_samples: int = 5) -> None:
        if min_samples < 2:
            raise ValueError("min_samples must be >= 2")
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.min_samples = min_samples
        self._window: Deque[float] = deque(maxlen=window_size)

    def is_anomalous(self, value: float) -> bool:
        if len(self._window) < self.min_samples:
            self._window.append(value)
            return False
        mean = statistics.fmean(self._window)
        stdev = statistics.pstdev(self._window) or 1e-9
        z_score = abs(value - mean) / stdev
        self._window.append(value)
        return z_score >= self.z_threshold

    def as_layer(self, field_name: str) -> SafetyLayer:
        """Adapt this detector into a :data:`SafetyLayer` over ``action[field_name]``."""

        def _layer(action: Dict[str, Any]) -> bool:
            if field_name not in action:
                return True
            return not self.is_anomalous(action[field_name])

        _layer.__name__ = f"anomaly_detector[{field_name}]"
        return _layer


@dataclass
class SafetyCheckResult:
    safe: bool
    failed_layers: List[str] = field(default_factory=list)
    breaker_state: CircuitState = CircuitState.CLOSED


class SafetyStack:
    """Runs every registered layer independently; any failure denies the action.

    Layers are intentionally independent of each other and of Pillar 1's
    constraint engine, so that a single defect (a bad constraint config, a
    blind spot in one detector) cannot by itself let an unsafe action
    through. Repeated layer failures trip the shared :class:`CircuitBreaker`.
    """

    def __init__(self, layers: Optional[List[SafetyLayer]] = None, breaker: Optional[CircuitBreaker] = None) -> None:
        self.layers: List[SafetyLayer] = list(layers or [])
        self.breaker = breaker or CircuitBreaker()

    def add_layer(self, layer: SafetyLayer) -> None:
        self.layers.append(layer)

    def check(self, action: Dict[str, Any]) -> SafetyCheckResult:
        if not self.breaker.allow():
            return SafetyCheckResult(
                safe=False, failed_layers=["circuit_breaker_open"], breaker_state=self.breaker.state
            )

        failed: List[str] = []
        for index, layer in enumerate(self.layers):
            name = getattr(layer, "__name__", repr(layer))
            try:
                if not layer(action):
                    failed.append(f"layer_{index}:{name}")
            except Exception as exc:  # a misbehaving layer must not silently pass the action
                failed.append(f"layer_{index}:{name}:error={exc}")

        if failed:
            self.breaker.record_failure()
        else:
            self.breaker.record_success()

        return SafetyCheckResult(safe=not failed, failed_layers=failed, breaker_state=self.breaker.state)
