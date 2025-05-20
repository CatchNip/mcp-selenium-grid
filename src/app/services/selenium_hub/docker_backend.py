import logging

import docker

from .backend import HubBackend


class DockerHubBackend(HubBackend):
    def __init__(self, settings):
        self.client = docker.from_env()
        self.settings = settings

    def cleanup(self) -> None:
        try:
            hub_container = self.client.containers.get("selenium-hub")
            hub_container.remove(force=True)
        except Exception:
            logging.exception("Exception occurred while removing selenium-hub container")
        try:
            net = self.client.networks.get("selenium-grid")
            net.remove()
        except Exception:
            logging.exception("Exception occurred while removing selenium-grid network")

    async def ensure_hub_running(self, browser_configs: dict) -> bool:
        try:
            try:
                self.client.networks.get("selenium-grid")
            except Exception:
                self.client.networks.create("selenium-grid", driver="bridge")
            try:
                hub = self.client.containers.get("selenium-hub")
                if hub.status != "running":
                    hub.restart()
            except Exception:
                self.client.containers.run(
                    "selenium/hub:4.18.1",
                    name="selenium-hub",
                    detach=True,
                    network="selenium-grid",
                    ports={
                        f"{self.settings.SELENIUM_HUB_PORT}/tcp": self.settings.SELENIUM_HUB_PORT
                    },
                    environment={
                        "SE_NODE_MAX_SESSIONS": str(self.settings.MAX_BROWSER_INSTANCES or 10),
                        "SE_NODE_OVERRIDE_MAX_SESSIONS": "true",
                    },
                )
            return True
        except Exception as e:
            logging.error(f"Error ensuring Docker hub: {e}")
            return False

    async def create_browsers(self, count: int, browser_type: str, browser_configs: dict) -> list:
        config = browser_configs[browser_type]
        browser_ids = []
        for _ in range(count):
            try:
                self.client.images.get(config["image"])
            except Exception as e:
                if "No such image" in str(e) or "not found" in str(e).lower():
                    self.client.images.pull(config["image"])
                else:
                    raise
            container = self.client.containers.run(
                config["image"],
                detach=True,
                network="selenium-grid",
                environment={
                    "SE_EVENT_BUS_HOST": "selenium-hub",
                    "SE_EVENT_BUS_PUBLISH_PORT": "4442",
                    "SE_EVENT_BUS_SUBSCRIBE_PORT": "4443",
                    "SE_NODE_MAX_SESSIONS": "1",
                },
                mem_limit=config["resources"]["memory"],
                cpu_count=int(float(config["resources"]["cpu"])),
            )
            cid = getattr(container, "id", None)
            if not cid:
                raise RuntimeError("Failed to start browser container or retrieve container ID.")
            browser_ids.append(cid[:12])
        return browser_ids

    async def get_browser_status(self, browser_id: str) -> dict:
        """Get status for a specific browser instance by container ID (Docker)."""
        try:
            container = self.client.containers.get(browser_id)
            container.reload()
            image_tag = None
            if getattr(container, "image", None) and getattr(container.image, "tags", None):
                image_tag = container.image.tags[0] if container.image.tags else None
            return {
                "id": getattr(container, "id", "")[:12],
                "status": getattr(container, "status", None),
                "name": getattr(container, "name", None),
                "image": image_tag,
            }
        except Exception:
            return {"status": "not found"}
