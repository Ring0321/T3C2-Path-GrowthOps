# Model card — T³-C² Path GrowthOps 0.1.0

## 1. System identity

- **Type:** transparent research algorithms plus deterministic capability-bounded orchestration.
- **Status:** research alpha; synthetic-only reference implementation.
- **Release date:** 2026-07-19.
- **Owner:** repository maintainers.
- **No trained foundation model:** v0.1.0 does not ship learned weights or call an external LLM.

## 2. Intended use

The system is intended for low-risk, formative research on how authorized evidence can support an evolving student profile, multiple conditional paths, reversible next actions and explicit uncertainty. It may also support group-level evaluation design when target-trial and causal identification requirements are met.

Permitted prototype uses include synthetic demonstrations, algorithm property tests, adviser workflow design, usability research and preregistration preparation. Any real-data pilot requires ethics/privacy review, purpose-bound consent, local rule verification and qualified human supervision.

## 3. Prohibited use

- Automated admission, rejection, recruitment, pricing, ranking or disciplinary decisions.
- Inferring stable personality, disability, mental health, socioeconomic status or employability from chat text, face, voice or biometrics.
- Treating missing data as low ability or withdrawn evidence as available.
- Presenting path readiness as success probability.
- Presenting student VA as enterprise contribution, or presenting observational association as causal service effect.
- Silently changing intervention, knowledge or model versions during evaluation.

## 4. Components

| Module | Output | Main uncertainty | Stop condition |
|---|---|---|---|
| A Evidence state | posterior and interval by dimension/context | reliability, age, duplicate origin | invalid authorization or unresolved conflict |
| B Path twin | readiness distribution and Pareto set | state and rule uncertainty | missing/expired hard rule |
| C Safe-VOI | gated reversible task order | expected information and burden | unsafe, high-stakes or dominated paid action |
| D Student VA | observed-minus-expected with interval | measurement and reference model | non-invariance, small reference, wide interval |
| E Service SE | randomized ITT or AIPW group estimate | allocation, confounding, positivity, attrition | no comparator, mixed version or non-overlap |
| F Safety gate | publish/defer/review/block | calibration, fairness, coverage, workload | any gate failure |

## 5. Evaluation evidence

The automated suite covers schema contracts, time semantics, evidence updates, path rules, Pareto filtering, Safe-VOI dominance, VA uncertainty, randomized ITT, AIPW, calibration, risk–coverage, fairness burden, agent permissions, API contracts, audit tampering and export reproducibility.

For seed `20260719`, the 1200-row synthetic generator injected an average effect of `2.9947`. The unadjusted treated-control difference was `7.2944`; AIPW was `2.6000` with interval `[2.0964, 3.1035]`. AIPW absolute bias was `0.3948`, versus `4.2996` for the naive estimator. These values are a code validation under an explicitly favorable generator with known nuisance functions, not performance estimates for real students.

## 6. Fairness

The system audits error among published cases, selective coverage and mean task burden. Small groups are marked non-estimable. Audit attributes must be separately authorized and isolated from student-facing disadvantage scoring. No single fairness metric is declared universally sufficient, and thresholds must be preregistered by use case.

## 7. Limitations

- Reliability, half-life, weights and thresholds are research defaults, not locally calibrated parameters.
- Monte Carlo readiness depends on the declared rubric and is not admission probability.
- The AIPW reference accepts prespecified nuisance predictions; it does not prove that real confounding is controlled.
- The audit store is in-memory and the API lacks production identity, persistence, rate limiting and tenant isolation.
- The deterministic explanation is intentionally limited; future LLM integration introduces hallucination and prompt-injection risks.
- No evidence currently establishes user acceptance, outcome improvement, transportability, enterprise ROI or production fairness.

## 8. Monitoring and retirement

Production candidates must monitor time drift, rule expiry, missingness, calibration, group coverage/error/burden, human override, complaints and adverse events. A module is disabled when its preregistered stop condition is met. A new version first replays historical snapshots and red-team cases in shadow mode; it never silently replaces the active intervention during a study.
