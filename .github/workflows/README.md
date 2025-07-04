# 🚀 Local GitHub Actions Testing with act

## 📂 Workflow Overview

This repository uses modular, clearly named workflows for CI, integration tests, packaging, Docker, and releases.

1. 🧪 **Continuous Integration** — Unit tests, lint, and type checks
1.2. 🔬 **Integration & E2E Tests** — Resource intensive, needs Docker & Kubernetes
2. 🚀 **Full Release Workflow** — Builds and publishes both the Python package and Docker image, then creates a GitHub Release
2.1. 📦 **Build & Publish Python Package** — Build and (optionally) publish the Python package
2.2. 🐋 **Build & Push Docker Image** — Build and (optionally) push the Docker image
2.3. 📝 **Create GitHub Release Only** — Create a GitHub Release from already published artifacts

## ⚡ Quick Start

1. 🛠️ **Install [act](https://github.com/nektos/act):**

    ```sh
    brew install act
    ```

    Or, for any system:

    ```sh
    curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
    ```

    👉 For more install options, see: <https://nektosact.com/installation/index.html>

## 🐳 Docker Image for act

```sh
docker pull catthehacker/ubuntu:act-latest
```

## 1. 🧪 Continuous Integration

Run all CI checks (unit tests, lint, type checks):

```sh
act -W .github/workflows/1_ci.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

## 1.2. 🔬 Integration & E2E Tests

Run integration and E2E tests (resource intensive, needs Docker & Kubernetes):

```sh
act workflow_dispatch -W .github/workflows/1.2_integration-e2e-tests.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

## 2. 🚀 Full Release Workflow

Builds and publishes both the Python package and Docker image, then creates a GitHub Release:

```sh
act workflow_dispatch -W .github/workflows/2_release.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

## 2.1. 📦 Build & Publish Python Package

Build and (optionally) publish the Python package:

```sh
act -W .github/workflows/2.1_build-python-package.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

## 2.2. 🐋 Build & Push Docker Image

Build and (optionally) push the Docker image:

```sh
act -W .github/workflows/2.2_build-docker-image.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

## 2.3. 📝 Create GitHub Release Only

Create a GitHub Release from already published artifacts:

```sh
act -W .github/workflows/2.3_create-github-release.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

## 💡 Notes

- 🐳 You need Docker running.
- 🐍 Use the same Python version as in `.python-version` for best results.
- 🧩 Each workflow is modular and can be rerun independently for robust, atomic releases.
- 🏷️ The main release workflow only creates a GitHub Release if both the Python package and Docker image are published successfully.

That's it. 😎✨ 