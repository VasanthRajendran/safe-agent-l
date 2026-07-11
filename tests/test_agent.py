import time

from safeagentl.agent import ConformanceLevel, SafeAgent
from safeagentl.constraints import Constraint, ConstraintEngine
from safeagentl.explainability import DecisionLogger
from safeagentl.network import PartitionTolerantCache, TimeoutToSafeDefault
from safeagentl.safety import CircuitBreaker, SafetyStack


def build_agent(**overrides):
    defaults = dict(
        agent_id="pricing-agent-1",
        constraint_engine=ConstraintEngine([Constraint(field="price", op="gte", bound=10.0)]),
        logger=DecisionLogger(),
        safety_stack=SafetyStack(layers=[lambda action: action.get("price", 0) < 10_000]),
    )
    defaults.update(overrides)
    return SafeAgent(**defaults)


def test_decide_allows_compliant_action_and_logs_it():
    agent = build_agent()
    decision = agent.decide({"sku": "A1"}, propose_fn=lambda state: {"price": 25.0})
    assert decision.allowed is True
    assert decision.action == {"price": 25.0}
    assert decision.trace is not None
    assert agent.logger.reconstruct(decision.trace.decision_id).output == {"price": 25.0}


def test_decide_denies_action_violating_constraint():
    agent = build_agent()
    decision = agent.decide({"sku": "A1"}, propose_fn=lambda state: {"price": 1.0})
    assert decision.allowed is False
    assert decision.reason == "constraint_violation"
    assert decision.trace is not None  # denial is still traced


def test_decide_denies_action_flagged_unsafe():
    agent = build_agent()
    decision = agent.decide({"sku": "A1"}, propose_fn=lambda state: {"price": 999_999})
    assert decision.allowed is False
    assert decision.reason == "safety_control_triggered"


def test_decide_times_out_to_safe_default_under_network_degradation():
    guard = TimeoutToSafeDefault(timeout=0.05, safe_default={})
    agent = build_agent(timeout_guard=guard)
    try:
        decision = agent.decide({"sku": "A1"}, propose_fn=lambda state: time.sleep(0.5) or {"price": 25.0})
        assert decision.allowed is False
        assert decision.reason == "timeout_to_safe_default"
    finally:
        guard.shutdown()


def test_decide_notes_stale_policy_cache_in_reasoning():
    cache = PartitionTolerantCache(ttl_seconds=60)  # never synced -> stale
    agent = build_agent(policy_cache=cache)
    decision = agent.decide({"sku": "A1"}, propose_fn=lambda state: {"price": 25.0})
    assert any("stale" in line for line in decision.trace.reasoning)


def test_decide_uses_the_passed_in_empty_logger_and_engine_instances():
    # Regression test: `x or Default()` is a bug when `x` defines __len__,
    # since a freshly constructed, still-empty ConstraintEngine/DecisionLogger
    # is falsy and would be silently replaced by the `or` fallback.
    engine = ConstraintEngine()
    logger = DecisionLogger()
    agent = SafeAgent(agent_id="a", constraint_engine=engine, logger=logger)
    assert agent.constraint_engine is engine
    assert agent.logger is logger
    agent.decide({"sku": "A1"}, propose_fn=lambda state: {"price": 25.0})
    assert len(logger) == 1


def test_conformance_none_without_constraints_or_logging():
    agent = SafeAgent(agent_id="bare")
    assert agent.assess_conformance() == ConformanceLevel.NONE


def test_conformance_minimum_with_constraints_and_logging_only():
    agent = SafeAgent(
        agent_id="a",
        constraint_engine=ConstraintEngine([Constraint(field="price", op="gte", bound=1.0)]),
        logger=DecisionLogger(min_completeness=1.0),
    )
    assert agent.assess_conformance() == ConformanceLevel.MINIMUM


def test_conformance_recommended_with_defense_in_depth():
    agent = SafeAgent(
        agent_id="a",
        constraint_engine=ConstraintEngine([Constraint(field="price", op="gte", bound=1.0)]),
        logger=DecisionLogger(min_completeness=1.0),
        safety_stack=SafetyStack(layers=[lambda a: True, lambda a: True], breaker=CircuitBreaker()),
    )
    assert agent.assess_conformance() == ConformanceLevel.RECOMMENDED


def test_conformance_exemplary_with_all_four_pillars():
    guard = TimeoutToSafeDefault(timeout=1.0)
    try:
        agent = SafeAgent(
            agent_id="a",
            constraint_engine=ConstraintEngine([Constraint(field="price", op="gte", bound=1.0)]),
            logger=DecisionLogger(min_completeness=1.0),
            safety_stack=SafetyStack(layers=[lambda a: True, lambda a: True]),
            policy_cache=PartitionTolerantCache(),
            timeout_guard=guard,
        )
        assert agent.assess_conformance() == ConformanceLevel.EXEMPLARY
    finally:
        guard.shutdown()
