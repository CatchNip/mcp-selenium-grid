import logging
from typing import override

import docker
from docker.errors import APIError, NotFound

from ..models.browser import BrowserConfig, BrowserConfigs, BrowserType
from ..models.general_settings import SeleniumHubGeneralSettings
from .hub_backend import HubBackend


class DockerHubBackend(HubBackend):
    def __init__(self, settings: SeleniumHubGeneralSettings):
        self.client = docker.from_env()
        self.settings = settings

    @property
    @override
    def URL(self) -> str:
        """Base URL for the Docker Selenium Hub."""
        return f"http://localhost:{self.settings.selenium_grid.SELENIUM_HUB_PORT}"

    def _remove_container(self, container_name: str) -> None:
        """Helper method to remove a container by name."""
        try:
            logging.info(f"Attempting to remove container {container_name}.")
            container = self.client.containers.get(container_name)
            container.remove(force=True)
            logging.info(f"Removed container {container_name}.")
        except NotFound:
            logging.info(f"Container {container_name} not found for removal.")
        except APIError as e:
            logging.error(f"Docker API error removing container {container_name}: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error removing container {container_name}: {e}")

    def _remove_network(self, network_name: str) -> None:
        """Helper method to remove a network by name."""
        try:
            logging.info(f"Attempting to remove network {network_name}.")
            net = self.client.networks.get(network_name)
            net.remove()
            logging.info(f"Removed network {network_name}.")
        except NotFound:
            logging.info(f"Network {network_name} not found for removal.")
        except APIError as e:
            logging.error(f"Docker API error removing network {network_name}: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error removing network {network_name}: {e}")

    @override
    def cleanup_hub(self) -> None:
        """Clean up Selenium Hub container and network."""
        self._remove_container(self.settings.HUB_NAME)
        self._remove_network(self.settings.docker.DOCKER_NETWORK_NAME)

    @override
    def cleanup_browsers(self) -> None:
        """Clean up all browser containers."""
        try:
            # Get all containers with the selenium-node label
            containers = self.client.containers.list(filters={"label": self.settings.NODE_LABEL})
            for container in containers:
                self._remove_container(container.name)
        except APIError as e:
            logging.error(f"Docker API error listing browser containers: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error cleaning up browser containers: {e}")

    @override
    def cleanup(self) -> None:
        """Clean up all resources by first cleaning up browsers then the hub."""
        super().cleanup()

    async def ensure_hub_running(self) -> bool:
        """Ensure the Selenium Grid network and Hub container are running."""

        # Ensure network exists
        try:
            self.client.networks.get(self.settings.docker.DOCKER_NETWORK_NAME)
            logging.info(
                f"Docker network '{self.settings.docker.DOCKER_NETWORK_NAME}' already exists."
            )
        except NotFound:
            logging.info(
                f"Docker network '{self.settings.docker.DOCKER_NETWORK_NAME}' not found, creating."
            )
            self.client.networks.create(self.settings.docker.DOCKER_NETWORK_NAME, driver="bridge")
            logging.info(f"Docker network '{self.settings.docker.DOCKER_NETWORK_NAME}' created.")
        except APIError as e:
            logging.error(
                f"Docker API error ensuring network '{self.settings.docker.DOCKER_NETWORK_NAME}': {e}"
            )
            return False
        except Exception as e:
            logging.exception(
                f"Unexpected error ensuring network '{self.settings.docker.DOCKER_NETWORK_NAME}': {e}"
            )
            return False

        # Ensure Hub container is running
        try:
            hub = self.client.containers.get(self.settings.HUB_NAME)
            if hub.status != "running":
                logging.info(
                    f"{self.settings.HUB_NAME} container found but not running, restarting."
                )
                hub.restart()
                logging.info(f"{self.settings.HUB_NAME} container restarted.")
            else:
                logging.info(f"{self.settings.HUB_NAME} container is already running.")
        except NotFound:
            logging.info(f"{self.settings.HUB_NAME} container not found, creating.")
            self.client.containers.run(
                self.settings.selenium_grid.HUB_IMAGE,
                name=self.settings.HUB_NAME,
                detach=True,
                network=self.settings.docker.DOCKER_NETWORK_NAME,
                ports={
                    f"{self.settings.selenium_grid.SELENIUM_HUB_PORT}/tcp": self.settings.selenium_grid.SELENIUM_HUB_PORT
                },
                environment={
                    "SE_EVENT_BUS_HOST": self.settings.HUB_NAME,
                    "SE_EVENT_BUS_PUBLISH_PORT": "4442",
                    "SE_EVENT_BUS_SUBSCRIBE_PORT": "4443",
                    "SE_NODE_MAX_SESSIONS": str(self.settings.selenium_grid.SE_NODE_MAX_SESSIONS),
                    "SE_NODE_OVERRIDE_MAX_SESSIONS": "true",
                    "SE_VNC_NO_PASSWORD": self.settings.selenium_grid.SE_VNC_NO_PASSWORD_STR,
                    "SE_VNC_PASSWORD": str(
                        self.settings.selenium_grid.VNC_PASSWORD.get_secret_value()
                    ),
                    "SE_VNC_VIEW_ONLY": str(self.settings.selenium_grid.VNC_VIEW_ONLY_STR),
                    "SE_OPTS": f"--username {self.settings.selenium_grid.USER.get_secret_value()} \
                        --password {self.settings.selenium_grid.PASSWORD.get_secret_value()}",
                },
                mem_limit="256M",
                cpu_quota=int(0.5 * 100000),  # Convert to microseconds
                cpu_period=100000,  # 100ms period
            )
            logging.info(f"{self.settings.HUB_NAME} container created and started.")
        except APIError as e:
            logging.error(f"Docker API error ensuring {self.settings.HUB_NAME} container: {e}")
            return False
        except Exception as e:
            logging.exception(f"Unexpected error ensuring {self.settings.HUB_NAME} container: {e}")
            return False

        return True

    @override
    async def create_browsers(
        self,
        count: int,
        browser_type: BrowserType,
        browser_configs: BrowserConfigs,
    ) -> list[str]:
        """Create the requested number of Selenium browser containers."""
        config: BrowserConfig = browser_configs[browser_type]
        browser_ids: list[str] = []
        for _ in range(count):
            # Ensure image exists, pull if necessary
            try:
                self.client.images.get(config.image)
                logging.info(f"Docker image {config.image} already exists.")
            except NotFound:
                logging.info(f"Docker image {config.image} not found, pulling.")
                self.client.images.pull(config.image)
                logging.info(f"Docker image {config.image} pulled.")
            except APIError as e:
                logging.error(f"Docker API error ensuring image {config.image}: {e}")
                continue
            except Exception as e:
                logging.exception(f"Unexpected error ensuring image {config.image}: {e}")
                continue

            # Create and run container
            try:
                logging.info(f"Creating container for browser type {browser_type}.")
                container = self.client.containers.run(
                    config.image,
                    detach=True,
                    network=self.settings.docker.DOCKER_NETWORK_NAME,
                    labels={
                        self.settings.NODE_LABEL: "true",
                        self.settings.BROWSER_LABEL: str(browser_type),
                    },
                    environment={
                        "SE_EVENT_BUS_HOST": self.settings.HUB_NAME,
                        "SE_PORT": str(self.settings.selenium_grid.SELENIUM_HUB_PORT),
                        "SE_EVENT_BUS_PUBLISH_PORT": "4442",
                        "SE_EVENT_BUS_SUBSCRIBE_PORT": "4443",
                        "SE_NODE_MAX_SESSIONS": str(
                            self.settings.selenium_grid.SE_NODE_MAX_SESSIONS
                        ),
                        "SE_OPTS": f"--username {self.settings.selenium_grid.USER.get_secret_value()} \
                        --password {self.settings.selenium_grid.PASSWORD.get_secret_value()}",
                    },
                    mem_limit=config.resources.memory,
                    cpu_quota=int(float(config.resources.cpu) * 100000),  # Convert to microseconds
                    cpu_period=100000,  # 100ms period
                )
                cid = getattr(container, "id", None)
                if not cid:
                    logging.error("Failed to start browser container or retrieve container ID.")
                    continue
                browser_ids.append(cid[:12])
                logging.info(f"Created container with ID: {cid[:12]}")
            except APIError as e:
                logging.error(f"Docker API error creating container for {browser_type}: {e}")
                continue
            except Exception as e:
                logging.exception(f"Unexpected error creating container for {browser_type}: {e}")
                continue

        return browser_ids

    @override
    async def delete_browser(self, browser_id: str) -> bool:
        """Delete a specific browser instance by container ID (Docker). Returns True if deleted, False otherwise."""
        try:
            container = self.client.containers.get(browser_id)
            container.remove(force=True)
            return True
        except Exception:
            return False
