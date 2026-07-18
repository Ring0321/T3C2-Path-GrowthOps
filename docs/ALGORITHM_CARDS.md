# T³-C² algorithm cards

## 1. Shared publication contract

Every module returns a typed result and explicit diagnostics. A numerical score is never sufficient for publication. The application layer must freeze `decision_time`, evidence IDs, knowledge version, model version, purpose and consent before computation, then pass the candidate through Algorithm F. All random operations require an explicit seed. All examples are synthetic.

## 2. Algorithm A — evidence-calibrated state

### 2.1 Estimand

The current latent readiness state for one dimension and one context, conditional on authorized evidence available at the decision time. It is not a permanent trait and is not a success probability.

### 2.2 Calculation

For evidence `i`, effective variance is:

```text
v_i = base_sd_i² / max(reliability_i, reliability_floor)
      × 2^(age_days_i / half_life_days)
      × (1 + duplicate_corr_i)
```

Sequential normal updating combines the prior with observations. A Huber-like weight limits an observation whose residual exceeds 2.5 joint standard deviations. Unknown and withdrawn observations are skipped rather than converted to zero. Repeated `duplicate_group` records receive a correlation penalty. Different contexts are calculated separately and a mean-gap diagnostic identifies possible context conflict.

### 2.3 Required validation

- Repeatability and inter-rater reliability of each measurement source.
- Time-based holdout for half-life and calibration parameters.
- Context-split and duplicate-source ablations.
- Coverage, error and deferral comparison across protected or resource groups.

### 2.4 Failure action

If authorization is invalid, no state update occurs. If context results conflict beyond a preregistered threshold, the interface must show separate states and request discriminating evidence. If the model does not improve over an equal-weight baseline, retain only the evidence ledger.

## 3. Algorithm B — multi-path temporal digital twin

### 3.1 Estimand

A distribution of path readiness and stage feasibility under current evidence, current rules and an explicitly stated action horizon. It is not admission, recruitment or employment probability.

### 3.2 Calculation

Each path contains requirement thresholds, normalized dimension weights, critical-margin rules, workload, transferability, window length and referenced hard-rule IDs. Monte Carlo draws propagate evidence-state uncertainty. Each draw calculates weighted shortfall and whether critical dimensions meet the safety margin. Non-dominated alternatives are retained across readiness, feasibility, transferability and workload.

### 3.3 Hard boundary

A missing, expired or not-yet-valid hard rule changes the path to `NEEDS_VERIFICATION`; feasibility probability and risk index become `None`. No soft score can offset this state. This is the main architectural difference from a conventional weighted recommendation.

### 3.4 Required validation

- Deadline, expiry and missing-rule regression tests.
- Monotonicity checks when all dimensions improve.
- Weight perturbation and critical-margin sensitivity.
- Comparison with an expert checklist and a simple weighted baseline.
- Rolling replay: recompute earlier decisions using only information available at that time.

## 4. Algorithm C — Safe-VOI minimum action experiment

### 4.1 Objective

Select a reversible next action that combines expected growth and expected information gain while controlling burden, risk and commercial inducement. The objective is to improve the next decision, not maximize clicks or course purchases.

### 4.2 Transparent MVP value

```text
value = 0.30 × expected_growth
      + 0.25 × information_gain
      + 0.20 × transferability
      + 0.15 × window_rescue
      - 0.10 × burden
      - 0.15 × risk
```

Consent, rule validity, reversibility and high-stakes status are evaluated before ranking. A paid action is blocked when a lower-cost, no-more-time-consuming action provides at least as much information. Blocked tasks keep their raw value for audit but have no publishable value or rank.

### 4.3 Required validation

Compare against random choice, adviser ordering, lowest-burden-first, maximum-growth-only and maximum-completion baselines. Primary outcomes are uncertainty reduction, path stability and burden—not click-through. If Safe-VOI does not beat lowest-burden-first, simplify to the baseline.

## 5. Algorithm D — formative student value-added

### 5.1 Estimand

```text
VA = observed readiness - expected readiness
     given baseline, stage, track and prespecified context
```

Observed and expected standard errors are propagated. The result is qualified only when measurement invariance is established, the reference sample reaches the minimum and the interval is narrow enough for individual interpretation. Synthetic inputs produce `SYNTHETIC_ONLY`; real research inputs cannot exceed `FORMATIVE` at the individual level.

### 5.2 Prohibited use

VA cannot rank students, determine eligibility, punish a low starting point or represent enterprise contribution. A wide interval means “uncertain,” not “no growth.” Model-specification sign changes stop individual reporting.

### 5.3 Required validation

Use cross-fitted reference predictions, report reference population and temporal split, test measurement invariance, compare change score/ANCOVA/hierarchical specifications and conduct missing-data sensitivity. Group summaries must preserve the distribution and uncertainty.

## 6. Algorithm E — group service effect

### 6.1 Target-trial contract

Before estimation, define eligibility, time zero, assigned strategies, comparator, intervention version, follow-up, outcome, estimand and missing-data rule. Randomized wait-list evaluation uses assignment-based ITT even when actual use crosses over. Observational AIPW uses supplied out-of-fold propensity and outcome predictions.

### 6.2 AIPW pseudo-outcome

```text
psi_i = m1_i - m0_i
      + A_i × (Y_i - m1_i) / e_i
      - (1-A_i) × (Y_i - m0_i) / (1-e_i)
SE = mean(psi_i)
```

The implementation reports the influence-function standard error and original propensity range. It refuses estimation when the comparator is absent, intervention versions are mixed or positivity fails. Clipping must not conceal non-overlap.

### 6.3 Claim boundary

Synthetic known-truth results validate code properties only. Real causal language additionally requires credible allocation or exchangeability, prespecified confounding control, stable treatment, outcome follow-up and sensitivity analysis. Otherwise the report must use associational language.

## 7. Algorithm F — calibration, fairness and selective publication

### 7.1 Diagnostics

- Brier score and expected calibration error from held-out predictions.
- Risk–coverage curve to verify that deferral actually reduces risk.
- Group error among published cases, publication coverage and mean task burden.
- Evidence coverage, interval width, rule validity and expected student workload.

Fairness auditing must include selective coverage and support burden. Removing sensitive attributes prevents auditing and is not itself a fairness solution. Attributes used for audit must be purpose-authorized and isolated from disadvantage scoring.

### 7.2 Decision order

1. Invalid consent → `BLOCK`.
2. High-stakes, large fairness gap or excessive workload → `HUMAN_REVIEW`.
3. Invalid rule, insufficient evidence, poor calibration or wide uncertainty → `DEFER` with a concrete remediation.
4. All gates pass → `PUBLISH`.

If lower coverage does not produce lower risk, confidence is not informative and the gate must be redesigned rather than silently raising its threshold.

## 8. Minimal-complexity rule

Every advanced component has a simple comparator and an ablation. Complexity is retained only if it improves a preregistered decision, calibration, fairness or burden metric without creating unacceptable operational cost. This rule prevents the project from treating Bayesian updating, Monte Carlo, AIPW or multi-agent decomposition as innovation by themselves; the innovation claim is limited to the auditable coupling of time, counterfactuals, safe action experiments and governance.
