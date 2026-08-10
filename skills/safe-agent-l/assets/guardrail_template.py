"""Starter skeleton for a safe-agent-l guardrail.

Copy this file, replace the marked sections with your domain's fields and
bounds, and delete what you do not use. Runs as-is:

    python guardrail_template.py

See references/domain-packs.md for ready-made field vocabularies and
starter constraints per domain.
"""

from __future__ import annotations

from typing import Any, Dict

from safeagentl import (
    AnomalyDetector,
    CircuitBreaker,
    Constraint,
    ConstraintEngine,
    DecisionLogger,
    EnforcementMode,
    SafeAgent,
    SafetyStack,
    TimeoutToSafeDefault,
)

# --------------------------------------------------------------------------
# 1. Constraints — one rule per field. REJECT to escalate, CLIP to correct.
#    Mark `required=True` on any rule that must always apply: a missing
#    field is ignored otherwise, which silently turns an allowlist into a
#    no-op.
# --------------------------------------------------------------------------
ALLOWED_TOOLS = ["lookup_order", "create_ticket", "issue_refund"]

constraints = ConstraintEngine(
    [
        Constraint(
            field="tool",
            op="in",
            bound=ALLOWED_TOOLS,
            reason="tool allowlist",
            required=True,
        ),
        Constraint(
            field="refund_amount",
            op="lte",
            bound=100.0,
            reason="autonomous refund cap; above this goes to a human",
        ),
        Constraint(
            field="refund_amount",
            op="gte",
            bound=0.0,
            reason="no negative refunds",
            mode=EnforcementMode.CLIP,
        ),
    ]
)

problems = constraints.verify_configuration()
if problems:
    raise SystemExit(f"Contradictory constraint configuration: {problems}")


# --------------------------------------------------------------------------
# 2. Safety layers — independent of the constraints on purpose. Any layer
#    returning False (or raising) denies the action. Name them: the name
#    shows up in SafetyCheckResult.failed_layers during an incident.
# --------------------------------------------------------------------------
def refund_has_order_id(action: Dict[str, Any]) -> bool:
    if action.get("tool") != "issue_refund":
        return True
    return bool(action.get("order_id"))


safety = SafetyStack(
    layers=[
        refund_has_order_id,
        AnomalyDetector(z_threshold=3.0).as_layer("refund_amount"),
    ],
    breaker=CircuitBreaker(failure_threshold=3, reset_timeout=30.0),
)


# --------------------------------------------------------------------------
# 3. The gate. sink_path makes the audit trail durable — the in-memory
#    index is not storage.
# --------------------------------------------------------------------------
gate = SafeAgent(
    agent_id="REPLACE-ME-agent",
    constraint_engine=constraints,
    logger=DecisionLogger(sink_path="audit.jsonl"),
    safety_stack=safety,
    timeout_guard=TimeoutToSafeDefault(timeout=0.5),
)


# --------------------------------------------------------------------------
# 4. Your agent. Flatten whatever it produces into one dict. No side
#    effects here — a timed-out proposal keeps running in its worker
#    thread. Side effects belong in the executor, behind the gate.
# --------------------------------------------------------------------------
def propose_fn(state: Dict[str, Any]) -> Dict[str, Any]:
    # call = my_llm_agent.next_tool_call(state)
    # return {"tool": call.name, **call.arguments}
    return {
        "tool": "issue_refund",
        "order_id": state.get("order_id"),
        "refund_amount": state.get("requested_amount", 0.0),
    }


def execute(action: Dict[str, Any]) -> None:
    print(f"  EXECUTED {action}")


def escalate(decision) -> None:
    print(f"  BLOCKED  reason={decision.reason}")
    for line in decision.trace.reasoning:
        print(f"           {line}")


# --------------------------------------------------------------------------
# 5. The loop. Execute decision.action, never the raw proposal.
# --------------------------------------------------------------------------
def handle(state: Dict[str, Any]) -> None:
    decision = gate.decide(state, propose_fn=propose_fn)
    if decision.allowed:
        execute(decision.action)
    else:
        escalate(decision)


if __name__ == "__main__":
    print("within the refund cap:")
    handle({"order_id": "A-1001", "requested_amount": 42.0})

    print("\nover the refund cap:")
    handle({"order_id": "A-1002", "requested_amount": 5000.0})

    print("\nmissing order_id (caught by a safety layer, not a constraint):")
    handle({"requested_amount": 20.0})

    print(f"\nself-assessed conformance: {gate.assess_conformance().value}")
