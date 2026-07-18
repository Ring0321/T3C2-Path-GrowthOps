## Change

Describe the smallest research or product behavior changed.

## Claim and boundary

- Claim/module:
- Allowed conclusion:
- Conclusion that remains prohibited:

## Verification

- [ ] A new test failed for the expected reason before implementation.
- [ ] `ruff check .`
- [ ] `mypy src`
- [ ] `pytest --cov=t3c2_path --cov-fail-under=85`
- [ ] Synthetic bundle reproduces with no diff.
- [ ] No personal data, secrets or causal-language upgrade is included.

## Failure and rollback

State the stop condition and how the feature degrades or rolls back.
