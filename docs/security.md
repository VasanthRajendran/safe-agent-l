# Security model

This page describes what safe-agent-l defends against, what it assumes,
and where its boundaries are. For reporting vulnerabilities, see
[SECURITY.md](../SECURITY.md).

## Threat model

safe-agent-l is built to contain a **misbehaving or manipulated agent
policy**: an LLM that ignores its prompt, a compromised planner, a policy
that was prompt-injected into proposing harmful actions. Against that
adversary it provides:

- **Action-space enforcement** — the proposal is checked against
  configured constraints after the agent produces it; the agent cannot
  talk its way past a REJECT-mode rule.
- **Independent layers** — a proposal must survive the constraint engine
  *and* every safety layer; compromising the prompt does not compromise
  the gate.
- **Fail-closed defaults** — timeouts deny; safety-layer exceptions count
  as failures; an open circuit breaker denies everything.
- **Tamper-evident recording** — every outcome is traced at a mandatory
  completeness level, to an append-only sink if configured.

## Trust assumptions

The library trusts:

- **The process it runs in.** Enforcement is in-process Python. An
  attacker with arbitrary code execution in the same process can call
  tools directly, monkey-patch the engine, or edit the in-memory log. If
  your threat model includes a compromised process, put the gate in a
  separate service the agent reaches over an API, so the enforcement
  boundary is a process boundary.
- **The policy author.** Constraints are organization-defined. The engine
  faithfully enforces what you configure — including mistakes.
  `verify_configuration()` catches contradictions, not wrong policy.
- **The executor discipline.** Only `decision.action` may be executed.
  Any code path that executes raw proposals bypasses everything (see
  [integrations.md](integrations.md)).

## Known boundaries

- **Audit sink integrity**: the JSONL sink is append-only from the
  library's side, but it is a local file; production deployments should
  ship it to write-once storage (object lock, log pipeline) if
  tamper-resistance matters.
- **Timed-out calls are not killed**: `TimeoutToSafeDefault` fails the
  *decision* closed, but the orphaned callable finishes in its worker
  thread. Keep side effects out of `propose_fn`.
- **The anomaly detector is statistical**: a patient adversary can shift
  its baseline gradually. Treat it as one layer among several, never the
  only one.
- **No cryptographic guarantees**: traces are not signed or hash-chained
  today (see [ROADMAP.md](../ROADMAP.md) for audit-export plans).

## Deployment recommendations

1. Run the gate as close to the execution boundary as possible — ideally
   the only code path that can reach your tools/APIs.
2. Give the agent process least privilege: if the process cannot reach an
   endpoint, neither can a bypassed gate.
3. Ship audit sinks off-host promptly.
4. Alert on `circuit_breaker_open` and on denial-rate spikes — they are
   your earliest signal that an agent is misbehaving.
5. Review constraint configurations like code: version them, review
   changes, and test them (`verify_configuration()` in CI is cheap).
