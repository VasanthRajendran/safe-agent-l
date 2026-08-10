---
name: safe-agent-l
description: Put runtime guardrails in front of an autonomous agent with the safe-agent-l Python library - constraint enforcement, audit traces, defense-in-depth safety layers, and fail-closed timeouts. Use when wrapping an LLM, tool-calling agent, policy, or workflow step so it cannot take an impermissible action - price floors, refund caps, tool allowlists, quantity ceilings, spend limits, approval gates - or when asked for an auditable trail of agent decisions. Domain vocabulary is customizable; see "Adapting the skill to your domain".
---

# safe-agent-l guardrails

Move an agent's rules out of the prompt and into an enforcement layer its
output must pass through. A prompt instruction ("never price below $19.99")
is a suggestion the model can ignore, and you cannot prove to an auditor
that it didn't. A constraint is a control.

The library is pure Python, zero runtime dependencies, Python 3.9+. It is
not an LLM agent and calls no model API — it wraps whatever agent you
already have.

## When this applies

Use this skill when the task involves an agent, policy, planner, or
workflow step that takes a consequential action and needs limits,
approval, or an audit trail. It does not apply to read-only assistants or
to code that never acts on the model's output.

## Install

```bash
pip install git+https://github.com/VasanthRajendran/safe-agent-l.git
```

Not yet on PyPI. If the environment has no network access, say so rather
than substituting a different library.

## The workflow

### 1. Name the action as a flat dict

Everything downstream constrains keys of one dict. Flatten the agent's
output into it — a tool call becomes `{"tool": name, **arguments}`.

```python
def propose_fn(state: dict) -> dict:
    call = my_agent.next_tool_call(state)   # LLM, RL policy, rules engine
    return {"tool": call.name, **call.arguments}
```

Keep side effects out of `propose_fn`. It proposes; it does not act.

### 2. Write the constraints

One `Constraint` per rule, on one field. `reason` is free text that lands
in the audit trace — write it for the person reading the incident review.

```python
from safeagentl import Constraint, ConstraintEngine, EnforcementMode

constraints = ConstraintEngine([
    Constraint(field="tool", op="in", bound=["lookup_order", "issue_refund"],
               reason="tool allowlist", required=True),
    Constraint(field="refund_amount", op="lte", bound=100.0,
               reason="autonomous refund cap", mode=EnforcementMode.CLIP),
])
```

| `op` | Meaning | Clippable |
|---|---|---|
| `gte` / `gt` | value at or above / above `bound` | yes |
| `lte` / `lt` | value at or below / below `bound` | yes |
| `eq` | value equals `bound` | no |
| `in` / `not_in` | value is / is not a member of `bound` | no |

`mode=REJECT` (default) denies the whole action. `mode=CLIP` coerces the
value to the bound and lets it through — only valid on the four ordering
operators. Clip when a too-large number should become the maximum; reject
when the attempt itself is the problem.

### 3. Verify the config before deploying

```python
problems = constraints.verify_configuration()
assert not problems, problems     # contradictory bounds, conflicting eq rules
```

### 4. Add independent safety layers

Layers are `Callable[[dict], bool]`, independent of the constraints on
purpose: one bad constraint config should not be the only thing standing
between the agent and production. Any layer returning `False` — or
raising — denies the action.

```python
from safeagentl import AnomalyDetector, CircuitBreaker, SafetyStack

safety = SafetyStack(
    layers=[
        lambda action: action.get("refund_amount", 0) >= 0,
        AnomalyDetector(z_threshold=3.0).as_layer("refund_amount"),
    ],
    breaker=CircuitBreaker(failure_threshold=3, reset_timeout=30.0),
)
```

Three consecutive failed checks trip the breaker and everything is denied
until the cool-down elapses.

### 5. Wire the gate and execute `decision.action`

