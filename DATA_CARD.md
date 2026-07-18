# Data card — synthetic known-truth validation cohort

## 1. Dataset purpose

`research/generated/synthetic_known_truth.csv` exists only to verify estimator mechanics against known potential outcomes and a known treatment propensity. It is not intended to resemble a real university population in distribution, language, culture, disability, major or career opportunity.

## 2. Generation

- Generator: `t3c2_path.research.generate_known_truth_cohort`.
- Seed: `20260719`.
- Rows: `1200`; analyzed after synthetic missingness: `1143`.
- IDs: `SYN-00001` style; no real identifiers or source records.
- Assignment depends on baseline readiness, motivation and resource access, intentionally creating selection bias.
- Potential outcomes share random noise; individual true effect varies with motivation and resource access.
- Ten percent crossover is injected between assignment and actual receipt; five percent independent outcome missingness is injected.
- Propensity range among analyzed rows: `[0.1359, 0.8808]`.

## 3. Fields

| Field | Meaning | Use boundary |
|---|---|---|
| subject_id | synthetic row key | never map to a person |
| baseline_readiness | generated baseline covariate | not a validated readiness scale |
| motivation/resource_access | generated confounders in `[0,1]` | not inferred protected attributes |
| propensity | known generated assignment probability | validation only |
| assigned/received_service | assignment and actual use | preserve ITT distinction |
| expected_y0/expected_y1 | known conditional mean potential outcomes | unavailable in real studies |
| y0/y1 | known potential outcomes | unavailable jointly for a real person |
| observed_outcome | outcome selected by assignment | synthetic only |
| true_effect | `y1-y0` | known-truth validation only |
| observed | synthetic follow-up flag | tests filtering and attrition counts |
| is_synthetic | mandatory provenance marker | must remain `true` |

## 4. Quality and integrity

The manifest records row count, generator, seed, dataset hash, byte size and SHA-256 for each artifact. CI regenerates the bundle and fails when committed artifacts differ. Tests require all IDs and provenance markers to remain synthetic.

## 5. Privacy and ethics

No personal data were used. The dataset is therefore not evidence that real-data collection is lawful or low risk. Real pilots require data minimization, purpose binding, withdrawal handling, retention rules, role-based access, fairness-audit isolation and an approved response process for student disputes.

## 6. Limitations

The generator is intentionally simple and correctly specified for AIPW. It does not include unmeasured confounding, complex missing-not-at-random mechanisms, interference, changing service versions, measurement non-invariance, institutional clustering or policy drift. Passing this dataset is necessary for code sanity and insufficient for real causal inference.
