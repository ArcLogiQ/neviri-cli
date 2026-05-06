# Contributing to neviri-cli

Thanks for helping build the Neviri CLI. This document covers the dev loop, code style, and PR expectations.

## Dev environment

Requires Python 3.11, 3.12, or 3.13.

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Local checks

Run before pushing:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

CI runs the same matrix on Linux, macOS, and Windows across all three Python versions. Anything that passes locally on one OS is not guaranteed to pass CI — keep cross-platform paths in mind (use `pathlib`, not string concatenation).

## Code style

- `ruff` config lives in `pyproject.toml`. We select `E`, `F`, `W`, `I`, `B`, `UP`, `RUF`.
- `mypy --strict` is required for `src/`. Tests are exempt.
- Default to no comments. Add one only when the *why* is non-obvious.
- Don't write multi-paragraph docstrings.

## Test coverage

The coverage gate is **90%** during Phase 1. It will be raised to **97%** before the Phase 2 GA cut, matching the backend's gate.

Coverage runs are scoped to `src/neviri_cli` and exclude `__main__.py`. Any module that drops below the gate fails CI; add tests rather than lowering the gate.

## Branches & commits

- Cut feature branches off `master`.
- One logical change per PR. Reviewers should be able to read the diff in one sitting.
- Conventional Commits are encouraged but not yet enforced (will be when `release-please` lands in Phase 3).

## Architecture rules

The CLI is a **pure HTTP client**. Do not:

- Import OpenStack SDKs.
- Open direct database connections.
- Re-implement business logic that lives in the backend.

Every action goes through the backend's public REST API. This is the most important architectural constraint and the reason the CLI exists in its own repo.
