# 🤝 Contributing to MCP Selenium Grid

Thank you for your interest in contributing to MCP Selenium Grid!

## 🤝 Contributing Guidelines

### Issue Reporting

When reporting issues, please include:

- A clear and descriptive title
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Environment details (OS, Python version, etc.)
- Any relevant logs or error messages

### Code Style

- Follow the existing code style and formatting
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions small and focused on a single responsibility

### Testing

- Write tests for new features and bug fixes
- Ensure all tests pass before submitting a pull request
- Include unit, integration, e2e tests where appropriate

### Pull Request Process

1. **Fork the repository** - Click the "Fork" button on GitHub
2. **Create a feature branch** - Use a descriptive branch name:

   ```bash
   git checkout -b feature/amazing-feature
   git checkout -b fix/bug-description
   git checkout -b docs/update-readme
   ```

3. **Make your changes** - Write clean, well-documented code
4. **Run and write tests** - Ensure everything works
5. **Commit your changes** - Write clear, descriptive commit messages
6. **Push to your branch**
7. **Open a Pull Request** - Fill out the PR template

#### 💡 Commit Message Tips

- **Use emojis** to make commits more readable and fun! 🎉
- **Use AI tools** to generate commit messages

**Examples:**

```txt
✨ feature: Add Kubernetes deployment support
🐛 fix: browser instance cleanup on shutdown
📝 docs: Update MCP client configuration examples
♻️ refactor: split selenium hub logic into separated classes
✅ test: Add integration tests for browser workflow
```

**For bigger changes:**

```txt
✨ feature: Add Kubernetes deployment support

- Add Helm charts for Selenium Grid deployment
- Support for multiple Kubernetes contexts
- Automatic namespace creation and cleanup
- Health checks and monitoring integration
```

## 🚀 Quick Start for Development

### 1. Prerequisites

- [uv](https://github.com/astral-sh/uv) (Python dependency manager)
- [Docker](https://www.docker.com/)
- [K3s](https://k3s.io/) (for Kubernetes, optional)
- [kubectl](https://kubernetes.io/docs/tasks/tools/) (optional)

### 2. Setup

```bash
# Clone the repository
git clone git@github.com:Falamarcao/mcp-selenium-grid.git
cd mcp-selenium-grid

# Create a virtual environment and install dev/test dependencies
uv sync --all-groups --extra test --extra coverage
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

```bash
# See command help
uv run mcp-selenium-grid helm --help

# Deploy using default config
uv run mcp-selenium-grid helm deploy

# Deploy with specific context
uv run mcp-selenium-grid helm deploy --context k3s-selenium-grid

# Uninstall
uv run mcp-selenium-grid helm uninstall --delete-namespace
```

> See [scripts/helm/README.md](scripts/helm/README.md) for more details.

### 4. Start Server

```bash
# See command help
uv run mcp-selenium-grid server --help
uv run mcp-selenium-grid server run --help
uv run mcp-selenium-grid server dev --help

# Start server
uv run mcp-selenium-grid server run
uv run mcp-selenium-grid server run --host 127.0.0.1 --port 9000 --log-level debug

# Development mode with auto-reload
uv run mcp-selenium-grid server dev

# Using FastAPI Cli (auto-reload)
uv run fastapi dev src/app/main.py

# Using FastAPI Cli (no auto-reload)
uv run fastapi run src/app/main.py
```

### 5. Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test types
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m e2e

# Run with coverage
uv run coverage run -m pytest -m unit
uv run coverage report
```

#### 🧪 CI & Workflow Testing

- To test GitHub Actions workflows locally, see [`.github/README.md`](.github/README.md) for simple act usage instructions.

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

- Install all dependencies: `uv sync --all-groups --extra test --extra coverage`
- Add a dependency: `uv add <package>`
- Add a dev dependency: `uv add <package> --dev`
- Add a test dependency: `uv add <package> --optional test`
- Remove a dependency: `uv remove <package>`

## 📄 License

By contributing to MCP Selenium Grid, you agree that your contributions will be licensed under the MIT License.
