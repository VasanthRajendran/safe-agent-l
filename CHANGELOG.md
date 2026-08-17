# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with the pre-1.0 caveat that minor versions may contain breaking changes,
which will always be listed here).

## [Unreleased]

## [0.2.0] - 2026-08-17

First release published to PyPI: `pip install safe-agent-l`.

### Added

- `Constraint.required`: a constraint marked `required=True` now rejects an
  action whose field is absent, instead of letting the missing field pass
  through unchecked. Constraints remain optional-by-default, so existing
  configurations are unaffected.
- `docs/integrations.md`: framework-agnostic integration patterns for
  tool-calling gates, workflow guardrails, and audit-log export.
- `examples/generic_agent_guard.py`: a runnable tool-calling example showing
  both allowed and denied operations.
- Automated PyPI publishing on GitHub release via Trusted Publishing
  (`.github/workflows/publish.yml`); release checklist updated accordingly.

## [0.1.0] - 2026-07-19

### Added

- `safeagentl.constraints`: `Constraint` and `ConstraintEngine` — machine-readable
  policy rules with REJECT and CLIP enforcement modes, pre-deployment
  configuration verification (contradictory-bound detection), and an
  auditable enforcement history.
- `safeagentl.explainability`: `DecisionTrace` and `DecisionLogger` —
  reconstructable decision records with a log-time completeness bar,
  optional retention window, and append-only JSONL sink.
- `safeagentl.safety`: `SafetyStack`, `CircuitBreaker`, and `AnomalyDetector` —
  independent safety layers evaluated per action; layer exceptions count as
  failures (fail-closed); repeated failures trip the breaker.
- `safeagentl.network`: `PriorityRouter` (safety-critical signals dispatch
  first), `TimeoutToSafeDefault` (checks that exceed their budget default to
  deny), and `PartitionTolerantCache` (last-known-good policy survives
  partitions and resyncs on recovery).
- `safeagentl.agent`: `SafeAgent` orchestrator composing all four controls
  around any `propose_fn`, with `assess_conformance()` self-assessment.
- Test suite (48 tests), end-to-end pricing example, MIT license, CI.

[Unreleased]: https://github.com/VasanthRajendran/safe-agent-l/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/VasanthRajendran/safe-agent-l/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/VasanthRajendran/safe-agent-l/releases/tag/v0.1.0
