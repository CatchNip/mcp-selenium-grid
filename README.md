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
 uv pip install -e ".[dev, test]"
```

### 3. Running Tests

You can run tests using pytest:

- **All tests:**

  ```bash
  uv run pytest src/tests/ -v
  ```

> **ℹ️ For more details on test types and structure, see [`src/tests/README.md`](src/tests/README.md).**
>
> ```bash
>  uv run pytest -m unit
> ```
>
> - The following test markers are available: `unit`, `integration`, `e2e`.

### 4. Code Quality

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
mypy .
```

## Dependency Management

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management and installation. All contributors and AI Agents should use `uv` for installing and updating dependencies.

- To install dependencies: `uv pip install .` or `uv pip install -e ".[dev]"` (for development)
- To add a dependency: `uv pip install <package>`

## 🔧 Environment Variables

Create a `.env` file with the following (edit as needed):

```env
# OAuth Configuration
MCP_OAUTH_ISSUER=https://your-domain
MCP_OAUTH_CLIENT_ID=your-client-id
MCP_OAUTH_CLIENT_SECRET=your-client-secret
MCP_OAUTH_AUDIENCE=your-audience

# Selenium Hub
SELENIUM_HUB_TOKEN_SECRET=random-secret-key
SELENIUM_HUB_PORT=4444

# Deployment
DEPLOYMENT_MODE=docker  # or kubernetes
K8S_NAMESPACE=selenium-grid

# Security
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000
```

## 📄 License

MIT

## Migration Notice

- The file `src/app/auth/oauth.py` is deprecated.
- Please use `src/app/auth/token.py` for token-based authentication.
