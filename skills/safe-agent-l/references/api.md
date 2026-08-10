# API reference

Everything importable from the top-level `safeagentl` package. Anything
reached through a submodule with a leading underscore is internal and may
change without notice.

```python
from safeagentl import (
    SafeAgent, Decision, ConformanceLevel,
    Constraint, ConstraintEngine, EnforcementMode, EnforcementResult, InvalidConstraintError,
    DecisionLogger, DecisionTrace, TraceIncompleteError,
    AnomalyDetector, CircuitBreaker, CircuitState, SafetyStack, SafetyCheckResult,
    PriorityRouter, Priority, TimeoutToSafeDefault, PartitionTolerantCache,
)
```

Pre-1.0: minor versions may break the API. Check `CHANGELOG.md` on upgrade.

---

## Constraint enforcement — `safeagentl.constraints`

### `Constraint(field, op, bound, mode=REJECT, reason="", required=False)`

Frozen dataclass. One rule over one field of the action dict.

| Arg | Type | Notes |
|---|---|---|
| `field` | `str` | key in the action dict |
| `op` | `str` | `gte`, `lte`, `gt`, `lt`, `eq`, `in`, `not_in` |
| `bound` | `Any` | comparison value; a container for `in` / `not_in` |
| `mode` | `EnforcementMode` | `REJECT` (default) or `CLIP` |
| `reason` | `str` | free text, appears in violation messages and traces |
| `required` | `bool` | if `True`, a missing field is a violation |

Raises `InvalidConstraintError` at construction for an unknown operator,
or for `CLIP` combined with a non-ordering operator (`eq`, `in`,
`not_in`) — those have no well-defined nearest bound.

Methods: `is_satisfied(value) -> bool`, `clip(value) -> Any`,
`describe() -> str`, `describe_missing() -> str`.

### `EnforcementMode`

`REJECT = "reject"` — deny the action outright.
`CLIP = "clip"` — coerce the value to the bound and continue.

### `ConstraintEngine(constraints=None)`

- `add_constraint(constraint)` — constraints are additive; several on one
  field all apply.
- `constraints_for(field_name) -> List[Constraint]`
- `len(engine)` — number of *distinct constrained fields*, not the number
  of constraints.
- `verify_configuration() -> List[str]` — pre-deployment check. Reports
  contradictory bounds on a field (min above max) and conflicting `eq`
  values. Empty list means no field's action space is provably empty. It
  does not prove the config is correct, only that it is not self-defeating.
- `enforce(action) -> EnforcementResult` — applies every constraint.
- `history: List[EnforcementResult]` — every call, retained in order.

Semantics of `enforce`:

- Fields with no constraints pass through untouched.
- A field absent from the action is skipped, **unless** a constraint on it
  has `required=True`, which is a violation and denies the action.
- Constraints on a field are evaluated in registration order; a `CLIP`
  updates the value in place, so a later constraint sees the clipped value.
- Any violated `REJECT` constraint sets `allowed=False`. Evaluation does
  not stop at the first violation — all violations are collected.

### `EnforcementResult`

| Attr | Type | Meaning |
|---|---|---|
| `action` | `dict` | the enforced action (clipped values applied) |
| `original_action` | `dict` | the proposal as received |
| `applied_constraints` | `List[str]` | human-readable log of clips and rejections |
| `violations` | `List[str]` | every violated constraint, including clipped ones |
| `allowed` | `bool` | `False` if any REJECT constraint was violated |

A CLIP violation appears in `violations` while `allowed` stays `True`.

---

## Audit traces — `safeagentl.explainability`

### `DecisionTrace(agent_id, input_state, applied_constraints, output, reasoning=[], decision_id=uuid4, timestamp=time.time)`

- `completeness_score() -> float` — fraction of the six required fields
  (`decision_id`, `timestamp`, `agent_id`, `input_state`,
  `applied_constraints`, `output`) that are populated. An empty dict or
  list counts as present — no constraints applied, or no output on a
  denial, are legitimate values. Only `None` or an empty identifier string
  counts as missing.
- `to_dict() -> dict`

### `DecisionLogger(retention_seconds=None, min_completeness=1.0, sink_path=None)`

- `log(trace) -> DecisionTrace` — raises `TraceIncompleteError` if the
  trace scores below `min_completeness`. Rejecting at log time is the
  point: gaps surface before an audit rather than during one.
- `reconstruct(decision_id) -> DecisionTrace` — raises `KeyError` if the
  id is unknown or was evicted.
- `all_traces() -> List[DecisionTrace]`
- `len(logger)` — traces currently in the in-memory index.

`sink_path` appends one JSON line per trace at log time and is never
truncated. `retention_seconds` evicts old traces from the in-memory index
only — the sink file keeps everything. If you need durable audit, set a
sink; the in-memory index is not storage.

---

## Safety layers — `safeagentl.safety`

`SafetyLayer = Callable[[Dict[str, Any]], bool]`

