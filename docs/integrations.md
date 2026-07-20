# Integration guide

safe-agent-l is framework-agnostic by design: it needs only a `propose_fn`
that maps input state (a dict) to a proposed action (a dict). This page
shows the common integration shapes.

## The one rule that matters

**Execute `decision.action`, never the raw proposal.** All enforcement
happens between the proposal and the decision; if any code path executes
tool calls or API requests directly, the gate is decorative. Structure your
code so the executor only ever receives governed actions:

```python
decision = gate.decide(state, propose_fn=agent_policy)
if decision.allowed:
    executor.run(decision.action)
else:
    escalation_queue.put(decision)
```

## Gate for an LLM tool-calling agent

Represent each tool call as a flat action dict and constrain the fields you
care about:

```python
from safeagentl import Constraint, ConstraintEngine, DecisionLogger, SafeAgent

gate = SafeAgent(
    agent_id="support-agent",
    constraint_engine=ConstraintEngine([
        Constraint(field="tool", op="in", bound=["lookup_order", "send_email", "issue_refund"],
                   reason="tool allowlist"),
        Constraint(field="refund_amount", op="lte", bound=100.0,
                   reason="autonomous refund cap"),
    ]),
    logger=DecisionLogger(sink_path="audit.jsonl"),
)

def propose_fn(state: dict) -> dict:
    call = llm_agent.next_tool_call(state)        # your existing agent
    return {"tool": call.name, **call.arguments}  # flatten to a dict

decision = gate.decide(conversation_state, propose_fn=propose_fn)
```

Denied decisions carry the machine-readable `reason` and a human-readable
`trace.reasoning`, which is exactly what you want to show a reviewer in an
escalation UI. See [`examples/tool_approval_gate.py`](../examples/tool_approval_gate.py)
for the runnable version.

## Workflow automation guardrail

For a step-based workflow engine, put one `SafeAgent` in front of each
consequential step type, sharing a logger so the audit trail is unified:

```python
audit = DecisionLogger(sink_path="workflow_audit.jsonl")
payment_gate = SafeAgent(agent_id="wf-payments", constraint_engine=payment_rules, logger=audit)
notify_gate  = SafeAgent(agent_id="wf-notify",   constraint_engine=notify_rules,  logger=audit)
```

## Adding fail-closed behavior

Wrap slow or network-dependent proposal paths with a timeout guard, and
keep policy enforcement alive through partitions with a cache:

```python
from safeagentl import PartitionTolerantCache, TimeoutToSafeDefault

policy_cache = PartitionTolerantCache(ttl_seconds=300)
policy_cache.sync(fetch_policy_from_control_plane)   # call periodically

with TimeoutToSafeDefault(timeout=0.5, safe_default={}) as guard:
    gate = SafeAgent(..., policy_cache=policy_cache, timeout_guard=guard)
    decision = gate.decide(state, propose_fn=slow_llm_call)
    # timeout -> decision.allowed == False, reason == "timeout_to_safe_default"
```

Caveat: a timed-out `propose_fn` keeps running in its worker thread — the
decision fails closed but the call is not killed. Keep side effects out of
`propose_fn`; side effects belong in the executor, behind the gate.

## Exporting the audit log

Two options:

1. **Streaming**: give `DecisionLogger` a `sink_path`; every trace is
   appended as one JSON line at log time. The sink is never truncated.
2. **Batch**: serialize on demand —

```python
import json

with open("export.jsonl", "w") as fh:
    for trace in logger.all_traces():
        fh.write(json.dumps(trace.to_dict(), default=str) + "\n")
```

Each record contains the decision id, timestamp, agent id, input state,
applied constraints, output, and reasoning chain — enough to reconstruct
the decision without access to the running system.

## Concurrency notes

The current implementation is designed for one `SafeAgent` per agent
worker. `ConstraintEngine.history` and `DecisionLogger`'s in-memory index
are plain Python structures without locking; if you share one instance
across threads, serialize access yourself, or give each worker its own
instances writing to per-worker sink files. Async-native support is on the
[roadmap](../ROADMAP.md).
