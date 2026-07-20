# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with the pre-1.0 caveat that minor versions may contain breaking changes,
which will always be listed here).

## [Unreleased]

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

[Unreleased]: https://github.com/VasanthRajendran/safe-agent-l/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/VasanthRajendran/safe-agent-l/releases/tag/v0.1.0
