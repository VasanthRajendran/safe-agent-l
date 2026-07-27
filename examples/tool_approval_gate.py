"""Approval gate for a tool-calling agent, with audit-log export.

Scenario: a customer-support agent proposes tool calls (send an email,
issue a refund, look up an order). The organization's policy:

* only three tools are allowed at all;
* refunds above $100 must not execute autonomously (they are denied and
  escalate to a human);
* a burst of denied actions trips the circuit breaker and halts the agent.

The agent itself is a stub here — in production it would be an LLM
choosing tool calls. The gate does not care where proposals come from.

Run with:

    python examples/tool_approval_gate.py
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from safeagentl import (
    CircuitBreaker,
    Constraint,
    ConstraintEngine,
    DecisionLogger,
    SafeAgent,
    SafetyStack,
)

ALLOWED_TOOLS = ["lookup_order", "send_email", "issue_refund"]

# The proposals our stub "LLM agent" will make, in order. The third and
# fourth violate policy on purpose.
SCRIPTED_PROPOSALS: List[Dict[str, Any]] = [
    {"tool": "lookup_order", "order_id": "A-1001", "refund_amount": 0.0},
    {"tool": "issue_refund", "order_id": "A-1001", "refund_amount": 42.50},
    {"tool": "issue_refund", "order_id": "A-1002", "refund_amount": 950.00},  # over the cap
    {"tool": "delete_account", "order_id": "A-1002", "refund_amount": 0.0},   # tool not allowed
    {"tool": "send_email", "order_id": "A-1001", "refund_amount": 0.0},
]


def execute_tool(action: Dict[str, Any]) -> None:
    """Simulate the execution of an approved tool call."""
    print(f"    executed: {action['tool']}({action.get('order_id', '')})")


def escalate_to_human(decision) -> None:
    """Escalate a denied action for human review instead of executing it."""
    print(f"    escalated to human review: {decision.reason}")


def export_audit_log(logger: DecisionLogger, path: str) -> int:
    """Export every decision trace to a JSONL audit file for compliance review."""
    with open(path, "w", encoding="utf-8") as fh:
        for trace in logger.all_traces():
            fh.write(json.dumps(trace.to_dict(), default=str) + "\n")
    return len(logger)


def main() -> None:
    """Run the approval-gate example and show how policy violations are handled."""
    constraint_engine = ConstraintEngine(
        [
            Constraint(field="tool", op="in", bound=ALLOWED_TOOLS, reason="tool allowlist"),
            Constraint(field="refund_amount", op="lte", bound=100.0, reason="autonomous refund cap"),
        ]
    )
    logger = DecisionLogger()
    safety_stack = SafetyStack(
        layers=[lambda action: action.get("refund_amount", 0) >= 0],
        breaker=CircuitBreaker(failure_threshold=3, reset_timeout=60.0),
    )

    gate = SafeAgent(
        agent_id="support-agent-1",
        constraint_engine=constraint_engine,
        logger=logger,
        safety_stack=safety_stack,
    )

    proposals = iter(SCRIPTED_PROPOSALS)
    for step in range(len(SCRIPTED_PROPOSALS)):
        decision = gate.decide(
            {"customer": "cust-77", "step": step},
            propose_fn=lambda state: next(proposals),
        )
        verdict = "ALLOWED" if decision.allowed else "DENIED "
        print(f"[{step}] {verdict} {decision.action or decision.trace.output}")
        if decision.allowed:
            execute_tool(decision.action)  # never the raw proposal
        else:
            escalate_to_human(decision)

    exported = export_audit_log(logger, "tool_gate_audit.jsonl")
    print(f"\nExported {exported} decision traces to tool_gate_audit.jsonl")

    # Any single trace can be reconstructed for an auditor:
    example = logger.all_traces()[2]
    print(f"\nReconstructed trace {example.decision_id[:8]}…:")
    for line in example.reasoning:
        print(f"    {line}")


if __name__ == "__main__":
    main()