### `CircuitBreaker(failure_threshold=3, reset_timeout=30.0)`

Trips after `failure_threshold` *consecutive* failures; a success resets
the counter. `state` is `CLOSED` / `OPEN` / `HALF_OPEN` — reading `state`
transitions `OPEN` to `HALF_OPEN` once `reset_timeout` has elapsed.
`allow() -> bool` is `False` only while `OPEN`. Raises `ValueError` for a
threshold below 1.

### `AnomalyDetector(window_size=20, z_threshold=3.0, min_samples=5)`

Rolling z-score over a `deque`. `is_anomalous(value) -> bool` returns
`False` until `min_samples` observations have accumulated, then compares
against the window mean and population stdev. Every value is folded into
the window afterward, including anomalous ones, so the baseline adapts —
a slow drift will eventually be treated as normal. Pair it with a hard
constraint for anything that has an absolute limit.

`as_layer(field_name) -> SafetyLayer` adapts it into a layer over
`action[field_name]`; an action missing that field passes. Raises
`ValueError` for `min_samples < 2`.

### `SafetyStack(layers=None, breaker=None)`

- `add_layer(layer)`
- `check(action) -> SafetyCheckResult`

The breaker is consulted first — if open, the result is
`failed_layers=["circuit_breaker_open"]` and no layer runs. Otherwise
every layer runs (evaluation is not short-circuited). A layer that raises
is recorded as failed, never silently passed. Any failure records a
breaker failure; a clean pass records a success.

### `SafetyCheckResult`

`safe: bool`, `failed_layers: List[str]` (formatted
`layer_{index}:{name}`, with `:error={exc}` appended when the layer
raised), `breaker_state: CircuitState`.

Give layers real names — `def refund_nonnegative(action): ...` rather than
a lambda — so `failed_layers` is readable in an incident review.

---

## Network resilience — `safeagentl.network`

### `Priority` / `PriorityRouter`

`Priority.CRITICAL = 0`, `HIGH = 1`, `ROUTINE = 2`; lower dispatches
first. `submit(message, priority=ROUTINE)`, `dispatch_next() -> Optional`,
`drain()` (generator), `len(router)`. Ties break by submission order.
Use it so constraint updates, recall orders, and breaker triggers outrank
routine agent traffic.

### `TimeoutToSafeDefault(timeout, safe_default=False, max_workers=4)`

`run(fn, *args, **kwargs) -> Tuple[Any, bool]` returning
`(result, timed_out)`. On timeout returns `(safe_default, True)`.
Context manager; `shutdown()` releases the thread pool. Raises
`ValueError` for a non-positive timeout.

The timed-out call **keeps running** in its worker thread — the decision
fails closed but the work is not cancelled. Keep side effects out of
anything you wrap.

### `PartitionTolerantCache(ttl_seconds=300.0)`

`get() -> Tuple[Optional[Any], bool]` returning `(value, is_stale)`. It
deliberately returns a stale value rather than raising, because the read
path must keep working during a partition; callers inspect the flag.
`sync(fetch_fn) -> bool` refreshes from the source of truth and returns
`False` on failure, leaving the cached value intact. `is_stale` is `True`
before the first successful sync.

---

## Orchestration — `safeagentl.agent`

### `SafeAgent(agent_id, constraint_engine=None, logger=None, safety_stack=None, policy_cache=None, timeout_guard=None)`

Omitted components default to empty instances — an empty
`ConstraintEngine` enforces nothing, which is a valid but ungoverned
configuration.

### `decide(input_state, propose_fn) -> Decision`

Pipeline, in order:

1. If `policy_cache` is set and stale, append a line to the reasoning
   chain. **This does not deny** — it is a note in the trace.
2. If `timeout_guard` is set, run `propose_fn` under it. On timeout: log
   and return `allowed=False`, `action={}`, `reason="timeout_to_safe_default"`.
   Without a guard, `propose_fn` is called directly.
3. `constraint_engine.enforce(...)`. On denial: `reason="constraint_violation"`,
   with `action` set to the partially-enforced action.
4. `safety_stack.check(...)`. On denial: `reason="safety_control_triggered"`.
5. Log the trace and return `allowed=True`, `reason=""`.

Every outcome is logged, allowed or denied. The final reasoning entry is
always `allowed={bool}`.

### `Decision`

`allowed: bool`, `action: dict`, `trace: Optional[DecisionTrace]`,
`reason: str`.

`action` on a denial is the enforced action, not the raw proposal — it is
for the escalation UI, not for execution.

### `assess_conformance() -> ConformanceLevel`

Development-time heuristic, not third-party assessment:

| Level | Requires |
|---|---|
| `NONE` | fewer than 1 constrained field, or `min_completeness < 1.0` |
| `MINIMUM` | the above satisfied, under 2 safety layers |
| `RECOMMENDED` | 2+ safety layers, missing a policy cache or timeout guard |
| `EXEMPLARY` | all of the above, both network components configured |
