"""SafeAgent — composes the four SAFE-AGENT-L pillars around one decision.

This module does not add new invariants of its own; it is the reference
wiring showing how the four pillars interact, as called for by the
proposed IEEE Recommended Practice's "reference architecture" requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .constraints import ConstraintEngine, EnforcementResult
from .explainability import DecisionLogger, DecisionTrace
from .network import PartitionTolerantCache, TimeoutToSafeDefault
from .safety import SafetyCheckResult, SafetyStack


class ConformanceLevel(str, Enum):
    """Assessment levels defined by the proposed standard's scope section."""

    NONE = "none"
    MINIMUM = "minimum"
    RECOMMENDED = "recommended"
    EXEMPLARY = "exemplary"


@dataclass
class Decision:
    allowed: bool
    action: Dict[str, Any]
    trace: Optional[DecisionTrace]
    reason: str = ""


class SafeAgent:
    """Runs a proposed action through all four pillars before it is executed.

    Pipeline order matters: a network-aware timeout guard wraps the
    proposal step itself (Pillar 4), then the proposed action is
    constrained to the legal action space (Pillar 1), then checked by the
    independent safety layers (Pillar 3); every outcome — allowed or
    denied — is logged as a complete, reconstructable trace (Pillar 2).
    """

    def __init__(
        self,
        agent_id: str,
        constraint_engine: Optional[ConstraintEngine] = None,
        logger: Optional[DecisionLogger] = None,
        safety_stack: Optional[SafetyStack] = None,
        policy_cache: Optional[PartitionTolerantCache] = None,
        timeout_guard: Optional[TimeoutToSafeDefault] = None,
    ) -> None:
        self.agent_id = agent_id
        # NB: deliberately `is not None` rather than `x or Default()` — both
        # ConstraintEngine and DecisionLogger define __len__, so an empty
        # (but valid) instance passed in would be falsy and silently
        # replaced by `or`.
        self.constraint_engine = constraint_engine if constraint_engine is not None else ConstraintEngine()
        self.logger = logger if logger is not None else DecisionLogger()
        self.safety_stack = safety_stack if safety_stack is not None else SafetyStack()
        self.policy_cache = policy_cache
        self.timeout_guard = timeout_guard

    def decide(
        self,
        input_state: Dict[str, Any],
        propose_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Decision:
        """Produce a governed decision for ``input_state`` using ``propose_fn``
        as the underlying (unconstrained) agent policy.
        """
        reasoning: List[str] = []

        if self.policy_cache is not None:
            _, stale = self.policy_cache.get()
            if stale:
                reasoning.append("policy cache stale: enforcing last-known-good policy (partition tolerance)")

        if self.timeout_guard is not None:
            proposed, timed_out = self.timeout_guard.run(propose_fn, input_state)
            if timed_out:
                reasoning.append("proposal exceeded timeout budget; defaulted to safe (deny) state")
                trace = self._log(input_state, [], {}, reasoning, allowed=False)
                return Decision(allowed=False, action={}, trace=trace, reason="timeout_to_safe_default")
        else:
            proposed = propose_fn(input_state)

        enforcement: EnforcementResult = self.constraint_engine.enforce(proposed)
        reasoning.extend(enforcement.applied_constraints)

        if not enforcement.allowed:
            trace = self._log(
                input_state, enforcement.applied_constraints, enforcement.action, reasoning, allowed=False
            )
            return Decision(allowed=False, action=enforcement.action, trace=trace, reason="constraint_violation")

        safety_result: SafetyCheckResult = self.safety_stack.check(enforcement.action)
        if not safety_result.safe:
            reasoning.append(f"safety layers denied action: {safety_result.failed_layers}")
            trace = self._log(
                input_state, enforcement.applied_constraints, enforcement.action, reasoning, allowed=False
            )
            return Decision(allowed=False, action=enforcement.action, trace=trace, reason="safety_control_triggered")

        trace = self._log(input_state, enforcement.applied_constraints, enforcement.action, reasoning, allowed=True)
        return Decision(allowed=True, action=enforcement.action, trace=trace, reason="")

    def _log(
        self,
        input_state: Dict[str, Any],
        applied_constraints: List[str],
        output: Dict[str, Any],
        reasoning: List[str],
        allowed: bool,
    ) -> DecisionTrace:
        trace = DecisionTrace(
            agent_id=self.agent_id,
            input_state=dict(input_state),
            applied_constraints=list(applied_constraints),
            output=dict(output),
            reasoning=list(reasoning) + [f"allowed={allowed}"],
        )
        return self.logger.log(trace)

    def assess_conformance(self) -> ConformanceLevel:
        """Self-assess against the draft standard's conformance levels.

        This is a convenience heuristic for development use, not a
        substitute for third-party conformance assessment.
        """
        has_constraints = len(self.constraint_engine) > 0
        has_full_logging = self.logger.min_completeness >= 1.0
        has_defense_in_depth = len(self.safety_stack.layers) >= 2
        has_network_awareness = self.policy_cache is not None and self.timeout_guard is not None

        if not (has_constraints and has_full_logging):
            return ConformanceLevel.NONE
        if not has_defense_in_depth:
            return ConformanceLevel.MINIMUM
        if not has_network_awareness:
            return ConformanceLevel.RECOMMENDED
        return ConformanceLevel.EXEMPLARY
