"""Pillar 2 — Explainability.

Invariant: every autonomous decision must be traceable and explainable to
regulators, auditors, and affected parties. ``DecisionLogger`` records a
:class:`DecisionTrace` with enough granularity to reconstruct the input
state, applied constraints, and output selection for any agent action.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

REQUIRED_TRACE_FIELDS = (
    "decision_id",
    "timestamp",
    "agent_id",
    "input_state",
    "applied_constraints",
    "output",
)


class TraceIncompleteError(Exception):
    """Raised when a decision trace does not meet the logger's completeness bar."""


@dataclass
class DecisionTrace:
    """A reconstructable record of a single autonomous decision.

    Captures the input state, which constraints were applied, the
    resulting output, and a free-text reasoning chain, so the decision can
    be replayed and explained after the fact.
    """

    agent_id: str
    input_state: Dict[str, Any]
    applied_constraints: List[str]
    output: Dict[str, Any]
    reasoning: List[str] = field(default_factory=list)
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def completeness_score(self) -> float:
        """Fraction of :data:`REQUIRED_TRACE_FIELDS` that are populated.

        An empty ``dict``/``list`` is a legitimate value (e.g. no
        constraints applied, or no output on a denial) and counts as
        present; only ``None`` or an empty identifier string counts as
        missing.
        """
        checks = {
            "decision_id": bool(self.decision_id),
            "timestamp": self.timestamp is not None and self.timestamp > 0,
            "agent_id": bool(self.agent_id),
            "input_state": self.input_state is not None,
            "applied_constraints": self.applied_constraints is not None,
            "output": self.output is not None,
        }
        return sum(checks.values()) / len(REQUIRED_TRACE_FIELDS)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionLogger:
    """Stores decision traces and enforces the explainability invariant.

    Traces below ``min_completeness`` are rejected at log time rather than
    silently accepted, so gaps in the reasoning chain are caught before
    they reach an audit. When ``retention_seconds`` is set, traces older
    than the window are evicted from the in-memory index (the append-only
    ``sink_path`` file, if configured, is never truncated).
    """

    def __init__(
        self,
        retention_seconds: Optional[float] = None,
        min_completeness: float = 1.0,
        sink_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.retention_seconds = retention_seconds
        self.min_completeness = min_completeness
        self.sink_path = Path(sink_path) if sink_path else None
        self._traces: Dict[str, DecisionTrace] = {}

    def log(self, trace: DecisionTrace) -> DecisionTrace:
        score = trace.completeness_score()
        if score < self.min_completeness:
            raise TraceIncompleteError(
                f"Decision trace is {score:.0%} complete; this logger requires "
                f"{self.min_completeness:.0%}. Missing one or more of: {REQUIRED_TRACE_FIELDS}"
            )
        self._traces[trace.decision_id] = trace
        if self.sink_path is not None:
            with self.sink_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(trace.to_dict(), default=str) + "\n")
        self._evict_expired()
        return trace

    def _evict_expired(self) -> None:
        if self.retention_seconds is None:
            return
        cutoff = time.time() - self.retention_seconds
        expired = [tid for tid, t in self._traces.items() if t.timestamp < cutoff]
        for tid in expired:
            del self._traces[tid]

    def reconstruct(self, decision_id: str) -> DecisionTrace:
        """Return the full trace for a given decision, for audit or regulator review."""
        try:
            return self._traces[decision_id]
        except KeyError:
            raise KeyError(f"No decision trace found for id '{decision_id}'") from None

    def all_traces(self) -> List[DecisionTrace]:
        return list(self._traces.values())

    def __len__(self) -> int:
        return len(self._traces)
