# Helm Selenium Grid CLI

This command-line interface (CLI) tool, `helm-selenium-grid`, is designed to simplify the deployment and management of the Selenium Grid on Kubernetes using Helm.

It interacts with your `config.yaml` for default settings but allows overriding these settings via command-line options.

## Installation

This script is part of the MCP Selenium Grid project. Ensure you have followed the main project's Quick Start for Development to set up your environment and install dependencies.

The script is made available as `helm-selenium-grid` via the `pyproject.toml` configuration:

```toml
[project.scripts]
helm-selenium-grid = "scripts.helm.main:app"
```

You can run the commands using `uv run helm-selenium-grid <command> [OPTIONS]`.

## Commands

### `deploy`

Deploys or upgrades the Selenium Grid Helm release on your Kubernetes cluster.

**Usage:**

```bash
uv run helm-selenium-grid deploy [OPTIONS]
```

**Options:**

- `--chart-path PATH`: Path to the Helm chart.
  - Default: `deployment/helm/selenium-grid`
- `--release-name TEXT`: Name of the Helm release.
  - Default: `selenium-grid`
- `--namespace TEXT`: Kubernetes namespace.
  - Default: Value from `config.yaml` (`K8S_NAMESPACE`)
- `--context TEXT`: Kubernetes context to use (e.g., 'k3s'). Overrides context from `config.yaml`.
  - Default: Value from `config.yaml` (`K8S_CONTEXT`)
- `--kubeconfig PATH`: Path to the kubeconfig file. Overrides `K8S_KUBECONFIG` from settings.
  - Default: None
- `--debug`: Enable debug output.
  - Default: `False`
- `--help`: Show help message and exit.

**Example:**

```bash
# Deploy using defaults from config.yaml
uv run helm-selenium-grid deploy

# Deploy to a specific Kubernetes context and namespace
uv run helm-selenium-grid deploy --kube-context k3s --namespace selenium
```

### `uninstall`

Uninstalls the Selenium Grid Helm release from your Kubernetes cluster.

**Usage:**

```bash
uv run helm-selenium-grid uninstall [OPTIONS]
```

**Options:**

- `--release-name TEXT`: Name of the Helm release to uninstall.
  - Default: `selenium-grid`
- `--namespace TEXT`: Kubernetes namespace.
  - Default: Value from `config.yaml` (`K8S_NAMESPACE`)
- `--context TEXT`: Kubernetes context to use. Overrides context from `config.yaml`.
  - Default: Value from `config.yaml` (`K8S_CONTEXT`)
- `--kubeconfig PATH`: Path to the kubeconfig file. Overrides `K8S_KUBECONFIG` from settings.
  - Default: None
- `--delete-namespace`: Delete the Kubernetes namespace after uninstalling the release.
  - Default: `False`
- `--debug`: Enable debug output.
  - Default: `False`
- `--help`: Show help message and exit.

**Example:**

```bash
# Uninstall using defaults from config.yaml
uv run helm-selenium-grid uninstall

# Uninstall and delete namespace from a specific Kubernetes context and namespace
uv run helm-selenium-grid uninstall --context k3s-selenium-grid --namespace selenium-grid-dev --delete-namespace
```

For more detailed deployment information, including configuration options and troubleshooting, see [Deployment Guide](src/deployment/README.md).
