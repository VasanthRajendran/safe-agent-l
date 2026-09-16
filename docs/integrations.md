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

## Framework-agnostic wrapper patterns

The simplest integration is a thin adapter between your existing agent and the
safe gate. The adapter should expose a callable that returns a proposed action
mapping, while the executor should only ever receive `decision.action`.

### 1. Wrap any existing agent

```python
from safeagentl import Constraint, ConstraintEngine, SafeAgent

gate = SafeAgent(
    agent_id="support-agent",
    constraint_engine=ConstraintEngine([
        Constraint(field="tool", op="in", bound=["lookup_customer", "create_ticket"],
                   reason="tool allowlist"),
    ]),
)

def propose_fn(state: dict) -> dict:
    proposal = existing_agent.propose(state)  # your current planner or policy
    return {"tool": proposal["tool"], **proposal.get("args", {})}

decision = gate.decide(state, propose_fn=propose_fn)
if decision.allowed:
    execute_tool(decision.action)
else:
    escalate_to_human(decision)
```

The important part is that the executor receives `decision.action`, never the
original proposal object from the underlying agent.

### 2. Front a workflow step or queue consumer

```python
def handle_job(job: dict) -> None:
    decision = gate.decide(job, propose_fn=lambda state: current_policy.propose(state))
    if decision.allowed:
        run_step(decision.action)
    else:
        queue_dead_letter(job, decision.reason)
```

This pattern works for cron jobs, queue workers, event handlers, or
assistant-style request loops.

### 3. Add a safety boundary for a generic executor

```python
def run_request(request: dict) -> dict:
    decision = gate.decide(request, propose_fn=lambda state: planner.plan(state))
    if not decision.allowed:
        return {"status": "blocked", "reason": decision.reason}

    return {"status": "ok", "action": decision.action}
```

A generic executor can be anything: a database write, a webhook dispatch, a
tool invocation, or an internal automation step. As long as the executor uses
`decision.action` and never the raw proposal, the guardrail remains effective.

These examples do not require LangChain, OpenAI, LlamaIndex, or any other
framework-specific client. Any callable that returns a dict can be wrapped by
`SafeAgent`.

## LangChain tool-call middleware

Install the optional adapter on Python 3.10 or later:

```bash
pip install "safe-agent-l[langchain]"
```

`SafeAgentMiddleware` uses LangChain's tool-call middleware hook, so the real
tool handler is called only after the action passes the Safe Agent pipeline:

```python
from langchain.agents import create_agent
from langchain.tools import tool

from safeagentl import Constraint, ConstraintEngine, SafeAgent
from safeagentl.integrations.langchain import SafeAgentMiddleware

@tool
def issue_refund(amount: float) -> str:
    """Issue a customer refund."""
    return refund_service.issue(amount)

gate = SafeAgent(
    agent_id="refund-agent",
    constraint_engine=ConstraintEngine([
        Constraint(field="tool", op="eq", bound="issue_refund", required=True),
        Constraint(field="amount", op="lte", bound=100.0, required=True,
                   reason="autonomous refund cap"),
    ]),
)

agent = create_agent(
    model=chat_model,  # your configured LangChain chat model
    tools=[issue_refund],
    middleware=[SafeAgentMiddleware(gate)],
)
```

The adapter maps a call to `{"tool": tool_name, **tool_arguments}`. A rejected
call becomes an error `ToolMessage` containing the auditable decision ID, and
the underlying tool is not invoked. If a constraint uses `CLIP`, only the
governed argument values reach the tool. Both synchronous and asynchronous
LangChain execution are supported. Concurrent tool calls have their decision
checks serialized to protect the gate's in-memory audit history, while approved
tool handlers may still run concurrently. The `tool` key is reserved by
default; use `tool_name_field` when a tool schema already has an argument with
that name.

This middleware governs client-side tools executed through LangChain's tool
node. Provider-hosted/server-side tools execute outside that boundary and
cannot be intercepted by this adapter.

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
