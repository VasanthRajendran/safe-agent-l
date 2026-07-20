# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
| < 0.1 | ❌ |

Until 1.0, only the latest released minor version receives security fixes.

## What counts as a security issue here

Because this library exists to enforce guardrails, **bypass bugs are
security bugs**. Please report privately (not in a public issue) anything
that allows:

- an action to reach `Decision.allowed == True` despite violating a
  registered REJECT-mode constraint;
- a safety layer failure or open circuit breaker to be ignored;
- a timeout or network failure to *fail open* (proceed without verification)
  where the documented behavior is fail-closed;
- decision traces to be silently dropped, truncated, or logged as complete
  when required fields are missing;
- code execution, path traversal, or injection via constraint
  configurations, trace sinks, or any other input this library parses.

Ordinary bugs (wrong error message, docs typo, API ergonomics) can go to the
public issue tracker.

## How to report

1. **Preferred:** GitHub private vulnerability reporting — use
   ["Report a vulnerability"](https://github.com/VasanthRajendran/safe-agent-l/security/advisories/new)
   on this repository.
2. **Email:** vasanthr430@gmail.com with subject line `[SECURITY]
   safe-agent-l`. Include a description, affected version, and a minimal
   reproduction if you have one.

## What to expect

- Acknowledgment of your report within **7 days**.
- An assessment (accepted / not a vulnerability / needs more info) within
  **30 days**.
- Coordinated disclosure: please give us a reasonable window to release a
  fix before publishing details. We will credit reporters in the release
  notes unless you ask otherwise.

This is a volunteer-maintained project; response targets are best-effort
commitments, not an SLA.
