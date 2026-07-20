# safe-agent-l documentation

**safe-agent-l** is a Python runtime enforcement library for autonomous AI
agent systems. It wraps an agent's proposed actions with constraint
enforcement, auditable decision traces, defense-in-depth safety checks, and
fail-closed behavior under timeouts and network degradation.

## Where to start

| If you want to… | Read |
|---|---|
| Understand the design and the four controls | [concepts.md](concepts.md) |
| Look up a class or method | [api.md](api.md) |
| Put this in front of an existing agent | [integrations.md](integrations.md) |
| Understand the threat model and its limits | [security.md](security.md) |
| See runnable code | [`../examples/`](../examples/) |

## The 60-second version

```python
from safeagentl import Constraint, ConstraintEngine, SafeAgent

agent = SafeAgent(
    agent_id="my-agent",
    constraint_engine=ConstraintEngine([
        Constraint(field="amount", op="lte", bound=100.0, reason="autonomous cap"),
    ]),
)

decision = agent.decide(state, propose_fn=my_agent_policy)
if decision.allowed:
    execute(decision.action)      # the governed action — never the raw proposal
else:
    escalate(decision)            # decision.trace explains why it was denied
```

Everything else — safety layers, circuit breakers, timeout guards,
partition-tolerant policy caching, audit sinks — is opt-in composition on
top of this loop.

## Project links

- [README](../README.md) — overview, installation, quickstart
- [CHANGELOG](../CHANGELOG.md) · [ROADMAP](../ROADMAP.md) · [RELEASING](../RELEASING.md)
- [CONTRIBUTING](../CONTRIBUTING.md) · [SECURITY](../SECURITY.md) · [MAINTAINERS](../MAINTAINERS.md)
