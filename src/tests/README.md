# MCP Selenium Grid Test Suite

This directory contains all tests for the MCP Selenium Grid Server.

## Test Types

- **Unit tests** - Fast, isolated tests with mocked dependencies
- **Integration tests** - Test component interactions with real services
- **E2E tests** - Full workflow tests with real infrastructure

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test types
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m e2e

# Run specific tests by name
uv run pytest -k "kubernetes"
uv run pytest -k "docker"
```

## Coverage

```bash
# Run tests with coverage
uv run coverage run -m pytest -m unit

# Show coverage report
uv run coverage report

# Generate HTML report
uv run coverage html
```

## Adding Tests

1. Place tests in the appropriate directory (`unit/`, `integration/`, or `e2e/`)
2. Use descriptive test names
3. Mark tests with appropriate pytest markers
