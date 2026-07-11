---
title: 'safe-agent-l: A Reference Implementation of the SAFE-AGENT-L Governance Framework for Autonomous AI Agent Systems'
tags:
  - Python
  - artificial intelligence
  - AI safety
  - AI governance
  - multi-agent systems
  - explainability
  - responsible AI
authors:
  - name: Vasanth Rajendran
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 11 July 2026
bibliography: paper.bib
---

# Summary

`safe-agent-l` is a small, dependency-free Python library that implements
SAFE-AGENT-L, a governance framework for autonomous AI agent systems built
around four architectural invariants: (1) legal compliance by design, where
an agent's action space is restricted so that impermissible outputs cannot
be produced; (2) explainability, where every autonomous decision is logged
as a complete, reconstructable trace; (3) defense-in-depth safety controls,
where independent safety layers and a circuit breaker ensure no single
point of failure lets an unsafe action reach production; and (4)
network-aware resilience, where these controls keep functioning under
network delay, message loss, or partition. The library provides one module
per pillar (`constraints`, `explainability`, `safety`, `network`) plus a
`SafeAgent` orchestrator that composes them into a single decision
pipeline, and includes a self-assessment helper against three conformance
levels (minimum, recommended, exemplary). The package ships with a
48-test pytest suite and an end-to-end example wiring all four pillars
around a simulated pricing agent.

# Statement of need

Autonomous AI agents are increasingly deployed to make consequential
decisions — setting prices, allocating inventory, completing
transactions — without a human in the loop for each decision, often at
millisecond timescales and with dozens of inter-agent messages per user
request [@euaiact2024]. Existing AI governance guidance, including the
NIST AI Risk Management Framework [@nist2023airmf], ISO/IEC 42001
[@iso42001_2023], and the IEEE 7000 series [@ieee7000_2021; @ieee7001_2021],
establishes risk-management processes, management-system requirements, and
ethical-design principles at the organizational level. None of these
specify concrete, testable architectural mechanisms for keeping policy
enforcement, decision traceability, and safety controls effective inside a
running agent system, or for defining how those controls should degrade
gracefully — rather than fail open — when the underlying network is slow,
lossy, or partitioned. Emerging IEEE efforts targeting agentic AI more
broadly, such as P3709 [@ieee_p3709] and P7022 [@ieee_p7022], are still in
early development and do not yet provide a reference implementation
researchers or practitioners can install, test against, or extend.

`safe-agent-l` fills this gap by making the four SAFE-AGENT-L pillars
concrete and runnable rather than descriptive. The constraint engine
(Pillar 1) encodes machine-readable policy rules and either rejects or
clips out-of-bound agent outputs, with a pre-deployment check for
contradictory constraints. The decision logger (Pillar 2) enforces a
minimum trace-completeness bar at log time, so incomplete audit records are
caught immediately rather than discovered during a later investigation.
The safety stack (Pillar 3) composes independently evaluated safety layers
— including a rolling z-score anomaly detector — behind a circuit breaker
modeled on the software circuit-breaker pattern [@nygard2018release] and on
defense-in-depth principles from systems safety engineering
[@leveson2011engineering]. The network module (Pillar 4) supplies a
priority router for safety-critical control signals, a
timeout-to-safe-default wrapper that fails closed rather than open, and a
partition-tolerant policy cache that keeps enforcing the last-known-good
policy through a network partition and resynchronizes afterward.

The intended audience is researchers studying AI agent governance and
practitioners building or evaluating autonomous agent systems who need a
concrete, testable baseline rather than a purely conceptual framework. The
library is deliberately implementation-agnostic with respect to the
underlying agent policy: it wraps any `propose_fn` that returns an action
dictionary, so it can sit in front of an LLM-based agent, a reinforcement
learning policy, or a rule-based system without modification. The
underlying SAFE-AGENT-L framework was presented to the IEEE Future
Networks AI/ML Working Group in February 2026 and is the subject of a
Project Authorization Request within IEEE ComSoc COM/NetSoft SC toward a
proposed IEEE Recommended Practice; this software is an independent,
permissively licensed companion to that effort and does not itself carry
any conformance claim to a not-yet-published standard.

# Acknowledgements

We acknowledge feedback from the IEEE Future Networks AI/ML Working Group
that helped clarify the scope of the four pillars implemented here.

# References
