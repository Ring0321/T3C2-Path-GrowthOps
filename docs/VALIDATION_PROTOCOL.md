# Reproducible validation protocol

## 1. Validation question

The current question is not “does the product work in the market?” It is “does each implemented mechanism obey its declared mathematical, safety and evidence boundary, and does it fail visibly when an identification condition is absent?”

## 2. Validation ladder

### 2.1 L0 — contracts and unit properties

Validate immutable schemas, unknown-not-zero, purpose/time consent, subject isolation, rule validity and VA/SE type separation. Directional tests require reliability to reduce effective variance, evidence age and duplicate origin to increase it, stronger latent states not to reduce simulated readiness, and a dominated paid task to be blocked.

### 2.2 L1 — synthetic known truth

Generate assignment with observed selection bias, save both potential outcomes and the true individual effect, then compare:

1. unadjusted treated-control outcome difference;
2. randomized assignment ITT when applicable;
3. supplied-nuisance AIPW with influence-function interval.

The code passes this fixed exercise when AIPW absolute bias is below `0.5`, lower than naive bias, true ATE lies inside the reported interval, propensity remains inside the prespecified region and all artifacts reproduce byte-for-byte. These thresholds test the fixed generator, not general estimator superiority.

### 2.3 L1b — red-team boundaries

The 12-case registry attacks consent withdrawal, subject crossover, rule expiry, unknown values, high-stakes automation, commercial inducement, intervention-version mixing, positivity, group disparity, prompt-like source text, audit tampering and causal-language upgrade. Each new incident becomes a permanent regression case.

### 2.4 L2 — usability and no-harm study (not yet conducted)

Recruit 12–15 students only after ethics/privacy review. Test whether they understand intervals, evidence sources, multiple conditional paths, dispute/withdrawal and task exit. Stop if users interpret readiness as success probability, cannot correct evidence, feel coerced toward paid action or show unacceptable distress.

### 2.5 L3 — eight-week wait-list pilot (not yet conducted)

Suggested sample: 120 students, random wait-list allocation where feasible, measurements at baseline/week 4/week 8. Primary outcomes: direction clarity, path preparation and valid task completion. Secondary outcomes: retention, adoption, trust and adviser time. Analyze ITT ANCOVA, report adjusted difference/effect size/interval, attrition and all preregistered outcomes. Do not replace assignment with actual product use.

### 2.6 L4 — multi-site longitudinal validation (not yet conducted)

Evaluate measurement invariance, temporal calibration, institutional transportability, group error/coverage/burden, rule drift and human override across schools and cohorts. Freeze intervention and knowledge versions within each causal contrast.

## 3. Baselines and ablations

| Module | Simple baseline | Required ablation |
|---|---|---|
| Evidence state | latest evidence; equal-weight mean | remove decay; remove duplicate penalty; merge contexts |
| Path twin | adviser checklist; weighted sum | remove hard gate; remove transferability; perturb weights |
| Safe-VOI | random; lowest burden; maximum growth | remove information gain; remove paid-action dominance |
| VA | change score; baseline ANCOVA | change reference group and model specification |
| SE | unadjusted difference; regression; randomized ITT | remove overlap check; mix versions as a negative control |
| Safety gate | full coverage; fixed confidence threshold | remove selective deferral and compare risk–coverage |

## 4. Reproduction

All continuous generator fields are canonicalized to ten decimal places and CSV uses LF line endings. This does not imply ten-decimal measurement accuracy. It isolates meaningful algorithm changes from last-bit differences in operating-system math libraries and text serialization, so every supported Python/platform combination can verify the same logical and file hashes.

```bash
python -m pip install -e ".[dev,api,research]"
pytest --cov=t3c2_path --cov-report=term-missing
python scripts/export_validation_bundle.py
git diff --exit-code -- research/generated
ruff check .
mypy src
python -m build
pip-audit
```

The report always separates `observed`, `expected_property` and `claim_boundary`. Failure is a result: the responsible module is simplified, deferred or disabled rather than reworded as success.
