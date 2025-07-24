import os
import textwrap
from pathlib import Path

import pytest
from app.core.settings import Settings
from app.services.selenium_hub.models import DeploymentMode

MAX_BROWSER_INSTANCES = 100
SELENIUM_PORT = 4444


@pytest.mark.unit
def test_settings_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_NAME", "Env Project")
    monkeypatch.setenv("VERSION", "3.0.0")
    monkeypatch.setenv("API_V1_STR", "/env/api")
    settings = Settings()
    assert settings.PROJECT_NAME == "Env Project"
    assert settings.VERSION == "3.0.0"
    assert settings.API_V1_STR == "/env/api"


@pytest.mark.unit
def test_deployment_mode_override_by_constructor(tmp_path: Path) -> None:
    # Change working directory to tmp_path so config.yaml is not found
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        settings = Settings(DEPLOYMENT_MODE=DeploymentMode.KUBERNETES)
        assert settings.DEPLOYMENT_MODE == DeploymentMode.KUBERNETES
    finally:
        os.chdir(old_cwd)


@pytest.mark.unit
def test_deployment_mode_override_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_MODE", "kubernetes")
    settings = Settings()
    assert settings.DEPLOYMENT_MODE == DeploymentMode.KUBERNETES
    monkeypatch.delenv("DEPLOYMENT_MODE", raising=False)


# --- YAML Loading and Special Behaviors ---
@pytest.mark.unit
def test_settings_loads_from_yaml(tmp_path: Path) -> None:
    yaml_content = textwrap.dedent(f"""
        project_name: YAML Project
        version: 9.9.9
        selenium_grid:
          max_browser_instances: {MAX_BROWSER_INSTANCES}
          browser_configs:
            chrome:
                image: selenium/node-chrome:4.18.1
                port: 4444
                resources:
                    memory: "512M"
                    cpu: "0.5"
        kubernetes:
          namespace: yaml-namespace
          kubeconfig: ~/fake-kubeconfig
    """)
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        f.write(yaml_content)
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        settings = Settings()
        assert settings.PROJECT_NAME == "YAML Project"
        assert settings.VERSION == "9.9.9"
        assert settings.selenium_grid.MAX_BROWSER_INSTANCES == MAX_BROWSER_INSTANCES
        assert settings.kubernetes.NAMESPACE == "yaml-namespace"
        expected_kubeconfig = os.path.expanduser("~/fake-kubeconfig")
        assert settings.kubernetes.KUBECONFIG == expected_kubeconfig
        # Verify browser configs
        assert "chrome" in settings.selenium_grid.BROWSER_CONFIGS
        chrome_config = settings.selenium_grid.BROWSER_CONFIGS["chrome"]
        assert chrome_config.image == "selenium/node-chrome:4.18.1"
        assert chrome_config.port == SELENIUM_PORT
        assert chrome_config.resources.memory == "512M"
        assert chrome_config.resources.cpu == "0.5"
    finally:
        os.chdir(old_cwd)


@pytest.mark.unit
def test_env_nested_delimiter_for_all_nested_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SELENIUM_GRID__MAX_BROWSER_INSTANCES", str(MAX_BROWSER_INSTANCES))
    monkeypatch.setenv("KUBERNETES__NAMESPACE", "env-namespace")
    monkeypatch.setenv("KUBERNETES__KUBECONFIG", "/env/kubeconfig")
    monkeypatch.setenv("DOCKER__DOCKER_NETWORK_NAME", "env-docker-net")
    settings = Settings()
    assert settings.selenium_grid.MAX_BROWSER_INSTANCES == MAX_BROWSER_INSTANCES
    assert settings.kubernetes.NAMESPACE == "env-namespace"
    assert settings.kubernetes.KUBECONFIG == "/env/kubeconfig"
    assert settings.docker.DOCKER_NETWORK_NAME == "env-docker-net"
