# 🚀 Local GitHub Actions Testing with act

## ⚡ Quick Start

1. 🛠️ **Install [act](https://github.com/nektos/act):**

    ```sh
    brew install act
    ```

    You can easily install a pre-built act executable on any system with bash via below commandline

    ```sh
    curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
    ```

    ⚠️ Script can't install non-released versions ⚠️

    👉 For more installation options (Windows, Linux, Mac, package managers, manual download), see the official docs: <https://nektosact.com/installation/index.html>

## 🧪 Run Workflows Locally

### 🐳 Pull Docker image

```sh
docker pull catthehacker/ubuntu:act-latest
```

### 🏃 CI Workflow

Run all workflows:

```sh
act -P ubuntu-latest=catthehacker/ubuntu:act-latest --rm
```

Run the main CI workflow (unit tests, mypy, ruff):

```sh
act -W .github/workflows/ci.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest  --rm
```

### 🔬 Manual Integration & E2E Workflow

Run the manual integration and E2E tests (resource intensive, depends on Docker and Kubernetes):

```sh
act workflow_dispatch -W .github/workflows/manual-integration-e2e.yml  -P ubuntu-latest=catthehacker/ubuntu:act-latest  --rm
```

### 📦 Release Workflows

- `release.yml` runs both the Python package build and Docker image build workflows.
- You can run them individually or together:

**Run the release workflow (builds both):**

```sh
act workflow_dispatch -W .github/workflows/release.yml  -P ubuntu-latest=catthehacker/ubuntu:act-latest  --rm
```

**Run just the Python package build:**

```sh
act -W .github/workflows/build-python-package.yml  -P ubuntu-latest=catthehacker/ubuntu:act-latest  --rm
```

**Run just the Docker image build:**

```sh
act -W .github/workflows/build-docker-image.yml  -P ubuntu-latest=catthehacker/ubuntu:act-latest  --rm
```

## 💡 Notes

- 🐳 You need Docker running.
- 🐍 Use the same Python version as in `.python-version` for best results.
- 🧩 For matrix jobs, act will run each matrix entry as a separate job.

That's it. 😎✨ 