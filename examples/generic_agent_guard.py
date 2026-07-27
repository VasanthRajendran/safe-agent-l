"""Generic tool-calling agent integration example.

This example shows that SAFE-AGENT-L is not limited to pricing workflows.
It simulates a generic support agent that proposes tool calls, and a
SIGMA-like guardrail gate decides whether the proposed action is allowed
or denied before any tool is executed.

Run with:

    python examples/generic_agent_guard.py
"""

from __future__ import annotations

from typing import Any, Dict, List

from safeagentl import Constraint, ConstraintEngine, DecisionLogger, SafeAgent, SafetyStack

ALLOWED_TOOLS = ["lookup_customer", "create_ticket"]

# Simulated proposals from a generic tool-calling agent. The last two are
# intentionally policy-violating to illustrate both deny and cap behavior.
SCRIPTED_PROPOSALS: List[Dict[str, Any]] = [
    {"tool": "lookup_customer", "customer_id": "CUST-001", "refund_amount": 0.0},
    {"tool": "create_ticket", "customer_id": "CUST-001", "ticket_type": "billing", "refund_amount": 0.0},
    {"tool": "delete_account", "customer_id": "CUST-001", "refund_amount": 0.0},
    {"tool": "create_ticket", "customer_id": "CUST-001", "ticket_type": "billing", "refund_amount": 150.0},
]


def execute_tool(action: Dict[str, Any]) -> None:
    """Stand-in for the real tool call that only receives governed actions."""
    print(f"    executed tool: {action['tool']} for {action.get('customer_id', 'unknown')}")


def escalate_to_human(decision) -> None:
    print(f"    escalated to human review: {decision.reason}")


def main() -> None:
    # The CDE (Constraint Decision Engine) is the policy gate for this example.
    # It evaluates each proposed action against explicit rules before the agent can
    # execute anything, which is how the guardrail blocks risky tool calls.
    constraint_engine = ConstraintEngine(
        [
            Constraint(field="tool", op="in", bound=ALLOWED_TOOLS, reason="tool allowlist"),
            Constraint(field="refund_amount", op="lte", bound=100.0, reason="autonomous refund cap"),
        ]
    )

    logger = DecisionLogger()
    safety_stack = SafetyStack(layers=[lambda action: action.get("refund_amount", 0) >= 0])

    gate = SafeAgent(
        agent_id="generic-agent-guard",
        constraint_engine=constraint_engine,
        logger=logger,
        safety_stack=safety_stack,
    )

    proposals = iter(SCRIPTED_PROPOSALS)
    for step in range(len(SCRIPTED_PROPOSALS)):
        decision = gate.decide(
            {"step": step, "customer_id": "CUST-001"},
            propose_fn=lambda state: next(proposals),
        )

        verdict = "ALLOWED" if decision.allowed else "DENIED "
        print(f"[{step}] {verdict} {decision.action or decision.trace.output}")

        if decision.allowed:
            execute_tool(decision.action)
        else:
            escalate_to_human(decision)

    print("\nDecision trace summary:")
    for trace in logger.all_traces():
        print(f"  - {trace.decision_id[:8]}… {trace.output}")


if __name__ == "__main__":
    main()
