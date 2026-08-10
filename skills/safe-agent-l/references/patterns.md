# Integration patterns

The library needs one thing from you: a `propose_fn` mapping input state
(a dict) to a proposed action (a dict). Everything below is a variation on
where you put the gate.

## The rule that makes or breaks all of them

**Execute `decision.action`, never the raw proposal.** All enforcement
happens between the proposal and the decision. If any code path reaches
the executor directly, the gate is decoration. Structure the code so the
executor cannot be called with anything else:

```python
decision = gate.decide(state, propose_fn=agent_policy)
if decision.allowed:
    executor.run(decision.action)
else:
    escalation_queue.put(decision)
```

A useful shape for enforcing this structurally — the executor is private,
and the only public entry point goes through the gate:

```python
class GovernedExecutor:
    def __init__(self, gate, executor):
        self._gate, self._executor = gate, executor

    def handle(self, state, propose_fn):
        decision = self._gate.decide(state, propose_fn=propose_fn)
        if not decision.allowed:
            return {"status": "blocked", "reason": decision.reason,
                    "decision_id": decision.trace.decision_id}
        return {"status": "ok", "result": self._executor.run(decision.action)}
```

---

## 1. Wrap an existing agent

```python
from safeagentl import Constraint, ConstraintEngine, SafeAgent

gate = SafeAgent(
    agent_id="support-agent",
    constraint_engine=ConstraintEngine([
        Constraint(field="tool", op="in",
                   bound=["lookup_customer", "create_ticket"],
                   reason="tool allowlist", required=True),
    ]),
)

def propose_fn(state: dict) -> dict:
    proposal = existing_agent.propose(state)
    return {"tool": proposal["tool"], **proposal.get("args", {})}

decision = gate.decide(state, propose_fn=propose_fn)
```

Framework-agnostic — no LangChain, OpenAI, or LlamaIndex client required.
Any callable returning a dict works.

## 2. LLM tool-calling gate

Flatten each tool call into one action dict and constrain the fields you
care about:

```python
def propose_fn(state: dict) -> dict:
    call = llm_agent.next_tool_call(state)
    return {"tool": call.name, **call.arguments}
```

Denied decisions carry a machine-readable `reason` and a human-readable
`trace.reasoning` — exactly what an escalation UI should show a reviewer.
See `examples/tool_approval_gate.py` in the repository for the runnable
version.

## 3. Workflow step or queue consumer

```python
def handle_job(job: dict) -> None:
    decision = gate.decide(job, propose_fn=lambda s: current_policy.propose(s))
    if decision.allowed:
        run_step(decision.action)
    else:
        queue_dead_letter(job, decision.reason)
```

Works for cron jobs, queue workers, event handlers, and request loops.

## 4. One gate per consequential step type

Separate constraint engines, one shared logger, so the audit trail stays
unified across the workflow:

```python
audit = DecisionLogger(sink_path="workflow_audit.jsonl")
payment_gate = SafeAgent(agent_id="wf-payments", constraint_engine=payment_rules, logger=audit)
notify_gate  = SafeAgent(agent_id="wf-notify",   constraint_engine=notify_rules,  logger=audit)
```

`agent_id` is what distinguishes them in the log — make it meaningful.

## 5. Fail-closed under network trouble

```python
from safeagentl import PartitionTolerantCache, TimeoutToSafeDefault

policy_cache = PartitionTolerantCache(ttl_seconds=300)
policy_cache.sync(fetch_policy_from_control_plane)   # call periodically

with TimeoutToSafeDefault(timeout=0.5, safe_default={}) as guard:
    gate = SafeAgent(..., policy_cache=policy_cache, timeout_guard=guard)
    decision = gate.decide(state, propose_fn=slow_llm_call)
    # timeout -> allowed=False, reason == "timeout_to_safe_default"
```

Two things to know. The timed-out `propose_fn` keeps running in its worker
thread — the decision fails closed but the call is not killed, so keep
side effects out of it. And a stale cache only annotates the trace; if
stale policy should block, add a safety layer:

```python
def policy_is_fresh(action, cache=policy_cache):
    _, stale = cache.get()
    return not stale

safety.add_layer(policy_is_fresh)
```

## 6. Exporting the audit log

Streaming — one JSON line appended per trace at log time, never truncated:

```python
logger = DecisionLogger(sink_path="audit.jsonl")
```

Batch — serialize on demand:

```python
import json
with open("export.jsonl", "w") as fh:
    for trace in logger.all_traces():
        fh.write(json.dumps(trace.to_dict(), default=str) + "\n")
```

Each record carries decision id, timestamp, agent id, input state, applied
constraints, output, and the reasoning chain — enough to reconstruct the
decision without access to the running system. `retention_seconds` evicts
from the in-memory index only; the sink file keeps everything.

---

## Testing a guardrail

A guardrail nobody tested is a guardrail nobody has. Three tests per rule:

```python
def test_below_floor_is_denied():
    d = gate.decide({}, propose_fn=lambda s: {"price": 9.99, "currency": "USD"})
    assert not d.allowed
    assert d.reason == "constraint_violation"

def test_at_floor_is_allowed():
    d = gate.decide({}, propose_fn=lambda s: {"price": 19.99, "currency": "USD"})
    assert d.allowed

def test_missing_field_is_denied():        # the one people forget
    d = gate.decide({}, propose_fn=lambda s: {"currency": "USD"})
    assert not d.allowed                   # requires required=True on the constraint
```

The third test is the one that catches a constraint that silently does
nothing. Write it for every rule that must always apply.

Also assert on the trace, not just the boolean — an audit trail that is
never read is never known to be broken:

```python
def test_denial_is_explained():
    d = gate.decide({}, propose_fn=lambda s: {"price": 9.99})
    assert "MAP floor" in " ".join(d.trace.reasoning)
```

## Concurrency

One `SafeAgent` per agent worker. `ConstraintEngine.history` and
`DecisionLogger`'s in-memory index are plain Python structures without
locking. Sharing an instance across threads means serializing access
yourself, or giving each worker its own instances writing to per-worker
sink files.
