# Roadmap

This roadmap reflects current maintainer intent. It is not a commitment;
items move based on user feedback and contributor interest. Open an issue if
something here matters to you — that is the main input for prioritization.

## Near term (0.2.x)

- **Publish to PyPI** (after a TestPyPI dry run — see RELEASING.md).
- **Declarative policy loading**: define `ConstraintEngine` configurations
  in YAML/JSON so policies can be reviewed and versioned outside code.
- **More constraint operators**: regex match, length bounds, nested-field
  paths (`payment.amount`), cross-field rules.
- **Async support**: `async def decide()` and an async-friendly
  `TimeoutToSafeDefault` for asyncio-based agent stacks.
- **Structured audit export**: first-class export of decision traces to
  JSONL/CSV with filtering, beyond the current append-only sink.

## Medium term

- **Integration adapters**: thin, optional wrappers for common agent
  frameworks and tool-calling protocols (kept out of the core so the base
  library stays dependency-free).
- **OpenTelemetry trace emission** for decision traces, so audit events land
  in existing observability pipelines.
- **Policy versioning**: record which policy version governed each decision
  in its trace.

## Longer term / exploratory

- **Conformance assessment tooling** aligned with the SAFE-AGENT-L
  standardization effort (IEEE PAR in review), if and when the Recommended
  Practice is published. No conformance claims will be made before then.
- **Multi-agent coordination controls**: message-ordering and priority
  guarantees across cooperating governed agents.

## Non-goals

- Becoming an LLM agent framework. This library governs actions; it does not
  plan them.
- Bundling model/provider SDKs as runtime dependencies.
- Shipping domain policy content (e.g. a specific industry's rules) in the
  core library.
