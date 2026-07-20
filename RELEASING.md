# Release checklist

Releases are cut by maintainers only (see [MAINTAINERS.md](MAINTAINERS.md)).
Nothing in this checklist is automated yet; run each step deliberately.

## 1. Prepare

- [ ] Decide the new version (`X.Y.Z`). Pre-1.0: breaking changes bump the
  minor version and must be listed in the changelog.
- [ ] Update `version` in `pyproject.toml`.
- [ ] Update `version` and `date-released` in `CITATION.cff`.
- [ ] Move entries from `[Unreleased]` to a new `[X.Y.Z] - YYYY-MM-DD`
  section in `CHANGELOG.md`, and update the compare links at the bottom.

## 2. Validate

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=safeagentl
ruff check .
mypy
python examples/pricing_agent.py
python examples/tool_approval_gate.py
```

- [ ] All tests pass on the oldest supported Python (3.9) locally or in CI.
- [ ] CI is green on the release commit.

## 3. Build distributions

```bash
pip install build twine
rm -rf dist/
python -m build          # produces sdist + wheel in dist/
twine check dist/*
```

- [ ] `twine check` reports PASSED for both artifacts.
- [ ] Unzip the wheel and confirm it contains `safeagentl/` (including
  `py.typed`) and no stray files.

## 4. Tag and publish the GitHub release

```bash
git tag -a vX.Y.Z -m "safe-agent-l X.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <(sed -n '/## \[X.Y.Z\]/,/## \[/p' CHANGELOG.md)
```

- [ ] Attach `dist/*` to the GitHub release.

## 5. Publish to TestPyPI, then PyPI

```bash
twine upload --repository testpypi dist/*
# verify: pip install -i https://test.pypi.org/simple/ safe-agent-l
#         python -c "import safeagentl; print(safeagentl.__version__)"
twine upload dist/*
```

- [ ] Install from TestPyPI in a clean venv and run the quickstart before
  uploading to real PyPI.
- [ ] After PyPI publish, verify `pip install safe-agent-l` works, then
  update the README installation section to prefer the PyPI path.

## 6. After release

- [ ] Bump `__version__` in `src/safeagentl/__init__.py` if it lags
  `pyproject.toml` (keep the two in sync).
- [ ] Announce in the repo Discussions/README if significant.
- [ ] If the release fixes a security issue, publish the advisory per
  [SECURITY.md](SECURITY.md) with credit to the reporter.
