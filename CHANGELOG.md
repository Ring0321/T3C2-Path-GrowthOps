# Changelog

All notable changes are documented here. The project follows Semantic Versioning.

## [Unreleased]

### Added

- Executable specification, research boundaries and architecture baseline.
- Immutable domain contracts for consent, evidence, profiles, paths, tasks, service exposure, VA, SE, disputes, review tickets and audit events.
- Separate evidence, path and service clocks with expiry, crossover and intervention-version diagnostics.
- Algorithm A robust evidence-state updates with reliability, decay, duplicate-source and context-conflict handling.
- Algorithm B reproducible multi-path Monte Carlo simulation with hard-rule blocking and Pareto filtering.
- Algorithm C Safe-VOI task gating that prevents scores from overriding consent, reversibility, high-stakes and lower-cost alternatives.
- Algorithm D formative VA with measurement-invariance, reference-sample and interval-width stop rules.
- Algorithm E randomized ITT and AIPW service-effect estimators with target-trial, intervention-version and positivity checks.
- Algorithm F calibration, risk-coverage, group error/coverage/burden audits and selective publication gates.
- Capability-bounded evidence, path, task, governance, explanation and audit agents.
- Deterministic decision orchestrator, tamper-evident audit chain, synthetic CLI and versioned REST endpoint.
