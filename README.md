# 🤖 MCP Selenium Grid

A Model Context Protocol (MCP) server that enables AI Agents to request and manage Selenium browser instances through a secure API. Perfect for your automated browser testing needs! 🚀

## 🚀 Quick Start for Development

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

-----

### 3. Kubernetes Setup (Optional for tests and using K8s backend)

This project requires a Kubernetes cluster for running tests and managing browser instances. We use K3s for local development and testing.

#### Install K3s ([https://docs.k3s.io/quick-start](https://docs.k3s.io/quick-start))

```bash
# Install K3s
curl -sfL https://get.k3s.io | sh -

# Verify installation
k3s --version
```

#### Create K3s Kubernetes Context (Optional)

After installing K3s, you might want to create a dedicated `kubectl` context for it. This makes it easier to switch between different Kubernetes clusters if you have them.

First, copy the K3s `kubeconfig` file to your standard `kubeconfig` directory:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config-local-k3s
sudo chown $USER:$USER ~/.kube/config-local-k3s
chmod 600 ~/.kube/config-local-k3s
```

```bash
# start if not running
sudo systemctl start k3s
```

Next, you can add a new context named **k3s** to your `kubeconfig`:

```bash
KUBECONFIG=~/.kube/config-local-k3s \
kubectl config set-context k3s-selenium-grid \
  --cluster=default \
  --user=default
```

Now, the **k3s** context is available for you to use. You can switch to it anytime with `kubectl config use-context k3s` or specify it for individual commands using the `--context k3s` flag.

#### Deploy Selenium Grid using the Helm Chart

Deploy using kubernetes context from [config.yaml](./config.yaml).

```bash
uv run helm-selenium-grid deploy
```

Deploy using a specific kubernetes context:

```bash
uv run helm-selenium-grid deploy --context k3s-selenium-grid
```

Uninstall using kubernetes context from [config.yaml](./config.yaml).

```bash
uv run helm-selenium-grid uninstall
```

Uninstall and delete the namespace from a given context:

```bash
uv run helm-selenium-grid uninstall --context k3s-selenium-grid --delete-namespace
```

> - **Note:** For more details, see the [README.md](scripts/helm/README.md).

-----

### 4. Start Server

- **Development server with auto-reload:**

```bash
# Uses fastapi-cli to run uvicorn.
uv run fastapi dev src/app/main.py
```

> - `uv run` uses the virtual environment to run the command, then you don't need to activate the enviroment to run the commands.
> **Note:** activating the enviroment helps IDE's autocompletion and AI Agents.

-----

### 5. Running Tests

You can run tests using pytest:

- **Run unit tests:**

  ```bash
  uv run pytest -m unit
  ```

> - The following test markers are available: `unit`, `integration`, `e2e`.
> **Note:** Integration and e2e tests interact with real infrastructure (Docker/Kubernetes) and require these services to be running.
> **ℹ️ For more details on test types and structure, see [`src/tests/README.md`](src/tests/README.md).**

### 6. Code Quality

Format code:

```bash
uv run ruff format .
```

Lint code:

```bash
uv run ruff check .
```

Type check:

```bash
uv run mypy .
```

-----

### 7. Clean Cache

```bash
# Clear pycache files
uvx pyclean .

# Clear ruff cache
uv run ruff clean
```

-----

## Dependency Management

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management and installation. All contributors and AI Agents should use `uv` for installing and updating dependencies.

- To install dependencies: `uv sync --all-groups --extra test` (install all including dev and test)
- To add a dependency: `uv add <package>`
- To add a dev dependency: `uv add <package> --dev`
- To add a test dependency: `uv add <package> --optional test`

## 📄 License

MIT
