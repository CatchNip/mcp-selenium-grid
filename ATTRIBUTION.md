# Attribution

This document lists the third-party dependencies, tools, and components used in the MCP Selenium Grid project, along with their respective licenses and attribution information.

## Project Information

- **Project Name**: MCP Selenium Grid
- **Author**: [Marco (falamarcao)](https://github.com/Falamarcao)
- **License**: MIT License
- **Repository**: [mcp-selenium-grid](https://github.com/Falamarcao/mcp-selenium-grid)

## Core Dependencies

### Python Dependencies

#### FastAPI Ecosystem

- **fastapi[standard]>=0.115.14** - [MIT License](https://github.com/tiangolo/fastapi/blob/master/LICENSE)

  - Fast web framework for building APIs with Python
  - Created by Sebastián Ramírez (tiangolo)

- **fastapi-mcp>=0.3.4** - [MIT License](https://github.com/jlowin/fastapi-mcp/blob/main/LICENSE)
  - Model Context Protocol integration for FastAPI
  - Created by jlowin

#### Data Validation & Settings

- **pydantic[email]>=2.11.7** - [MIT License](https://github.com/pydantic/pydantic/blob/main/LICENSE)

  - Data validation using Python type annotations
  - Created by the Pydantic team

- **pydantic-settings>=2.10.1** - [MIT License](https://github.com/pydantic/pydantic-settings/blob/main/LICENSE)
  - Settings management using Pydantic
  - Created by the Pydantic team

#### Container & Orchestration

- **docker>=7.1.0** - [Apache License 2.0](https://github.com/docker/docker-py/blob/main/LICENSE)

  - Docker API client for Python
  - Created by the Docker team

- **kubernetes>=33.1.0** - [Apache License 2.0](https://github.com/kubernetes-client/python/blob/master/LICENSE)
  - Kubernetes API client for Python
  - Created by the Kubernetes team

#### Monitoring & Metrics

- **prometheus-client>=0.22.1** - [Apache License 2.0](https://github.com/prometheus/client_python/blob/master/LICENSE)

  - Prometheus client library for Python
  - Created by the Prometheus team

- **prometheus-fastapi-instrumentator>=7.1.0** - [MIT License](https://github.com/trallnag/prometheus-fastapi-instrumentator/blob/main/LICENSE)
  - Prometheus metrics for FastAPI applications
  - Created by trallnag

#### HTTP & System Utilities

- **httpx>=0.28.1** - [BSD License](https://github.com/encode/httpx/blob/master/LICENSE.md)

  - HTTP client for Python
  - Created by the Encode team

- **psutil>=7.0.0** - [BSD License](https://github.com/giampaolo/psutil/blob/master/LICENSE)
  - Cross-platform library for retrieving information on running processes and system utilization
  - Created by Giampaolo Rodola

## Development Dependencies

### Code Quality & Testing

- **ruff>=0.12.2** - [MIT License](https://github.com/astral-sh/ruff/blob/main/LICENSE)

  - Fast Python linter and formatter
  - Created by Astral Software

- **mypy>=1.16.1** - [MIT License](https://github.com/python/mypy/blob/master/LICENSE)

  - Static type checker for Python
  - Created by the mypy team

- **pre-commit>=4.2.0** - [MIT License](https://github.com/pre-commit/pre-commit/blob/main/LICENSE)
  - Framework for managing and maintaining pre-commit hooks
  - Created by the pre-commit team

### Type Stubs

- **types-docker>=7.1.0.20250523** - [Apache License 2.0](https://github.com/python/typeshed/blob/main/LICENSE)

  - Type stubs for docker package
  - Part of typeshed project

- **types-pyyaml>=6.0.12.20250516** - [MIT License](https://github.com/python/typeshed/blob/main/LICENSE)

  - Type stubs for PyYAML package
  - Part of typeshed project

- **kubernetes-stubs-elephant-fork>=33.1.0** - [Apache License 2.0](https://github.com/kubernetes-client/python/blob/master/LICENSE)

  - Type stubs for kubernetes package
  - Fork of official Kubernetes Python client stubs

- **types-psutil>=7.0.0.20250601** - [BSD License](https://github.com/python/typeshed/blob/main/LICENSE)
  - Type stubs for psutil package
  - Part of typeshed project

### CLI Framework

- **typer>=0.16.0** - [MIT License](https://github.com/tiangolo/typer/blob/master/LICENSE)
  - Library for building CLI applications
  - Created by Sebastián Ramírez (tiangolo)

### Testing Framework

- **pytest>=8.4.1** - [MIT License](https://github.com/pytest-dev/pytest/blob/main/LICENSE)

  - Testing framework for Python
  - Created by the pytest team

- **pytest-mock>=3.14.1** - [MIT License](https://github.com/pytest-dev/pytest-mock/blob/main/LICENSE)

  - Mocking plugin for pytest
  - Created by the pytest team

- **pytest-asyncio>=1.0.0** - [Apache License 2.0](https://github.com/pytest-dev/pytest-asyncio/blob/main/LICENSE)

  - Asyncio support for pytest
  - Created by the pytest team

- **coverage[toml]>=7.9.2** - [Apache License 2.0](https://github.com/nedbat/coveragepy/blob/master/LICENSE.txt)

  - Code coverage measurement for Python
  - Created by Ned Batchelder

- **pytest-sugar>=1.0.0** - [MIT License](https://github.com/Frozenball/pytest-sugar/blob/master/LICENSE)
  - Plugin that changes the default look and feel of pytest
  - Created by Frozenball

## Build System & Tools

### Dependency Management

- **uv** - [MIT License](https://github.com/astral-sh/uv/blob/main/LICENSE)
  - Fast Python package installer and resolver
  - Created by Astral Software

### Build Backend

- **hatchling** - [MIT License](https://github.com/pypa/hatch/blob/main/LICENSE.txt)
  - Modern, extensible Python project manager
  - Created by the Python Packaging Authority (PyPA)

## Container & Infrastructure

### Base Images

- **python:3.13-slim-bullseye** - [Python Software Foundation License](https://github.com/python/cpython/blob/main/LICENSE)
  - Official Python Docker image
  - Maintained by the Python Software Foundation

### Container Tools

- **Docker** - [Apache License 2.0](https://github.com/docker/docker-ce/blob/master/LICENSE)
  - Container platform
  - Created by Docker Inc.

### Kubernetes & Helm

- **Kubernetes** - [Apache License 2.0](https://github.com/kubernetes/kubernetes/blob/master/LICENSE)

  - Container orchestration platform
  - Created by the Cloud Native Computing Foundation (CNCF)

- **Helm** - [Apache License 2.0](https://github.com/helm/helm/blob/main/LICENSE)

  - Kubernetes package manager
  - Created by the Cloud Native Computing Foundation (CNCF)

- **K3s** - [Apache License 2.0](https://github.com/k3s-io/k3s/blob/master/LICENSE)
  - Lightweight Kubernetes distribution
  - Created by Rancher Labs

## External Services & APIs

### Selenium

- **Selenium Grid** - [Apache License 2.0](https://github.com/SeleniumHQ/selenium/blob/trunk/LICENSE)
  - Browser automation framework
  - Created by the Selenium team

### Model Context Protocol (MCP)

- **MCP Specification** - [Apache License 2.0](https://github.com/modelcontextprotocol/specification/blob/main/LICENSE)
  - Protocol for AI model context management
  - Created by the Model Context Protocol team

## Fonts & Icons

This project uses standard system fonts and does not include any custom fonts or icon libraries that require attribution.

## License Summary

All dependencies used in this project are licensed under open source licenses:

- **MIT License**: Most Python packages and tools
- **Apache License 2.0**: Kubernetes ecosystem, Docker, Selenium
- **BSD License**: httpx, psutil, and related type stubs

## Additional Notes

- All dependencies are managed through `uv` and specified in `pyproject.toml`
- The project follows the Model Context Protocol (MCP) specification
- Docker images are based on official Python images
- No proprietary or commercial dependencies are included

For questions about specific licenses or attributions, please refer to the individual project repositories listed above.

## Citing This Project

If you use this project in your work, research, or other projects, please include the following attribution:

### Academic Citation

```bibtex
@software{mcp_selenium_grid,
  title = {MCP Selenium Grid: A Model Context Protocol Server for Browser Automation},
  author = {Marco (falamarcao)},
  year = {2025},
  url = {https://github.com/Falamarcao/mcp-selenium-grid},
  license = {MIT},
  note = {A REST API server for managing Selenium browser instances through MCP}
}
```

### Software Attribution

```markdown
## Dependencies

This project uses the following third-party components:

- **MCP Selenium Grid** - [MIT License](https://github.com/Falamarcao/mcp-selenium-grid/blob/main/LICENSE)
  - Model Context Protocol server for managing Selenium Grid.
  - Created by [Marco (falamarcao)](https://github.com/Falamarcao)
```

### Code Comments

```python
# This module uses MCP Selenium Grid
# https://github.com/Falamarcao/mcp-selenium-grid
# MIT License - Copyright (c) 2025 Marco (falamarcao)
```

### requirements.txt (for Python projects)

```txt
# MCP Selenium Grid - MIT License
# https://github.com/Falamarcao/mcp-selenium-grid
git+https://github.com/Falamarcao/mcp-selenium-grid.git
```

### Dockerfile

```dockerfile
# Uses MCP Selenium Grid - MIT License
# https://github.com/Falamarcao/mcp-selenium-grid
FROM ghcr.io/falamarcao/mcp-selenium-grid:latest
```

### License Compliance

When using this project, ensure you comply with the MIT License requirements:

- Include the original copyright notice
- Include the MIT License text
- State any changes made to the software

For more information about the MIT License, see: https://opensource.org/licenses/MIT

---

## Disclaimer

**⚠️ Auto-Generated Document**

This ATTRIBUTION.md file was automatically generated using AI assistance. While every effort has been made to ensure accuracy, the information contained herein should be verified against the original source repositories and documentation.

**Important Notes:**

- License information and attribution details should be cross-referenced with the official repositories
- Version numbers and dependency information may need to be updated as the project evolves
- Please verify all links and license URLs are current and accessible
- Contact the original authors or maintainers for the most up-to-date information

**Last Updated:** This document was generated on the current date and may require periodic review and updates.
