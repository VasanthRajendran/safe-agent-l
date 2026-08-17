"""safe-agent-l: a Python runtime enforcement library for governed
autonomous AI agent systems, implementing the four SAFE-AGENT-L controls.

One control per module:

* :mod:`safeagentl.constraints`     — constraint enforcement (legal compliance by design)
* :mod:`safeagentl.explainability`  — auditable decision traces
* :mod:`safeagentl.safety`          — defense-in-depth safety controls
* :mod:`safeagentl.network`         — fail-closed, network-aware resilience

:class:`safeagentl.agent.SafeAgent` composes all four into a single
decision pipeline.
"""

from .agent import ConformanceLevel, Decision, SafeAgent
from .constraints import (
    Constraint,
    ConstraintEngine,
    EnforcementMode,
    EnforcementResult,
    InvalidConstraintError,
)
from .explainability import DecisionLogger, DecisionTrace, TraceIncompleteError
from .network import PartitionTolerantCache, Priority, PriorityRouter, TimeoutToSafeDefault
from .safety import AnomalyDetector, CircuitBreaker, CircuitState, SafetyCheckResult, SafetyStack

__version__ = "0.2.0"

__all__ = [
    "SafeAgent",
    "Decision",
    "ConformanceLevel",
    "Constraint",
    "ConstraintEngine",
    "EnforcementMode",
    "EnforcementResult",
    "InvalidConstraintError",
    "DecisionLogger",
    "DecisionTrace",
    "TraceIncompleteError",
    "AnomalyDetector",
    "CircuitBreaker",
    "CircuitState",
    "SafetyStack",
    "SafetyCheckResult",
    "PriorityRouter",
    "Priority",
    "TimeoutToSafeDefault",
    "PartitionTolerantCache",
    "__version__",
]
