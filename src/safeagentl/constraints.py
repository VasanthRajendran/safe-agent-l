"""Pillar 1 — Legal Compliance by Design.

Invariant: legal and contractual violations must be architecturally
impossible, not merely discouraged. ``ConstraintEngine`` restricts an
agent's action space so that impermissible outputs cannot leave the
system, rather than trusting the agent to choose to follow the rule.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class EnforcementMode(str, Enum):
    """How a violated constraint is handled."""

    REJECT = "reject"  #: deny the action outright
    CLIP = "clip"       #: coerce the value to the nearest permitted bound


_COMPARATORS = {
    "gte": operator.ge,
    "lte": operator.le,
    "gt": operator.gt,
    "lt": operator.lt,
    "eq": operator.eq,
    "in": lambda value, bound: value in bound,
    "not_in": lambda value, bound: value not in bound,
}

_CLIPPABLE_OPS = {"gte", "lte", "gt", "lt"}


class InvalidConstraintError(ValueError):
    """Raised when a constraint is malformed or cannot be enforced as configured."""


@dataclass(frozen=True)
class Constraint:
    """A single machine-readable policy rule restricting one field of an action.

    Example: a contractual minimum-advertised-price rule is expressed as
    ``Constraint(field="price", op="gte", bound=19.99, mode=EnforcementMode.REJECT)``.
    """

    field: str
    op: str
    bound: Any
    mode: EnforcementMode = EnforcementMode.REJECT
    reason: str = ""

    def __post_init__(self) -> None:
        if self.op not in _COMPARATORS:
            raise InvalidConstraintError(
                f"Unknown constraint operator '{self.op}'. Valid operators: {sorted(_COMPARATORS)}"
            )
        if self.mode == EnforcementMode.CLIP and self.op not in _CLIPPABLE_OPS:
            raise InvalidConstraintError(
                f"Operator '{self.op}' cannot be used with EnforcementMode.CLIP "
                f"(only {sorted(_CLIPPABLE_OPS)} define a well-defined nearest bound)."
            )

    def is_satisfied(self, value: Any) -> bool:
        return _COMPARATORS[self.op](value, self.bound)

    def clip(self, value: Any) -> Any:
        if self.op in ("gte", "gt"):
            return self.bound if not self.is_satisfied(value) else value
        if self.op in ("lte", "lt"):
            return self.bound if not self.is_satisfied(value) else value
        raise InvalidConstraintError(f"Operator '{self.op}' is not clippable")

    def describe(self) -> str:
        label = f"{self.field} {self.op} {self.bound!r}"
        return f"{label} ({self.reason})" if self.reason else label


@dataclass
class EnforcementResult:
    """The outcome of running an action through a :class:`ConstraintEngine`."""

    action: Dict[str, Any]
    original_action: Dict[str, Any]
    applied_constraints: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    allowed: bool = True


class ConstraintEngine:
    """Restricts an agent's action space to what organization policy permits.

    Constraints are additive and independent per field: an action is only
    allowed through unmodified if every applicable constraint is satisfied.
    Every enforcement call is retained in :attr:`history` for auditability.
    """

    def __init__(self, constraints: List[Constraint] | None = None) -> None:
        self._constraints: Dict[str, List[Constraint]] = {}
        self.history: List[EnforcementResult] = []
        for constraint in constraints or []:
            self.add_constraint(constraint)

    def add_constraint(self, constraint: Constraint) -> None:
        self._constraints.setdefault(constraint.field, []).append(constraint)

    def constraints_for(self, field_name: str) -> List[Constraint]:
        return list(self._constraints.get(field_name, []))

    def __len__(self) -> int:
        return len(self._constraints)

    def verify_configuration(self) -> List[str]:
        """Pre-deployment check for contradictory constraints on the same field.

        Returns a list of human-readable problems; an empty list means the
        configured action space is not provably empty for any field.
        """
        problems: List[str] = []
        for field_name, constraints in self._constraints.items():
            lower_bounds = [c.bound for c in constraints if c.op in ("gte", "gt")]
            upper_bounds = [c.bound for c in constraints if c.op in ("lte", "lt")]
            if lower_bounds and upper_bounds and max(lower_bounds) > min(upper_bounds):
                problems.append(
                    f"Field '{field_name}' has contradictory bounds: "
                    f"minimum {max(lower_bounds)} exceeds maximum {min(upper_bounds)}"
                )
            eq_values = {c.bound for c in constraints if c.op == "eq"}
            if len(eq_values) > 1:
                problems.append(
                    f"Field '{field_name}' has conflicting equality constraints: {sorted(eq_values, key=str)}"
                )
        return problems

    def enforce(self, action: Dict[str, Any]) -> EnforcementResult:
        """Apply every registered constraint to ``action`` and return the result.

        Fields with no registered constraints pass through unchanged. A
        field is rejected (``allowed=False``) if any REJECT-mode constraint
        on it is violated; CLIP-mode constraints instead coerce the value.
        """
        enforced = dict(action)
        applied: List[str] = []
        violations: List[str] = []
        allowed = True

        for field_name, constraints in self._constraints.items():
            if field_name not in enforced:
                continue
            value = enforced[field_name]
            for constraint in constraints:
                if constraint.is_satisfied(value):
                    continue
                violations.append(constraint.describe())
                if constraint.mode == EnforcementMode.CLIP:
                    value = constraint.clip(value)
                    enforced[field_name] = value
                    applied.append(f"clipped '{field_name}' to satisfy {constraint.describe()}")
                else:
                    allowed = False
                    applied.append(f"rejected: '{field_name}' violates {constraint.describe()}")

        result = EnforcementResult(
            action=enforced,
            original_action=dict(action),
            applied_constraints=applied,
            violations=violations,
            allowed=allowed,
        )
        self.history.append(result)
        return result
