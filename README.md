# 🤖 MCP Selenium Grid

A Model Context Protocol (MCP) server for managing Selenium browser instances through a REST API. Useful for browser automation and testing workflows.

The MCP Selenium Grid provides a REST API for creating and managing browser instances in both Docker and Kubernetes environments. It's designed to work with AI agents and automation tools that need browser automation capabilities.

## Key Features

- **Multi-browser support**: Chrome, Firefox, and other Selenium-compatible browsers
- **Dual backend support**: Docker and Kubernetes deployment modes
- **Secure API**: Token-based authentication for browser management
- **Scalable architecture**: Support for multiple browser instances
- **MCP compliance**: Follows Model Context Protocol standards

## 📖 Usage

The MCP Selenium Grid provides a REST API for creating and managing browser instances. The server runs on `localhost:8000` and exposes MCP endpoints at `/mcp`.

### MCP Client Configuration

To use the MCP Selenium Grid with MCP-compatible clients (like Cursor, VS Code, etc.), add the server configuration to your `mcp.json` file:

```json
{
  "mcpServers": {
    "selenium-grid": {
      "command": "uv",
      "args": ["run", "fastapi", "run", "src/app/main.py"],
      "env": {
        "API_TOKEN": "CHANGE_ME",
        "DEPLOYMENT_MODE": "docker",
        "SELENIUM_GRI__USERNAME": "USER",
        "SELENIUM_GRID__PASSWORD": "CHANGE_ME",
        "SELENIUM_GRID__VNC_PASSWORD": "CHANGE_ME",
        "SELENIUM_GRID__VNC_VIEW_ONLY": false,
        "SELENIUM_GRID__MAX_BROWSER_INSTANCES": 4,
        "SELENIUM_GRID__SE_NODE_MAX_SESSIONS": 1,
      }
    }
  }
}
```

```json
{
  "mcpServers": {
    "selenium-grid": {
      "command": "uv",
      "args": ["run", "fastapi", "run", "src/app/main.py"],
      "env": {
        "API_TOKEN": "CHANGE_ME",
        "DEPLOYMENT_MODE": "kubernetes",
        "SELENIUM_GRI__USERNAME": "USER",
        "SELENIUM_GRID__PASSWORD": "CHANGE_ME",
        "SELENIUM_GRID__VNC_PASSWORD": "CHANGE_ME",
        "SELENIUM_GRID__VNC_VIEW_ONLY": false,
        "SELENIUM_GRID__MAX_BROWSER_INSTANCES": 4,
        "SELENIUM_GRID__SE_NODE_MAX_SESSIONS": 1,
        "KUBERNETES__KUBECONFIG": "~/.kube/config-local-k3s",
        "KUBERNETES__CONTEXT": "k3s-selenium-grid",
        "KUBERNETES__NAMESPACE": "selenium-grid-dev",
        "KUBERNETES__SELENIUM_GRID_SERVICE_NAME": "selenium-grid",
      }
    }
  }
}
```

Once the server is running, you can access the interactive API documentation at: **<http://localhost:8000/docs>**

## 🚀 Quick Start for Development

### 1. Prerequisites

- [uv](https://github.com/astral-sh/uv) (Python dependency manager)
- [Docker](https://www.docker.com/)
- [K3s](https://k3s.io/) (for Kubernetes, optional)
- [kubectl](https://kubernetes.io/docs/tasks/tools/) (optional)

### 2. Setup

```bash
# Clone the repository
 git clone <this-repo-url>
 cd <repo>

# Create a virtual environment and install dev/test dependencies
 uv sync --all-groups --extra test
```

### 3. Kubernetes Setup (Optional)

This project requires a Kubernetes cluster for running tests and managing browser instances. We use K3s for local development and testing.

#### Install K3s (<https://docs.k3s.io/quick-start>)

```bash
# Install K3s
curl -sfL https://get.k3s.io | sh -

# Verify installation
k3s --version

# Start if not running
sudo systemctl start k3s
```

#### Create K3s Kubernetes Context (Optional)

After installing K3s, you might want to create a dedicated `kubectl` context for it:

```bash
# Copy K3s kubeconfig
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config-local-k3s
sudo chown $USER:$USER ~/.kube/config-local-k3s
chmod 600 ~/.kube/config-local-k3s

# Create context
KUBECONFIG=~/.kube/config-local-k3s \
kubectl config set-context k3s-selenium-grid \
  --cluster=default \
  --user=default
```

#### Deploy Selenium Grid

Using kubernetes context name from [config.yaml](./config.yaml):

```bash
uv run helm-selenium-grid deploy
```

For a given kubernetes context name:

```bash
uv run helm-selenium-grid deploy --context k3s-selenium-grid
```

Uninstall:

```bash
uv run helm-selenium-grid uninstall --delete-namespace
uv run helm-selenium-grid uninstall --context k3s-selenium-grid --delete-namespace
```

> See [scripts/helm/README.md](scripts/helm/README.md) for more details.

### 4. Start Server

```bash
uv run fastapi dev src/app/main.py
```

> `uv run` uses the virtual environment automatically. Activating the environment is optional but helps IDEs.

### 5. Running Tests

```bash
uv run pytest -m unit         # Unit tests
uv run pytest -m integration  # Integration tests (needs Docker/K8s)
uv run pytest -m e2e          # E2E tests (needs Docker/K8s)
```

#### 🧪 CI & Workflow Testing

- To test GitHub Actions workflows locally, see [`.github/README.md`](.github/README.md) for simple act usage instructions.

  > See [`src/tests/README.md`](src/tests/README.md) for test details.

### 6. Code Quality

```bash
uv run ruff check .           # Lint
uv run mypy .                 # Type check
uv run ruff format .          # Format
```

This project uses pre-commit hooks configured in `.pre-commit-config.yaml` for automated code quality checks. If the pre-commit configuration is updated, run:

```bash
uv run pre-commit install && uv run pre-commit autoupdate && uv run pre-commit run --all-files
```

> Installs hooks, updates them to latest versions, and runs all hooks on all files.

### 7. Clean Cache

```bash
uvx pyclean .                 # Clear pycache
uv run ruff clean             # Clear ruff cache
```

## 📦 Dependency Management

- Install all dependencies: `uv sync --all-groups --extra test`
- Add a dependency: `uv add <package>`
- Add a dev dependency: `uv add <package> --dev`
- Add a test dependency: `uv add <package> --optional test`

## 📄 License

MIT
