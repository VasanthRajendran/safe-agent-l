# safe-agent-l

[![Tests](https://github.com/vasanthr430/safe-agent-l/actions/workflows/tests.yml/badge.svg)](https://github.com/vasanthr430/safe-agent-l/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A reference implementation of **SAFE-AGENT-L**, a governance framework for
autonomous AI agent systems built around four architectural invariants:

1. **Legal compliance by design** — impermissible actions are excluded from
   the agent's action space, not merely discouraged.
2. **Explainability** — every autonomous decision is logged as a complete,
   reconstructable trace.
3. **Defense-in-depth safety controls** — independent safety layers plus a
   circuit breaker mean no single point of failure lets an unsafe action
   through.
4. **Network-aware resilience** — safety controls (priority routing,
   timeout-to-safe-defaults, partition-tolerant policy caching) keep working
   when the network degrades or partitions.

This library exists to give the four pillars a concrete, testable
implementation that other governance tooling and research can build on or
compare against — see [`paper/paper.md`](paper/paper.md) for the
accompanying software paper. The pillars themselves are described in more
depth in the proposed IEEE Recommended Practice this project accompanies
(currently in PAR review).

## Installation

```bash
pip install safe-agent-l
```

Or from source:

```bash
git clone https://github.com/vasanthr430/safe-agent-l.git
cd safe-agent-l
pip install -e ".[dev]"
```

Requires Python 3.9+. No runtime dependencies.

## Quickstart

```python
from safeagentl import Constraint, ConstraintEngine, DecisionLogger, SafeAgent, SafetyStack

# Pillar 1: prices below the contractual MAP floor are architecturally impossible.
constraints = ConstraintEngine([
    Constraint(field="price", op="gte", bound=19.99, reason="contractual MAP floor"),
])

# Pillar 2: every decision is logged with a reconstructable trace.
logger = DecisionLogger()

# Pillar 3: independent safety layers must all pass.
safety = SafetyStack(layers=[lambda action: action["price"] > 0])

agent = SafeAgent(
    agent_id="pricing-agent-1",
    constraint_engine=constraints,
    logger=logger,
    safety_stack=safety,
)

decision = agent.decide(
    {"sku": "ABC123"},
    propose_fn=lambda state: {"price": 9.99},  # below the MAP floor
)

print(decision.allowed)          # False
print(decision.reason)           # "constraint_violation"
print(decision.trace.reasoning)  # full audit trail for this decision
```

See [`examples/pricing_agent.py`](examples/pricing_agent.py) for an
end-to-end example wiring up all four pillars, including network-aware
timeout and partition handling.

## API overview

| Pillar | Module | Key classes |
|---|---|---|
| 1. Legal compliance by design | `safeagentl.constraints` | `Constraint`, `ConstraintEngine` |
| 2. Explainability | `safeagentl.explainability` | `DecisionTrace`, `DecisionLogger` |
| 3. Defense in depth | `safeagentl.safety` | `AnomalyDetector`, `CircuitBreaker`, `SafetyStack` |
| 4. Network-aware resilience | `safeagentl.network` | `PriorityRouter`, `TimeoutToSafeDefault`, `PartitionTolerantCache` |
| Orchestration | `safeagentl.agent` | `SafeAgent`, `Decision`, `ConformanceLevel` |

`SafeAgent.assess_conformance()` gives a development-time self-assessment
against the framework's three conformance levels (minimum / recommended /
exemplary), based on which pillars are configured.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

## Relationship to the SAFE-AGENT-L standardization effort

SAFE-AGENT-L was presented to the IEEE Future Networks AI/ML Working Group
in February 2026 and is in PAR (Project Authorization Request) review within
IEEE ComSoc COM/NetSoft SC toward a proposed IEEE Recommended Practice. This
repository is an independent, permissively licensed reference implementation
of the four pillars — it is not itself part of the IEEE standardization
process and makes no claim of conformance to a not-yet-published standard.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Citation

If you use this software in academic work, please cite it — see
[`paper/paper.md`](paper/paper.md) and `CITATION.cff`.

## License

MIT — see [LICENSE](LICENSE).
