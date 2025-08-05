# 🤖 MCP Selenium Grid

[![Tests](https://github.com/CatchNip/mcp-selenium-grid/actions/workflows/1_tests.yml/badge.svg?branch=main)](https://github.com/CatchNip/mcp-selenium-grid/actions/workflows/1_tests.yml)
![GitHub Last Commit](https://img.shields.io/github/last-commit/CatchNip/mcp-selenium-grid)
[![GitHub Release](https://img.shields.io/github/v/release/CatchNip/mcp-selenium-grid?include_prereleases)](https://github.com/CatchNip/mcp-selenium-grid/releases)
![GitHub commits since latest release](https://img.shields.io/github/commits-since/CatchNip/mcp-selenium-grid/latest?include_prereleases)
![GitHub Commit Activity](https://img.shields.io/github/commit-activity/m/CatchNip/mcp-selenium-grid)
![GitHub Contributors](https://img.shields.io/github/contributors/CatchNip/mcp-selenium-grid?label=Contributors)
[![License](https://img.shields.io/github/license/CatchNip/mcp-selenium-grid)](LICENSE)

A Model Context Protocol (MCP) server for managing Selenium Grid browser instances. Useful for browser automation and testing workflows.

The MCP Selenium Grid provides a MCP Server for creating and managing browser instances in both Docker and Kubernetes environments. It's designed to work with AI agents and automation tools that need browser automation capabilities.

## Key Features

- **Multi-browser support**: Chrome, Firefox and Edge
- **Dual backend support**: Docker and Kubernetes deployment modes
- **Secure API**: Token-based authentication for browser management
- **Scalable architecture**: Support for multiple browser instances
- **MCP compliance**: Follows Model Context Protocol standards

## 🚀 Quick Start

### Prerequisites

- [uv](https://github.com/astral-sh/uv) (Python dependency manager)
- [Docker](https://www.docker.com/) (for Docker deployment mode)
- [K3s](https://k3s.io/) (for Kubernetes deployment mode, optional)

### 📖 Usage

The MCP Selenium Grid provides a Web API for creating and managing browser instances. The server runs on `localhost:8000` and exposes MCP endpoints at `/mcp`.

### MCP Client Configuration

#### 🐳 Docker Deployment

For Docker-based deployment, ensure Docker is running and use the Docker configuration in your MCP client setup.

```json
{
  "mcpServers": {
    "mcp-selenium-grid": {
      "command": "uvx",
      "args": ["mcp-selenium-grid", "server", "run",
        "--host", "127.0.0.1",
        "--port", "8000",
      ],
      "env": {
        "API_TOKEN": "CHANGE_ME",
        "ALLOWED_ORIGINS": ["http://localhost:8000"],
        "DEPLOYMENT_MODE": "docker",
        "SELENIUM_GRID__USERNAME": "USER",
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

> The server will be available at `http://localhost:8000` with interactive API documentation at `http://localhost:8000/docs`.

#### ☸️ Kubernetes Deployment

##### 3. Kubernetes Setup (Optional)

This project supports Kubernetes deployment for scalable browser instance management. We use K3s for local development and testing.

###### Install K3s (<https://docs.k3s.io/quick-start>)

```bash
# Install K3s
curl -sfL https://get.k3s.io | sh -

# Verify installation
k3s --version

# Start if not running
sudo systemctl start k3s
```

###### Create K3s Kubernetes Context (Optional)

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

###### Deploy Selenium Grid

Using kubernetes context name from [config.yaml](./config.yaml):

```bash
uvx mcp-selenium-grid helm --help
uvx mcp-selenium-grid helm deploy
```

For a given kubernetes context name:

```bash
uvx mcp-selenium-grid helm deploy --context k3s-selenium-grid
```

Uninstall:

```bash
uvx mcp-selenium-grid helm uninstall --delete-namespace
uvx mcp-selenium-grid helm uninstall --context k3s-selenium-grid --delete-namespace
```

```json
{
  "mcpServers": {
    "mcp-selenium-grid": {
      "command": "uvx",
      "args": ["mcp-selenium-grid", "server", "run",
        "--host", "127.0.0.1",
        "--port", "8000",
      ],
      "env": {
        "API_TOKEN": "CHANGE_ME",
        "ALLOWED_ORIGINS": ["http://localhost:8000"],
        "DEPLOYMENT_MODE": "kubernetes",
        "SELENIUM_GRID__USERNAME": "USER",
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

```json
{
  "mcpServers": {
    "mcp-selenium-grid": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--init",
        "-p", "8000:80",
        "-e", "API_TOKEN=CHANGE_ME",
        "-e", "ALLOWED_ORIGINS=http://localhost:8000",
        "-e", "DEPLOYMENT_MODE=kubernetes", // required for docker
        "-e", "SELENIUM_GRID__USERNAME=USER",
        "-e", "SELENIUM_GRID__PASSWORD=CHANGE_ME",
        "-e", "SELENIUM_GRID__VNC_PASSWORD=CHANGE_ME",
        "-e", "SELENIUM_GRID__VNC_VIEW_ONLY=false",
        "-e", "SELENIUM_GRID__MAX_BROWSER_INSTANCES=4",
        "-e", "SELENIUM_GRID__SE_NODE_MAX_SESSIONS=1",
        "-e", "KUBERNETES__KUBECONFIG=/kube/config-local-k3s",
        "-e", "KUBERNETES__CONTEXT=k3s-selenium-grid",
        "-e", "KUBERNETES__NAMESPACE=selenium-grid-dev",
        "-e", "KUBERNETES__SELENIUM_GRID_SERVICE_NAME=selenium-grid",
        "ghcr.io/falamarcao/mcp-selenium-grid:latest",
      ]
    }
  }
}

```

> The server will be available at `http://localhost:8000` with interactive API documentation at `http://localhost:8000/docs`.

## 🤝 Contributing

For development setup, testing, and contribution guidelines, please see [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

MIT
