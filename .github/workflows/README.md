# 🚀 Local GitHub Actions Testing with act

## 📂 Workflow Overview

This repository uses modular, clearly named workflows for CI, integration tests, packaging, Docker, and releases.
A top-level **`0_ci-cd.yaml`** orchestrates the process for pushes to `main`, running **Tests** first and triggering the **Release** workflow only if they pass.

1. 🧪 **Tests** — lint, types checks, unit, integration and e2e tests.
   - 🧩 **Unit Tests** — Run unit tests
   - 🐳 **Docker Integration & E2E Tests** — Run Docker integration and end-to-end tests
   - ☸️ **Kubernetes Integration & E2E Tests** — Run Kubernetes integration and end-to-end tests
2. 🚀 **Full Release Workflow** — Builds and publishes both the Python package and Docker image, then creates a GitHub Release
   - 📦 **Build & Publish Python Package** — Build and (optionally) publish the Python package
   - 🐋 **Build & Push Docker Image** — Build and (optionally) push the Docker image
   - 📝 **Create GitHub Release Only** — Create a GitHub Release from already published artifacts
3. 🔄 **CI/CD Orchestration** (`3_ci-cd.yaml`) — Runs Tests → Release when pushing to `main`.

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

    > _Warning: act is not always realiable_.

## 🐳 Docker Image for act

```sh
docker pull catthehacker/ubuntu:act-latest
```

## 1. 🧪 Tests

Run all CI checks (lint, types checks, unit, integration and e2e tests):

```sh
act -W .github/workflows/1_tests.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

### 1.1. 🧩 Unit Tests

Run unit tests:

```sh
act -W .github/workflows/1.2_unit_tests.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

### 1.2. 🐳 Docker Integration & E2E Tests

Run Docker integration and end-to-end tests:

```sh
act -W .github/workflows/1.3_docker_tests.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

### 1.3. ☸️ Kubernetes Integration & E2E Tests

Run Kubernetes integration and end-to-end tests:

```sh
act -W .github/workflows/1.4_kubernetes_tests.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
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

## 3. 🔄 CI/CD Orchestration

Run the combined CI + Release process (push to main simulation):

```sh
act -W .github/workflows/3_ci-cd.yaml -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

## 💡 Notes

- 🐳 You need Docker running.
- 🐍 Use the same Python version as in `.python-version` for best results.
- 🧩 Each workflow is modular and can be rerun independently for robust, atomic releases.
- 🏷️ The main release workflow only creates a GitHub Release if both the Python package and Docker image are published successfully.

That's it. 😎✨ 