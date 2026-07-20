# Contributing to safe-agent-l

Thanks for your interest in improving safe-agent-l.

## Getting started

```bash
git clone https://github.com/VasanthRajendran/safe-agent-l.git
cd safe-agent-l
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Before opening a PR, make sure all three checks pass:

```bash
pytest --cov=safeagentl   # tests with coverage
ruff check .              # lint
mypy                      # type check
```

CI runs the same three checks across Python 3.9–3.12.

## Workflow

1. Open an issue describing the bug or feature before starting significant
   work, so we can agree on scope.
2. Create a branch off `main`.
3. Add or update tests in `tests/` for any behavior change — PRs without
   test coverage for new logic will be asked to add it.
4. Update `CHANGELOG.md` under `[Unreleased]` for user-visible changes.
5. Open a pull request with a clear description of the change and why it's
   needed.

**Changes to enforcement semantics** (constraint evaluation, fail-closed
defaults, trace completeness, circuit-breaker logic) are held to a higher
bar: tests must demonstrate both the old and the new behavior, and the
change needs an explicit CHANGELOG entry even when the diff is small. See
[MAINTAINERS.md](MAINTAINERS.md).

## Scope

This library provides runtime enforcement primitives for governed
autonomous agent actions: constraint-based action-space enforcement,
auditable decision traces, defense-in-depth safety controls, and
fail-closed network resilience. Contributions that strengthen or extend
these primitives — new constraint operators, additional safety-layer
building blocks, alternative resilience strategies, better audit export —
are welcome. Domain-specific policy content (e.g. a particular industry's
regulatory rules) is out of scope for the core library; it belongs in a
downstream `ConstraintEngine` configuration. Runtime dependencies are kept
at zero; anything that needs a third-party package belongs in an optional
extra or a separate adapter package (see [ROADMAP.md](ROADMAP.md)).

## Code style

Plain Python 3.9+, standard library only for runtime code. Keep functions
small and prefer explicit dataclasses over dictionaries for public return
types, matching the existing modules. `ruff` and `mypy` configurations in
`pyproject.toml` are the source of truth.

## Reporting security issues

Please do not open a public issue for a security-relevant bug — including
anything that bypasses constraints, safety layers, audit logging, or
fail-closed behavior. Follow [SECURITY.md](SECURITY.md) instead.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
