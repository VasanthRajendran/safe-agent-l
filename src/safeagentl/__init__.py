"""safe-agent-l: a reference implementation of the SAFE-AGENT-L governance
framework for autonomous AI agent systems.

Four pillars, one module each:

* :mod:`safeagentl.constraints`     — Pillar 1, legal compliance by design
* :mod:`safeagentl.explainability`  — Pillar 2, decision traceability
* :mod:`safeagentl.safety`          — Pillar 3, defense-in-depth safety controls
* :mod:`safeagentl.network`         — Pillar 4, network-aware resilience

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

__version__ = "0.1.0"

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
