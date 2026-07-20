# Maintainers and Governance

## Maintainers

| Name | GitHub | Role |
|---|---|---|
| Vasanth Rajendran | [@VasanthRajendran](https://github.com/VasanthRajendran) | Lead maintainer |

## Decision process

The project currently follows a **BDFL-style model**: the lead maintainer
has final say on design direction, API changes, and releases. In practice,
decisions of any consequence happen in public — in issues and pull
requests — and community input is actively considered before merging.

Substantial changes (new public API, behavioral changes to enforcement
semantics, new dependencies) should start as an issue describing the
problem before a PR is opened, per [CONTRIBUTING.md](CONTRIBUTING.md).

Contributors with a sustained track record of quality contributions may be
invited to become maintainers.

## Release authority

Only maintainers can tag releases and publish packages. The release process
is documented in [RELEASING.md](RELEASING.md); every release must pass the
full CI matrix (tests, lint, type checks) first.

## Support expectations

This is a volunteer-maintained open-source project:

- Issues and PRs are triaged on a **best-effort** basis, typically within a
  couple of weeks.
- Security reports get priority handling per [SECURITY.md](SECURITY.md).
- There is no commercial support offering and no SLA. Companies adopting
  the library should plan to pin versions and review changes on upgrade,
  as with any pre-1.0 dependency.

## Enforcement semantics are load-bearing

A note for future maintainers: changes to enforcement behavior
(constraint evaluation, fail-closed defaults, trace completeness, breaker
logic) are treated as the highest-risk category of change. They require
tests demonstrating the old and new behavior and an explicit CHANGELOG
entry, even when the diff is small.
