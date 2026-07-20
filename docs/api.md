# API reference

The public API is the set of names exported from the top-level `safeagentl`
package. Everything below is importable as `from safeagentl import …`.
Docstrings in the source are the authoritative reference; this page is the
map.

## `safeagentl.agent`

### `SafeAgent(agent_id, constraint_engine=None, logger=None, safety_stack=None, policy_cache=None, timeout_guard=None)`

Composes the four controls around one decision.

- `decide(input_state: dict, propose_fn: Callable[[dict], dict]) -> Decision`
  — run the full pipeline for one action. `propose_fn` is your agent.
- `assess_conformance() -> ConformanceLevel` — development-time
  self-assessment of the current configuration (`none` / `minimum` /
  `recommended` / `exemplary`).

### `Decision`

| Field | Type | Meaning |
|---|---|---|
| `allowed` | `bool` | whether the governed action may execute |
| `action` | `dict` | the governed action (post-clipping); execute this, never the raw proposal |
| `trace` | `DecisionTrace` | the audit record for this decision |
| `reason` | `str` | `""`, `"constraint_violation"`, `"safety_control_triggered"`, or `"timeout_to_safe_default"` |

## `safeagentl.constraints`

### `Constraint(field, op, bound, mode=EnforcementMode.REJECT, reason="")`

One machine-readable rule on one action field. Operators: `gte`, `lte`,
`gt`, `lt`, `eq`, `in`, `not_in`. `EnforcementMode.CLIP` is only valid for
the four ordering operators; anything else raises
`InvalidConstraintError` at construction.

### `ConstraintEngine(constraints=None)`

- `add_constraint(constraint)` — register another rule.
- `enforce(action: dict) -> EnforcementResult` — apply every registered
  rule; unregistered fields pass through untouched.
- `verify_configuration() -> list[str]` — pre-deployment check for
  contradictory bounds; empty list means no problems found.
- `history: list[EnforcementResult]` — every enforcement call, for audit.

### `EnforcementResult`

`action` (post-enforcement), `original_action`, `applied_constraints`,
`violations`, `allowed`.

## `safeagentl.explainability`

### `DecisionTrace(agent_id, input_state, applied_constraints, output, reasoning=[], …)`

One reconstructable decision record. `decision_id` and `timestamp` are
auto-generated. `completeness_score() -> float` reports the fraction of
required fields present; `to_dict()` serializes for export.

### `DecisionLogger(retention_seconds=None, min_completeness=1.0, sink_path=None)`

- `log(trace) -> DecisionTrace` — raises `TraceIncompleteError` if the
  trace is below the completeness bar; otherwise stores it, appends to the
  JSONL sink if configured, and evicts expired traces.
- `reconstruct(decision_id) -> DecisionTrace` — retrieve one trace;
  `KeyError` if unknown.
- `all_traces() -> list[DecisionTrace]`, `len(logger)`.

The `sink_path` file is append-only and never truncated by retention
eviction (eviction only affects the in-memory index).

## `safeagentl.safety`

### `SafetyStack(layers=None, breaker=None)`

- A layer is any `Callable[[dict], bool]`; `True` means safe.
- `check(action) -> SafetyCheckResult` — evaluates every layer; any
  `False` or raised exception is a failure (fail-closed). Failures feed the
  breaker; an open breaker denies everything with
  `failed_layers=["circuit_breaker_open"]`.
- `add_layer(layer)`.

### `CircuitBreaker(failure_threshold=3, reset_timeout=30.0)`

`record_failure()` / `record_success()` / `allow()`; `state` is
`CLOSED`, `OPEN`, or `HALF_OPEN` (reset window elapsed, next success
re-closes).

### `AnomalyDetector(window_size=20, z_threshold=3.0, min_samples=5)`

Rolling z-score baseline. `is_anomalous(value) -> bool`;
`as_layer(field_name)` adapts it into a safety layer that ignores actions
without that field.

## `safeagentl.network`

### `TimeoutToSafeDefault(timeout, safe_default=False, max_workers=4)`

`run(fn, *args, **kwargs) -> (result, timed_out)` — executes `fn` in a
worker thread; on timeout returns `safe_default` with `timed_out=True`.
Usable as a context manager; call `shutdown()` when done.

Note: the timed-out callable is not forcibly killed (Python threads cannot
be); the *decision* fails closed while the orphaned call finishes in the
background. Don't give `propose_fn` irreversible side effects.

### `PartitionTolerantCache(ttl_seconds=300.0)`

`sync(fetch_fn) -> bool` refreshes from the source of truth; on exception
returns `False` and leaves the cached value untouched. `get() -> (value,
is_stale)` always answers, even mid-partition. `is_stale` property.

### `PriorityRouter` / `Priority`

`submit(message, priority)` and `dispatch_next()` / `drain()`. Priorities:
`CRITICAL` > `HIGH` > `ROUTINE`; FIFO within a level.

## Exceptions

| Exception | Raised by | When |
|---|---|---|
| `InvalidConstraintError` | `Constraint` | malformed rule at construction |
| `TraceIncompleteError` | `DecisionLogger.log` | trace below the completeness bar |
| `ValueError` | `CircuitBreaker`, `AnomalyDetector`, `TimeoutToSafeDefault` | invalid configuration parameters |
