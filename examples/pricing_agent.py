"""End-to-end example: a retail pricing agent governed by all four
SAFE-AGENT-L pillars.

Run with:

    python examples/pricing_agent.py
"""

from __future__ import annotations

import random

from safeagentl import (
    AnomalyDetector,
    Constraint,
    ConstraintEngine,
    DecisionLogger,
    EnforcementMode,
    PartitionTolerantCache,
    SafeAgent,
    SafetyStack,
    TimeoutToSafeDefault,
)


def propose_price(input_state: dict) -> dict:
    """Stand-in for an LLM- or RL-driven pricing policy the organization
    does not fully trust to respect business rules on its own.
    """
    base = input_state["reference_price"]
    noisy_price = base * random.uniform(0.6, 1.3)  # a policy that sometimes misbehaves
    return {"price": round(noisy_price, 2)}


def fetch_policy_from_source_of_truth() -> dict:
    return {"min_advertised_price": 19.99, "max_price": 499.99}


def main() -> None:
    # Pillar 1 — legal compliance by design: the agent cannot output a
    # price below the contractual MAP floor, and prices above the
    # catalog ceiling are clipped rather than rejected outright.
    constraint_engine = ConstraintEngine(
        [
            Constraint(field="price", op="gte", bound=19.99, reason="contractual MAP floor"),
            Constraint(field="price", op="lte", bound=499.99, mode=EnforcementMode.CLIP, reason="catalog ceiling"),
        ]
    )
    print("Pre-deployment constraint check:", constraint_engine.verify_configuration() or "OK")

    # Pillar 2 — explainability: every decision, allowed or denied, is
    # logged as a complete, reconstructable trace.
    logger = DecisionLogger(sink_path="decision_audit.jsonl")

    # Pillar 3 — defense in depth: an anomaly detector and a rule-based
    # layer are independent checks; either can veto the action.
    anomaly_detector = AnomalyDetector(window_size=10, z_threshold=2.5, min_samples=5)
    safety_stack = SafetyStack(
        layers=[
            anomaly_detector.as_layer("price"),
            lambda action: action.get("price", 0) > 0,
        ]
    )

    # Pillar 4 — network-aware resilience: the policy fetch is cached so
    # the agent keeps enforcing the last-known-good policy through a
    # partition, and the proposal step itself is timeout-guarded.
    policy_cache = PartitionTolerantCache(ttl_seconds=300)
    policy_cache.sync(fetch_policy_from_source_of_truth)
    timeout_guard = TimeoutToSafeDefault(timeout=0.25, safe_default={})

    agent = SafeAgent(
        agent_id="pricing-agent-1",
        constraint_engine=constraint_engine,
        logger=logger,
        safety_stack=safety_stack,
        policy_cache=policy_cache,
        timeout_guard=timeout_guard,
    )

    print("Conformance level:", agent.assess_conformance().value)

    for sku in ["SKU-1", "SKU-2", "SKU-3", "SKU-4", "SKU-5"]:
        decision = agent.decide(
            {"sku": sku, "reference_price": 50.0},
            propose_fn=propose_price,
        )
        status = "ALLOWED" if decision.allowed else f"DENIED ({decision.reason})"
        print(f"{sku}: {status} -> {decision.action}")

    timeout_guard.shutdown()
    print(f"\n{len(logger)} decisions logged to decision_audit.jsonl")


if __name__ == "__main__":
    main()
