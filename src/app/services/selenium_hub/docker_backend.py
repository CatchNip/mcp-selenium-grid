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

    def cleanup(self) -> None:
        """Clean up Selenium Hub container and network."""
        # Remove selenium-hub container
        try:
            logging.info("Attempting to remove selenium-hub container.")
            hub_container = self.client.containers.get("selenium-hub")
            hub_container.remove(force=True)
            logging.info("Removed selenium-hub container.")
        except NotFound:
            logging.info("Selenium-hub container not found for removal.")
        except APIError as e:
            logging.error(f"Docker API error removing selenium-hub container: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error removing selenium-hub container: {e}")

        # Remove selenium-grid network
        try:
            logging.info("Attempting to remove selenium-grid network.")
            net = self.client.networks.get("selenium-grid")
            net.remove()
            logging.info("Removed selenium-grid network.")
        except NotFound:
            logging.info("Selenium-grid network not found for removal.")
        except APIError as e:
            logging.error(f"Docker API error removing selenium-grid network: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error removing selenium-grid network: {e}")

    async def ensure_hub_running(self) -> bool:
        """Ensure the Selenium Grid network and Hub container are running."""

        # Ensure network exists
        try:
            self.client.networks.get("selenium-grid")
            logging.info("Docker network 'selenium-grid' already exists.")
        except NotFound:
            logging.info("Docker network 'selenium-grid' not found, creating.")
            self.client.networks.create("selenium-grid", driver="bridge")
            logging.info("Docker network 'selenium-grid' created.")
        except APIError as e:
            logging.error(f"Docker API error ensuring network 'selenium-grid': {e}")
            return False
        except Exception as e:
            logging.exception(f"Unexpected error ensuring network 'selenium-grid': {e}")
            return False

        # Ensure Hub container is running
        try:
            hub = self.client.containers.get("selenium-hub")
            if hub.status != "running":
                logging.info("Selenium-hub container found but not running, restarting.")
                hub.restart()
                logging.info("Selenium-hub container restarted.")
            else:
                logging.info("Selenium-hub container is already running.")
        except NotFound:
            logging.info("Selenium-hub container not found, creating.")
            self.client.containers.run(
                "selenium/hub:4.18.1",
                name="selenium-hub",
                detach=True,
                network="selenium-grid",
                ports={f"{self.settings.SELENIUM_HUB_PORT}/tcp": self.settings.SELENIUM_HUB_PORT},
                environment={
                    "SE_EVENT_BUS_HOST": "selenium-hub",
                    "SE_EVENT_BUS_PUBLISH_PORT": "4442",
                    "SE_EVENT_BUS_SUBSCRIBE_PORT": "4443",
                    "SE_NODE_MAX_SESSIONS": str(self.settings.MAX_BROWSER_INSTANCES or 10),
                    "SE_NODE_OVERRIDE_MAX_SESSIONS": "true",
                    "SE_VNC_NO_PASSWORD": "true",
                    "SE_OPTS": f"--username {self.settings.SELENIUM_HUB_USER} \
                        --password {self.settings.SELENIUM_HUB_PASSWORD}",
                },
            )
            logging.info("Selenium-hub container created and started.")
        except APIError as e:
            logging.error(f"Docker API error ensuring selenium-hub container: {e}")
            return False
        except Exception as e:
            logging.exception(f"Unexpected error ensuring selenium-hub container: {e}")
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
                # Depending on requirements, might raise or skip this browser
                continue  # Skip this browser creation on image error
            except Exception as e:
                logging.exception(f"Unexpected error ensuring image {config.image}: {e}")
                continue  # Skip this browser creation on unexpected error

            # Create and run container
            try:
                logging.info(f"Creating container for browser type {browser_type}.")
                container = self.client.containers.run(
                    config.image,
                    detach=True,
                    network="selenium-grid",
                    environment={
                        "SE_EVENT_BUS_HOST": "selenium-hub",
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
                    cpu_count=int(config.resources.cpu),  # Convert cpu to int
                )
                cid = getattr(container, "id", None)
                if not cid:
                    logging.error("Failed to start browser container or retrieve container ID.")
                    continue  # Skip if container start failed
                browser_ids.append(cid[:12])
                logging.info(f"Created container with ID: {cid[:12]}")
            except APIError as e:
                logging.error(f"Docker API error creating container for {browser_type}: {e}")
                continue  # Skip this browser creation on API error
            except Exception as e:
                logging.exception(f"Unexpected error creating container for {browser_type}: {e}")
                continue  # Skip this browser creation on unexpected error

        return browser_ids

    async def delete_browser(self, browser_id: str) -> bool:
        """Delete a specific browser instance by container ID (Docker). Returns True if deleted, False otherwise."""
        try:
            container = self.client.containers.get(browser_id)
            container.remove(force=True)
            return True
        except Exception:
            return False
