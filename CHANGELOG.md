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
