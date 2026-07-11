# Contributing to safe-agent-l

Thanks for your interest in improving safe-agent-l.

## Getting started

```bash
git clone https://github.com/vasanthr430/safe-agent-l.git
cd safe-agent-l
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Workflow

1. Open an issue describing the bug or feature before starting significant
   work, so we can agree on scope.
2. Create a branch off `main`.
3. Add or update tests in `tests/` for any behavior change — PRs without
   test coverage for new logic will be asked to add it.
4. Run `pytest` locally and make sure it's green.
5. Open a pull request with a clear description of the change and why it's
   needed.

## Scope

This repository implements the four SAFE-AGENT-L pillars (constraint-based
action-space enforcement, decision explainability, defense-in-depth safety
controls, and network-aware resilience) as a reusable library. Contributions
that strengthen or extend these primitives — new constraint operators,
additional safety-layer building blocks, alternative network-resilience
strategies — are welcome. Domain-specific policy content (e.g. a particular
industry's regulatory rules) is out of scope for the core library; it
belongs in a downstream `ConstraintEngine` configuration.

## Code style

Plain Python 3.9+, standard library only for runtime code. Keep functions
small and prefer explicit dataclasses over dictionaries for public return
types, matching the existing modules.

## Reporting security issues

Please do not open a public issue for a security-relevant bug in the safety
or constraint-enforcement logic. Email the maintainer at
vasanthr430@gmail.com instead.

## Code of conduct

Be respectful and constructive. Harassment or discriminatory language will
not be tolerated in issues, pull requests, or discussions.
