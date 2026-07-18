# Contributing

## Development flow

1. Open an issue describing the research or product claim being changed.
2. State the expected behavior, failure condition and claim boundary.
3. Write a failing test and record why it failed.
4. Implement the smallest change, run all quality gates and update documentation.
5. Keep commits atomic; never mix synthetic demonstrations with claims about real effects.

## Required checks

```bash
pytest --cov=t3c2_path --cov-report=term-missing
ruff check .
mypy src
python -m build
```

Contributions containing personal data, secrets, unverifiable outcome claims, discriminatory high-stakes scoring or silent safety-gate bypasses will not be accepted.

