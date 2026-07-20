# Concepts

safe-agent-l implements four independent controls, derived from the
SAFE-AGENT-L governance framework. Each is useful on its own; `SafeAgent`
composes them into one decision pipeline.

## The decision pipeline

For each action, `SafeAgent.decide(input_state, propose_fn)` runs:

1. **Propose** — your `propose_fn` (the actual agent: LLM, RL policy,
   planner) maps input state to a proposed action dictionary. If a
   `TimeoutToSafeDefault` guard is configured and the proposal exceeds its
   budget, the decision is **denied** (`reason="timeout_to_safe_default"`)
   without executing anything.
2. **Constrain** — the `ConstraintEngine` checks every registered rule.
   A violated REJECT-mode constraint denies the action
   (`reason="constraint_violation"`); a violated CLIP-mode constraint
   coerces the value to the nearest permitted bound and continues.
3. **Safety-check** — every layer in the `SafetyStack` evaluates the
   (already-constrained) action independently. Any failing layer denies it
   (`reason="safety_control_triggered"`). Repeated failures trip the
   `CircuitBreaker`, after which all actions are denied until the breaker's
   reset window elapses.
4. **Trace** — regardless of outcome, a `DecisionTrace` is logged with the
   input state, applied constraints, output, and reasoning chain. Traces
   that don't meet the logger's completeness bar are rejected at log time.

The order is deliberate: constraints shape *what the agent may do*, safety
layers evaluate *whether this particular action looks safe*, and the trace
records *what actually happened* — including denials.

## Control 1: Constraint enforcement

A `Constraint` is one machine-readable rule on one field of the action:

```python
Constraint(field="price", op="gte", bound=19.99, reason="MAP floor")
Constraint(field="tool",  op="in",  bound=["search", "email"], reason="tool allowlist")
```

Operators: `gte`, `lte`, `gt`, `lt`, `eq`, `in`, `not_in`. Enforcement
modes: `REJECT` (deny the action) and `CLIP` (coerce to the bound; only
valid for ordering operators). `ConstraintEngine.verify_configuration()`
catches contradictory bounds (e.g. min > max) before deployment.

The point is architectural: the rule is enforced at the boundary the
agent's output must cross, not suggested in a prompt.

## Control 2: Auditable decision traces

`DecisionTrace` captures enough to reconstruct a decision after the fact:
who (agent id), when, on what input, under which constraints, with what
output and reasoning. `DecisionLogger` enforces a completeness bar at log
time (default: 100% of required fields present), optionally evicts expired
traces from its in-memory index, and can append every trace to a JSONL
sink file that is never truncated.

Design choice: **incomplete audit records fail loudly at write time.** An
audit trail you discover is full of holes during an incident is worse than
an exception during development.

## Control 3: Defense-in-depth safety

`SafetyStack` runs independent layers — plain callables from action dict to
bool — and denies the action if *any* layer fails. A layer that raises is
counted as a failure, not skipped (fail-closed). The included
`AnomalyDetector` is a rolling z-score baseline usable as one layer via
`detector.as_layer("price")`.

Layers are deliberately independent of the constraint engine and of each
other, so a single defect (a bad constraint config, a blind spot in one
detector) cannot alone let an unsafe action through. The shared
`CircuitBreaker` is the last line: repeated failures halt the agent
entirely.

## Control 4: Fail-closed resilience

The first three controls assume policies, checks, and logs are reachable.
Networks fail, so:

- `TimeoutToSafeDefault` — a safety-relevant call that doesn't complete in
  time returns a configured safe default (deny) instead of proceeding
  unverified.
- `PartitionTolerantCache` — keeps the last-known-good policy available
  locally; reads keep working (flagged stale) during a partition, and a
  failed `sync()` never clobbers the cached value.
- `PriorityRouter` — safety-critical control signals (constraint updates,
  recall orders, breaker triggers) dispatch before routine traffic.

## Conformance self-assessment

`SafeAgent.assess_conformance()` reports which of three levels the current
configuration reaches — `minimum` (constraints + full-completeness
logging), `recommended` (+ ≥2 independent safety layers), `exemplary`
(+ timeout guard and policy cache). This is a development-time heuristic
for your own configuration, not a certification of any kind.
