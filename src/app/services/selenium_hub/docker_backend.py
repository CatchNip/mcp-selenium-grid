import logging
from typing import Dict, List

import docker
from docker.errors import APIError, NotFound

from app.core.models import BrowserConfig
from app.core.settings import Settings

from .backend import HubBackend


class DockerHubBackend(HubBackend):
    def __init__(self, settings: Settings):
        self.client = docker.from_env()
        self.settings = settings

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

    def cleanup_hub(self) -> None:
        """Clean up Selenium Hub container and network."""
        self._remove_container(self.HUB_NAME)
        self._remove_network(self.NETWORK_NAME)

    def cleanup_browsers(self) -> None:
        """Clean up all browser containers."""
        try:
            # Get all containers with the selenium-node label
            containers = self.client.containers.list(filters={"label": self.NODE_LABEL})
            for container in containers:
                self._remove_container(container.name)
        except APIError as e:
            logging.error(f"Docker API error listing browser containers: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error cleaning up browser containers: {e}")

    def cleanup(self) -> None:
        """Clean up all resources by first cleaning up browsers then the hub."""
        super().cleanup()

    async def ensure_hub_running(self) -> bool:
        """Ensure the Selenium Grid network and Hub container are running."""

        # Ensure network exists
        try:
            self.client.networks.get(self.NETWORK_NAME)
            logging.info(f"Docker network '{self.NETWORK_NAME}' already exists.")
        except NotFound:
            logging.info(f"Docker network '{self.NETWORK_NAME}' not found, creating.")
            self.client.networks.create(self.NETWORK_NAME, driver="bridge")
            logging.info(f"Docker network '{self.NETWORK_NAME}' created.")
        except APIError as e:
            logging.error(f"Docker API error ensuring network '{self.NETWORK_NAME}': {e}")
            return False
        except Exception as e:
            logging.exception(f"Unexpected error ensuring network '{self.NETWORK_NAME}': {e}")
            return False

        # Ensure Hub container is running
        try:
            hub = self.client.containers.get(self.HUB_NAME)
            if hub.status != "running":
                logging.info(f"{self.HUB_NAME} container found but not running, restarting.")
                hub.restart()
                logging.info(f"{self.HUB_NAME} container restarted.")
            else:
                logging.info(f"{self.HUB_NAME} container is already running.")
        except NotFound:
            logging.info(f"{self.HUB_NAME} container not found, creating.")
            self.client.containers.run(
                "selenium/hub:4.18.1",
                name=self.HUB_NAME,
                detach=True,
                network=self.NETWORK_NAME,
                ports={f"{self.settings.SELENIUM_HUB_PORT}/tcp": self.settings.SELENIUM_HUB_PORT},
                environment={
                    "SE_EVENT_BUS_HOST": self.HUB_NAME,
                    "SE_EVENT_BUS_PUBLISH_PORT": "4442",
                    "SE_EVENT_BUS_SUBSCRIBE_PORT": "4443",
                    "SE_NODE_MAX_SESSIONS": str(self.settings.MAX_BROWSER_INSTANCES or 10),
                    "SE_NODE_OVERRIDE_MAX_SESSIONS": "true",
                    "SE_VNC_NO_PASSWORD": "true",
                    "SE_OPTS": f"--username {self.settings.SELENIUM_HUB_USER} \
                        --password {self.settings.SELENIUM_HUB_PASSWORD}",
                },
            )
            logging.info(f"{self.HUB_NAME} container created and started.")
        except APIError as e:
            logging.error(f"Docker API error ensuring {self.HUB_NAME} container: {e}")
            return False
        except Exception as e:
            logging.exception(f"Unexpected error ensuring {self.HUB_NAME} container: {e}")
            return False

        return True

    async def create_browsers(
        self, count: int, browser_type: str, browser_configs: Dict[str, BrowserConfig]
    ) -> List[str]:
        """Create the requested number of Selenium browser containers."""
        config: BrowserConfig = browser_configs[browser_type]
        browser_ids: List[str] = []
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
                    network=self.NETWORK_NAME,
                    labels={self.NODE_LABEL: "true", self.BROWSER_LABEL: browser_type},
                    environment={
                        "SE_EVENT_BUS_HOST": self.HUB_NAME,
                        "SE_EVENT_BUS_PUBLISH_PORT": "4442",
                        "SE_EVENT_BUS_SUBSCRIBE_PORT": "4443",
                        "SE_NODE_MAX_SESSIONS": str(self.settings.SE_NODE_MAX_SESSIONS or 1),
                        "SE_HUB_USER": getattr(self.settings, "SELENIUM_HUB_USER", None)
                        or getattr(self.settings, "selenium_hub_user", None)
                        or "user",
                        "SE_HUB_PASSWORD": getattr(self.settings, "SELENIUM_HUB_PASSWORD", None)
                        or getattr(self.settings, "selenium_hub_password", None)
                        or "CHANGE_ME",
                    },
                    mem_limit=config.resources.memory,
                    cpu_count=int(config.resources.cpu),
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

    async def delete_browser(self, browser_id: str) -> bool:
        """Delete a specific browser instance by container ID (Docker). Returns True if deleted, False otherwise."""
        try:
            container = self.client.containers.get(browser_id)
            container.remove(force=True)
            return True
        except Exception:
            return False
