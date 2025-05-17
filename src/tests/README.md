# MCP Selenium Grid Test Suite

This directory contains all tests for the MCP Selenium Grid Server. The test suite is organized to support unit, integration, and end-to-end (E2E) testing, using modern FastAPI and pytest best practices.

## Test Organization

```
tests/
├── unit/           # Unit tests (fast, isolated, all dependencies mocked)
├── integration/    # Integration tests (real app logic, external services mocked)
├── e2e/            # End-to-end tests (real infrastructure, full workflows)
└── conftest.py     # Shared fixtures and configuration
```

## Test Types

### Unit Tests

- Test individual functions, classes, and modules in isolation.
- All dependencies are mocked.
- Fast and reliable.

**Run unit tests:**

```bash
uv run pytest src/tests/unit/
```

### Integration Tests

- Test how components work together (e.g., API endpoints, service interactions).
- External services (Docker, Kubernetes) are mocked, but real app logic is used.

**Run integration tests:**

```bash
uv run pytest src/tests/integration/
```

### End-to-End (E2E) Tests

- Test complete workflows using real infrastructure (e.g., Selenium, Docker, Kubernetes).
- These tests may require running containers or external services.
- E2E tests are always run when you invoke pytest on the e2e directory.

**Run E2E tests:**

```bash
uv run pytest src/tests/e2e/
```

## Running All Tests

To run the entire test suite (unit, integration, and E2E):

```bash
uv run pytest src/tests/ -v
```

Or, with coverage:

```bash
uv run pytest src/tests/ --cov=app --cov-report=term-missing
```

## Running by Marker

Tests are marked for convenience. You can run specific types using markers:

- **Unit:**

  ```bash
  uv run pytest -m unit
  ```

- **Integration:**

  ```bash
  uv run pytest -m integration
  ```

- **E2E:**

  ```bash
  uv run pytest -m e2e
  ```

## Environment Variables

- There is currently NO code that checks for `RUN_E2E_TESTS`. Setting this variable has no effect on test selection or skipping. All E2E tests will run if you invoke pytest on the e2e directory or use the `e2e` marker.
- If you want to add conditional skipping based on environment variables, see the pytest documentation for `pytest.mark.skipif`.

## Test Coverage

- Coverage is measured for the `app` package.
- Minimum coverage threshold is 80% (see `pyproject.toml`).
- To generate an HTML coverage report:

  ```bash
  uv run pytest --cov=app --cov-report=html
  # Open htmlcov/index.html in your browser
  ```

## Adding New Tests

1. Place new tests in the appropriate directory (`unit/`, `integration/`, or `e2e/`).
2. Use descriptive test names and docstrings.
3. Prefer fixtures for setup/teardown logic (see `conftest.py`).
4. Mark tests with `@pytest.mark.unit`, `@pytest.mark.integration`, or `@pytest.mark.e2e` as appropriate.

## Notes

- All dependencies and test tools are managed with [uv](https://github.com/astral-sh/uv). Use `uv` for all installs and test runs.
- The test suite is warning-free and compatible with the latest FastAPI, pytest, and Python versions.
- For more details, see the main project README and `pyproject.toml` for configuration specifics.
