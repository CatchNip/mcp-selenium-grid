# 🤖 MCP Selenium Grid

A Model Context Protocol (MCP) server that enables AI Agents to request and manage Selenium browser instances through a secure API. Perfect for your automated browser testing needs! 🚀

## 🚀 Quick Start

### 1. Prerequisites

Make sure you have the following installed:

- [uv](https://github.com/astral-sh/uv) (Python package/dependency manager)
- [Docker](https://www.docker.com/)
- [K3s](https://k3s.io/) (for Kubernetes deployment)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)

### 2. Setup - (using [.python-version](./.python-version))

```bash
# Clone the repository
 git clone <this-repo-url>
 cd <repo>

# Create a virtual environment
 uv venv

# Install dependencies for development and testing
 uv sync --all-groups --extra test
```

### 3. Start Server

- **Development server with auto-reload:**

```bash
# Uses fastapi-cli to run uvicorn.
uv run fastapi dev src/app/main.py
```

Notes: `uv run` uses the virtual environment to run the command, then you don't need to activate the enviroment to run the commands.
But activating the enviroment helps IDE's autocompletion and AI Agents.

### 4. Running Tests

You can run tests using pytest:

- **Run unit tests:**

  ```bash
  uv run pytest -m unit
  ```

> - The following test markers are available: `unit`, `integration`, `e2e`.
> **ℹ️ For more details on test types and structure, see [`src/tests/README.md`](src/tests/README.md).**

### 5. Code Quality

Format code:

```bash
uv run black .
```

Lint code:

```bash
uv run ruff check .
```

Type check:

```bash
uv run mypy .
```

### 6. Clean Cache

```bash
# Clear pycache files
uvx pyclean .

# Clear ruff cache
uv run ruff clean
```

## Dependency Management

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management and installation. All contributors and AI Agents should use `uv` for installing and updating dependencies.

- To install dependencies: `uv pip install .` or `uv pip install -e ".[dev, test]"` (for development)
- To add a dependency: `uv add <package>`
- To add a dev dependency: `uv add <package> --dev`
- To add a test dependency: `uv add <package> --optional test`

## 📄 License

MIT
