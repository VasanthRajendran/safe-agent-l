# safe-agent-l

[![CI](https://github.com/VasanthRajendran/safe-agent-l/actions/workflows/tests.yml/badge.svg)](https://github.com/VasanthRajendran/safe-agent-l/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)

**safe-agent-l** is a Python runtime enforcement library for autonomous AI
agent systems. It sits between your agent's decision-making — an LLM, a
reinforcement-learning policy, a rules engine — and the actions that reach
production, and applies four independent controls at the point of action:

1. **Constraint enforcement** — machine-readable policy rules (price floors,
   allowlisted tools, quantity ceilings) reject or clip impermissible actions
   before they execute, instead of trusting the agent to follow the rules.
2. **Auditable decision traces** — every decision, allowed or denied, is
   recorded as a complete, reconstructable trace; incomplete audit records
   are rejected at log time, not discovered during an investigation.
3. **Defense-in-depth safety controls** — independent safety layers (anomaly
   detection, custom checks) all evaluate every action, and a circuit
   breaker halts the agent after repeated failures.
4. **Fail-closed resilience** — guardrail checks that time out default to
   *deny*, and last-known-good policy stays enforced through network
   degradation and partitions, resynchronizing on recovery.

The library is pure Python with **zero runtime dependencies**, is fully
typed (`py.typed`), and wraps any agent that can express an action as a
dictionary — it is not itself an LLM agent and does not call any model API.

## What problem does this solve?

Agents that set prices, issue refunds, call tools, or drive workflows act
faster than human review cycles. Prompt-level instructions ("never price
below $19.99") are suggestions, not controls: the model can ignore them,
and you cannot prove to an auditor that it didn't. safe-agent-l moves those
rules out of the prompt and into an enforcement layer the agent's output
must pass through, with an audit trail for every outcome.

**Who it's for:** teams deploying autonomous or semi-autonomous agents that
take consequential actions, and platform/safety engineers who need
guardrails and decision evidence that survive an incident review.

## How it works

```
input state ──► propose_fn (your agent) ──► TimeoutToSafeDefault   (timeout → deny)
                                                    │
                                                    ▼
                                            ConstraintEngine       (violation → deny or clip)
                                                    │
                                                    ▼
                                            SafetyStack             (any layer fails → deny;
                                                    │                repeated failures trip breaker)
                                                    ▼
                                            allowed action
                                                    
every outcome (allowed or denied) ────────► DecisionLogger          (complete, reconstructable trace)
```

`SafeAgent.decide()` runs this pipeline for one action. Each pillar is also
usable standalone — you can adopt just the `ConstraintEngine` in front of an
existing agent, or just the `DecisionLogger` for audit trails.

## What this does not guarantee

Be clear-eyed about what a library can and cannot do:

- **It does not guarantee legal or regulatory compliance.** It enforces the
  constraints *you configure* and produces evidence they were applied. Whether
  those constraints are legally correct and complete is your responsibility,
  with your legal and compliance teams.
- **It is not a complete safety system.** It is one enforcement layer.
  Deployment controls, monitoring, human escalation paths, and incident
  response still belong to you.
- **Enforcement is in-process.** Code that calls your tools or APIs directly,
  without going through `SafeAgent.decide()`, bypasses every control here.
  Place enforcement at a boundary the agent cannot route around (see
  [docs/security.md](docs/security.md)).
- **The anomaly detector is a statistical baseline**, not a substitute for
  domain-specific safety checks.
- **This is not legal advice** and carries no certification against any
  standard or regulation.

## Installation

```bash
pip install safe-agent-l
```

Or from source:

```bash
pip install git+https://github.com/VasanthRajendran/safe-agent-l.git
```

Or for development:

```bash
git clone https://github.com/VasanthRajendran/safe-agent-l.git
cd safe-agent-l
pip install -e ".[dev]"
```

Requires Python 3.9+. No runtime dependencies.

## Quickstart

```python
from safeagentl import Constraint, ConstraintEngine, DecisionLogger, SafeAgent, SafetyStack

# Constraint enforcement: prices below the contractual floor cannot execute.
constraints = ConstraintEngine([
    Constraint(field="price", op="gte", bound=19.99, reason="contractual MAP floor"),
])

# Auditability: every decision is logged with a reconstructable trace.
logger = DecisionLogger()

# Defense in depth: independent safety layers must all pass.
safety = SafetyStack(layers=[lambda action: action["price"] > 0])

agent = SafeAgent(
    agent_id="pricing-agent-1",
    constraint_engine=constraints,
    logger=logger,
    safety_stack=safety,
)

decision = agent.decide(
    {"sku": "ABC123"},
    propose_fn=lambda state: {"price": 9.99},  # below the floor
)

print(decision.allowed)          # False
print(decision.reason)           # "constraint_violation"
print(decision.trace.reasoning)  # full audit trail for this decision
```

## Integrating with an existing agent

Your agent stays whatever it already is; safe-agent-l only needs a
`propose_fn` that maps input state to a proposed action dictionary:

```python
def propose_fn(state: dict) -> dict:
    # call your LLM / policy / planner here
    tool_call = my_llm_agent.plan(state)
    return {"tool": tool_call.name, **tool_call.arguments}

decision = agent.decide(state, propose_fn=propose_fn)
if decision.allowed:
    execute_tool(decision.action)   # only ever execute the governed action
else:
    escalate_to_human(decision)     # trace explains exactly why it was denied
```

The key integration rule: **execute `decision.action`, never the raw
proposal.** See [docs/integrations.md](docs/integrations.md) for
tool-calling gates, workflow guardrails, and audit-log export, and
[`examples/`](examples/) for runnable end-to-end scripts:

- [`examples/pricing_agent.py`](examples/pricing_agent.py) — pricing agent with all four pillars, including timeout and partition handling
- [`examples/tool_approval_gate.py`](examples/tool_approval_gate.py) — approval gate for a tool-calling agent, with audit-log export
- [`examples/generic_agent_guard.py`](examples/generic_agent_guard.py) — generic tool-calling agent example with allowed and denied operations

## API overview

| Concern | Module | Key classes |
|---|---|---|
| Constraint enforcement | `safeagentl.constraints` | `Constraint`, `ConstraintEngine` |
| Auditable decision traces | `safeagentl.explainability` | `DecisionTrace`, `DecisionLogger` |
| Defense-in-depth safety | `safeagentl.safety` | `AnomalyDetector`, `CircuitBreaker`, `SafetyStack` |
| Fail-closed resilience | `safeagentl.network` | `PriorityRouter`, `TimeoutToSafeDefault`, `PartitionTolerantCache` |
| Orchestration | `safeagentl.agent` | `SafeAgent`, `Decision`, `ConformanceLevel` |

Full reference: [docs/api.md](docs/api.md). Concepts and design rationale:
[docs/concepts.md](docs/concepts.md).

## API stability

Pre-1.0: minor versions (0.x) may contain breaking changes, always listed in
[CHANGELOG.md](CHANGELOG.md). The public API is exactly the set of names
exported from the top-level `safeagentl` package; anything imported from
submodules with a leading underscore is internal. From 1.0 onward the
project will follow semantic versioning.

## Development

```bash
pip install -e ".[dev]"
pytest                        # test suite
pytest --cov=safeagentl       # with coverage
ruff check .                  # lint
mypy                          # type check
```

## Reporting security issues

Please do not open public issues for vulnerabilities — including bugs that
allow constraint, safety-layer, or audit-log bypass, which we treat as
security-relevant. See [SECURITY.md](SECURITY.md) for private reporting
instructions.

## Relationship to the SAFE-AGENT-L standardization effort

The SAFE-AGENT-L governance framework was presented to the IEEE Future
Networks AI/ML Working Group in February 2026 and is in PAR (Project
Authorization Request) review within IEEE ComSoc COM/NetSoft SC toward a
proposed IEEE Recommended Practice. This library is an independent,
permissively licensed implementation of the framework's four pillars. It is
not part of the IEEE standardization process and makes no claim of
conformance to a not-yet-published standard.

## Project

- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [CHANGELOG.md](CHANGELOG.md) — release history
- [ROADMAP.md](ROADMAP.md) — where the project is going
- [SECURITY.md](SECURITY.md) — vulnerability reporting
- [MAINTAINERS.md](MAINTAINERS.md) — governance and support expectations
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [docs/](docs/) — concepts, API reference, integration guides

## Citation

If you use this software in academic work, please cite it — see
[`CITATION.cff`](CITATION.cff) and the software paper in
[`paper/paper.md`](paper/paper.md).

## License

MIT — see [LICENSE](LICENSE).