```python
from safeagentl import DecisionLogger, SafeAgent

gate = SafeAgent(
    agent_id="support-agent",
    constraint_engine=constraints,
    logger=DecisionLogger(sink_path="audit.jsonl"),
    safety_stack=safety,
)

decision = gate.decide(state, propose_fn=propose_fn)
if decision.allowed:
    execute(decision.action)          # governed action, never the raw proposal
else:
    escalate(decision)                # decision.reason + decision.trace.reasoning
```

`decision.reason` is machine-readable: `constraint_violation`,
`safety_control_triggered`, `timeout_to_safe_default`, or `""` when
allowed. `decision.trace.reasoning` is the human-readable chain.

### 6. Optional — fail closed under network trouble

```python
from safeagentl import PartitionTolerantCache, TimeoutToSafeDefault

with TimeoutToSafeDefault(timeout=0.5) as guard:
    gate = SafeAgent(..., timeout_guard=guard,
                     policy_cache=PartitionTolerantCache(ttl_seconds=300))
```

A proposal that blows the timeout budget is denied rather than executed
unverified.

## Getting it right

These are the ways a guardrail ends up decorative. Check each one.

- **Execute `decision.action`, never the proposal.** Any code path that
  calls the tool directly bypasses every control here. Enforcement is
  in-process; place the gate where the agent cannot route around it.
- **Set `required=True` on constraints that must always apply.** A missing
  field is *ignored* by default — a `tool` allowlist silently passes an
  action with no `tool` key unless the constraint is marked required. This
  is the single most common way an allowlist turns out to be a no-op.
- **A stale `policy_cache` does not deny.** It only adds a line to the
  trace. If stale policy should block, add a safety layer that checks
  `policy_cache.get()[1]`.
- **A timed-out `propose_fn` keeps running** in its worker thread. The
  decision fails closed; the call is not killed. Another reason side
  effects belong behind the gate.
- **CLIP-mode violations still count as violations** in the trace and
  still trip nothing — the action is allowed with the coerced value. If
  the attempt itself should be visible as a denial, use REJECT.
- **`DecisionLogger` rejects incomplete traces at log time** with
  `TraceIncompleteError`. That is the point: gaps surface before the
  audit, not during it. Do not lower `min_completeness` to silence it.
- **One `SafeAgent` per worker.** The history and trace index are plain
  Python structures with no locking.

## Adapting the skill to your domain

Two things are customizable, and both matter for making this skill fire on
your team's vocabulary instead of the generic examples.

**1. Trigger keywords.** The `description` in the frontmatter above is what
decides whether this skill loads. Add your domain's actual words to it —
the terms your engineers type, not the abstract ones. A claims team should
add "claim adjudication, payout, denial code"; a lending team "credit
line, APR, adverse action". Keep the existing sentence structure and
append; the description is matched as a whole.

**2. Field vocabulary and starter constraints.** `references/domain-packs.md`
carries ready-made packs — pricing, refunds and support, lending, clinical,
infrastructure automation, data access — each with the action-dict field
names, the constraints worth starting from, and the safety layers that
domain usually needs. Copy the closest pack, rename the fields to match
your action dict, and adjust the bounds. If none fits, write a new pack in
the same shape and keep it in this file so the next person inherits it.

Changing the bounds in a pack is expected. Deleting a constraint because
it is inconvenient is a policy decision — surface it to the user rather
than quietly dropping it.

## What this does not do

Be straight with the user about the limits. It enforces the constraints
*you configure* and produces evidence they were applied; it does not
guarantee legal or regulatory compliance, does not certify against any
standard, and is one enforcement layer rather than a complete safety
system. The anomaly detector is a statistical baseline, not a
domain-specific safety check.

## Reference

- `references/api.md` — full API surface: every class, signature, default,
  and return shape. Read before using a class not shown above.
- `references/domain-packs.md` — per-domain field vocabularies and starter
  constraint sets.
- `references/patterns.md` — integration shapes: tool-calling gates,
  workflow steps, queue consumers, audit-log export, testing a guardrail.
- `assets/guardrail_template.py` — runnable skeleton to copy and fill in.
