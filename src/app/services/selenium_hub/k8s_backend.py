import asyncio
import logging
import time  # Import time for waiting
import uuid  # Import uuid for pod naming
from typing import Any, Dict, List

from kubernetes.client import (
    AppsV1Api,
    CoreV1Api,
)
from kubernetes.client.exceptions import ApiException
from kubernetes.client.models import (
    V1Container,
    V1ContainerPort,
    V1DeleteOptions,
    V1Deployment,
    V1DeploymentSpec,
    V1EnvVar,
    V1LabelSelector,
    V1Namespace,
    V1ObjectMeta,
    V1Pod,
    V1PodSpec,
    V1PodTemplateSpec,
    V1ResourceRequirements,
    V1Service,
    V1ServicePort,
    V1ServiceSpec,
)

from app.core.models import BrowserConfig

from .backend import HubBackend

K8S_NOT_FOUND = 404
K8S_CONFLICT = 409


class KubernetesHubBackend(HubBackend):
    """
    Backend for managing Selenium Hub on Kubernetes.
    Handles cleanup and resource management for Selenium Hub deployments.
    """

    def __init__(self, settings: Any) -> None:
        """
        Initialize the KubernetesHubBackend with the given settings.
        """
        self.settings = settings
        try:
            # Attempt to load Kubernetes config, but skip if not available
            pass
        except Exception as e:
            logging.exception(f"An unexpected error occurred during K8s config loading: {e}")
            raise RuntimeError("Unexpected error during Kubernetes configuration") from e

        self.k8s_core = CoreV1Api()
        self.k8s_apps = AppsV1Api()
        self.ns = settings.K8S_NAMESPACE

    async def _RETRY(self, attempt: int) -> None:
        """
        Wait for a specified delay before retrying an operation.
        This is used to handle transient errors in Kubernetes operations.
        """
        delay = self.settings.K8S_RETRY_DELAY_SECONDS * (2**attempt)  # Exponential backoff
        logging.info(f"Retrying in {delay} seconds...", stacklevel=2)
        await asyncio.sleep(delay)

    def _wait_for_resource_deletion(self, resource_type: str, name: str) -> None:
        """Waits for a specific resource to be deleted."""
        logging.info(f"Waiting for {resource_type} {name} to be deleted in namespace {self.ns}...")
        for i in range(self.settings.K8S_MAX_RETRIES):
            try:
                if resource_type == "pod":
                    self.k8s_core.read_namespaced_pod(name=name, namespace=self.ns)
                elif resource_type == "deployment":
                    self.k8s_apps.read_namespaced_deployment(name=name, namespace=self.ns)
                elif resource_type == "service":
                    self.k8s_core.read_namespaced_service(name=name, namespace=self.ns)
                # If resource is still found, wait and retry
                time.sleep(self.settings.K8S_RETRY_DELAY_SECONDS)
            except ApiException as e:
                if e.status == K8S_NOT_FOUND:
                    logging.info(f"{resource_type} {name} deleted successfully.")
                    return  # Resource is gone
                else:
                    logging.error(f"Error waiting for {resource_type} {name} deletion: {e}")
                    raise  # Re-raise unexpected API errors
            except Exception as e:  # Catch other unexpected exceptions during wait
                logging.exception(
                    f"Unexpected error while waiting for {resource_type} {name} deletion: {e}"
                )
                raise  # Re-raise unexpected errors
        logging.warning(f"Timeout waiting for {resource_type} {name} to be deleted.")

    def cleanup(self) -> None:
        """
        Clean up all Selenium Hub-related resources in the configured namespace.
        Deletes all selenium-node pods, the selenium-hub deployment, and the selenium-hub service.
        """
        # Delete selenium-node pods using collection deletion
        try:
            logging.info(f"Deleting selenium-node pods in namespace {self.ns}...")
            self.k8s_core.delete_collection_namespaced_pod(
                namespace=self.ns, label_selector="app=selenium-node"
            )
            # Note: delete_collection is asynchronous, a more robust wait might be needed
            # depending on the exact requirements, but this is a basic implementation.
            logging.info("Selenium-node pods delete request sent.")
        except ApiException as api_exc:
            if api_exc.status != K8S_NOT_FOUND:
                logging.error(f"Failed to delete selenium-node pods: {api_exc}")
            else:
                logging.info("No selenium-node pods found for deletion.")
        except Exception as exc:
            logging.exception(f"Unexpected error deleting selenium-node pods: {exc}")

        # Delete selenium-hub deployment
        try:
            logging.info(f"Deleting selenium-hub deployment in namespace {self.ns}...")
            self.k8s_apps.delete_namespaced_deployment(name="selenium-hub", namespace=self.ns)
            self._wait_for_resource_deletion("deployment", "selenium-hub")
        except ApiException as api_exc:
            if api_exc.status != K8S_NOT_FOUND:
                logging.error(f"Failed to delete deployment selenium-hub: {api_exc}")
            else:
                logging.info("Selenium-hub deployment not found for deletion.")
        except Exception as exc:
            logging.exception(f"Unexpected error deleting deployment selenium-hub: {exc}")

        # Delete selenium-hub service
        try:
            logging.info(f"Deleting selenium-hub service in namespace {self.ns}...")
            self.k8s_core.delete_namespaced_service(name="selenium-hub", namespace=self.ns)
            self._wait_for_resource_deletion("service", "selenium-hub")
        except ApiException as api_exc:
            if api_exc.status != K8S_NOT_FOUND:
                logging.error(f"Failed to delete service selenium-hub: {api_exc}")
            else:
                logging.info("Selenium-hub service not found for deletion.")
        except Exception as exc:
            logging.exception(f"Unexpected error deleting service selenium-hub: {exc}")

    def _ensure_namespace_exists(self) -> None:
        """Ensure the Kubernetes namespace exists."""
        try:
            self.k8s_core.read_namespace(self.ns)
            logging.info(f"Namespace {self.ns} already exists.")
        except ApiException as e:
            if e.status == K8S_NOT_FOUND:
                logging.info(f"Namespace {self.ns} not found, creating...")
                ns = V1Namespace(metadata=V1ObjectMeta(name=self.ns))
                try:
                    self.k8s_core.create_namespace(ns)
                    logging.info(f"Namespace {self.ns} created.")
                except ApiException as ce:
                    logging.error(f"Failed to create namespace {self.ns}: {ce}")
                    raise
            else:
                logging.error(f"Error reading namespace {self.ns}: {e}")
                logging.error(
                    f"Full ApiException: status={e.status}, reason={getattr(e, 'reason', None)}, body={getattr(e, 'body', None)}"
                )
                raise  # Re-raise other API errors after logging
        except Exception as e:
            logging.exception(f"Unexpected error ensuring namespace {self.ns}: {e}")
            raise  # Re-raise other unexpected errors after logging

    def _ensure_deployment_exists(self) -> None:
        """Ensure the Selenium Hub deployment exists."""
        try:
            self.k8s_apps.read_namespaced_deployment(name="selenium-hub", namespace=self.ns)
            logging.info("Selenium-hub deployment already exists.")
        except ApiException as e:
            if e.status == K8S_NOT_FOUND:
                logging.info("Selenium-hub deployment not found, creating...")
                deployment = self._create_hub_deployment()
                self.k8s_apps.create_namespaced_deployment(namespace=self.ns, body=deployment)
                logging.info("Selenium-hub deployment created.")
            else:
                logging.error(f"Error reading deployment selenium-hub: {e}")
                raise  # Re-raise other API errors after logging
        except Exception as e:
            logging.exception(f"Unexpected error ensuring deployment selenium-hub: {e}")
            raise  # Re-raise other unexpected errors after logging

    def _ensure_service_exists(self) -> None:
        """Ensure the Selenium Hub service exists."""
        try:
            self.k8s_core.read_namespaced_service(name="selenium-hub", namespace=self.ns)
            logging.info("Selenium-hub service already exists.")
        except ApiException as e:
            if e.status == K8S_NOT_FOUND:
                logging.info("Selenium-hub service not found, creating...")
                service = self._create_hub_service()
                self.k8s_core.create_namespaced_service(namespace=self.ns, body=service)
                logging.info("Selenium-hub service created.")
            else:
                logging.error(f"Error reading service selenium-hub: {e}")
                raise  # Re-raise other API errors after logging
        except Exception as e:
            logging.exception(f"Unexpected error ensuring service selenium-hub: {e}")
            raise  # Re-raise other unexpected errors after logging

    async def ensure_hub_running(self) -> bool:
        """
        Ensure the Selenium Hub deployment and service exist in the namespace.
        If not, create them. Also creates the namespace if missing.
        """
        for i in range(self.settings.K8S_MAX_RETRIES):
            try:
                self._ensure_namespace_exists()
                self._ensure_deployment_exists()
                self._ensure_service_exists()
                return True
            except Exception as e:
                logging.exception(f"Attempt {i + 1} to ensure K8s hub failed: {e}")
                if i < self.settings.K8S_MAX_RETRIES - 1:
                    await self._RETRY(i)
                else:
                    logging.exception("Max retries reached for ensuring K8s hub.")
                    return False  # Failed after retries

        return False  # Explicitly return False after loop if max retries reached

    async def create_browsers(
        self, count: int, browser_type: str, browser_configs: Dict[str, BrowserConfig]
    ) -> List[str]:
        """
        Create the requested number of Selenium browser pods of the given type.
        Returns a list of pod names (browser IDs).
        """
        browser_ids = []
        config: BrowserConfig = browser_configs[browser_type]

        for _ in range(count):
            for i in range(self.settings.K8S_MAX_RETRIES):
                try:
                    pod_name = f"selenium-node-{browser_type}-{uuid.uuid4().hex[:8]}"
                    pod = V1Pod(
                        metadata=V1ObjectMeta(
                            name=pod_name, labels={"app": "selenium-node", "browser": browser_type}
                        ),
                        spec=V1PodSpec(
                            containers=[
                                V1Container(
                                    name=f"selenium-node-{browser_type}",
                                    image=config.image,
                                    ports=[V1ContainerPort(container_port=config.port)],
                                    env=[
                                        V1EnvVar(name="SE_EVENT_BUS_HOST", value="selenium-hub"),
                                        V1EnvVar(name="SE_VNC_NO_PASSWORD", value="true"),
                                        V1EnvVar(
                                            name="SE_OPTS",
                                            value=f"--username {self.settings.SELENIUM_HUB_USER} \
                                                --password {self.settings.SELENIUM_HUB_PASSWORD}",
                                        ),
                                    ],
                                    resources=V1ResourceRequirements(
                                        limits={
                                            "cpu": config.resources.cpu,
                                            "memory": config.resources.memory,
                                        },
                                        requests={
                                            "cpu": config.resources.cpu,
                                            "memory": config.resources.memory,
                                        },
                                    ),
                                )
                            ]
                        ),
                    )
                    self.k8s_core.create_namespaced_pod(namespace=self.ns, body=pod)
                    logging.info(f"Pod {pod_name} created.")
                    browser_ids.append(pod_name)
                    break  # Exit retry loop on success
                except ApiException as e:
                    logging.error(f"Attempt {i + 1} to create browser pod failed: {e}")
                    if e.status == K8S_CONFLICT:
                        logging.warning("Pod name conflict, retrying with a new name.")
                        continue
                    if i < self.settings.K8S_MAX_RETRIES - 1:
                        await self._RETRY(i)
                    else:
                        logging.exception("Max retries reached for creating browser pod.")
                except Exception as e:
                    logging.exception(f"Unexpected error creating browser pod: {e}")
                    if i < self.settings.K8S_MAX_RETRIES - 1:
                        await self._RETRY(i)
                    else:
                        logging.exception(
                            "Max retries reached for creating browser pod due to unexpected error."
                        )
            else:
                # This else executes if the inner loop did NOT break (i.e., all retries failed)
                logging.error("Failed to create browser pod after all retries.")
        # Only return browser_ids for successfully created pods
        return browser_ids

    def _create_hub_deployment(self) -> V1Deployment:
        """
        Create a Kubernetes Deployment object for the Selenium Hub.
        """
        # Define the deployment
        container = V1Container(
            name="selenium-hub",
            image="selenium/hub:4.18.1",  # Use a specific version
            ports=[V1ContainerPort(container_port=4444)],
            env=[
                V1EnvVar(name="SE_EVENT_BUS_HOST", value="localhost"),
                V1EnvVar(name="SE_EVENT_BUS_PUBLISH_PORT", value="4442"),
                V1EnvVar(name="SE_EVENT_BUS_SUBSCRIBE_PORT", value="4443"),
                V1EnvVar(name="SE_HUB_USER", value=self.settings.selenium_hub_user),
                V1EnvVar(name="SE_HUB_PASSWORD", value=self.settings.selenium_hub_password),
            ],
            resources=V1ResourceRequirements(
                requests={"cpu": "100m", "memory": "128Mi"},
                limits={"cpu": "200m", "memory": "256Mi"},
            ),
        )

        template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels={"app": "selenium-hub"}),
            spec=V1PodSpec(containers=[container]),
        )

        spec = V1DeploymentSpec(
            replicas=1,  # Ensure only one hub instance
            template=template,
            selector=V1LabelSelector(match_labels={"app": "selenium-hub"}),
            # Remove strategy argument if AppsV1DeploymentStrategy is not available
        )

        deployment = V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=V1ObjectMeta(name="selenium-hub", namespace=self.ns),
            spec=spec,
        )

        return deployment

    def _create_hub_service(self) -> V1Service:
        """
        Create a Kubernetes Service object for the Selenium Hub.
        """
        # Define the service
        spec = V1ServiceSpec(
            selector={"app": "selenium-hub"},
            ports=[V1ServicePort(port=4444, target_port=4444)],  # Expose port 4444
            type="LoadBalancer",  # Use LoadBalancer for external access
        )

        service = V1Service(
            api_version="v1",
            kind="Service",
            metadata=V1ObjectMeta(name="selenium-hub", namespace=self.ns),
            spec=spec,
        )

        return service

    async def get_browser_status(self, browser_id: str) -> Dict[str, Any]:
        """
        Get the status of a specific browser pod by its ID.
        Returns a dictionary with status information.
        """
        # In Kubernetes backend, browser_id is the pod name.
        pod_name = browser_id
        try:
            # Read the pod status
            pod = self.k8s_core.read_namespaced_pod(name=pod_name, namespace=self.ns)
            # Extract relevant status information. This is a basic example;
            # you might want to check pod conditions, container statuses, etc.
            # For simplicity, we'll just check the phase.
            status = pod.status.phase if pod.status and pod.status.phase else "unknown"
            if status == "Running":
                return {"status": "ready", "id": browser_id, "message": "Pod is running"}
            else:
                return {"status": status, "id": browser_id, "message": f"Pod status: {status}"}

        except ApiException as e:
            if e.status == K8S_NOT_FOUND:
                logging.info(f"Browser pod {browser_id} not found.")
                return {"status": "not found", "id": browser_id, "message": "Pod not found"}
            else:
                logging.error(f"Error getting status for pod {browser_id}: {e}")
                return {
                    "status": "error",
                    "id": browser_id,
                    "message": f"Kubernetes API error: {e}",
                }
        except Exception as e:
            logging.exception(f"Unexpected error getting status for pod {browser_id}: {e}")
            return {"status": "error", "id": browser_id, "message": f"Unexpected error: {e}"}

    async def delete_browser(self, browser_id: str) -> bool:
        """Delete a specific browser pod by its ID (pod name). Returns True if deleted, False otherwise."""
        try:
            self.k8s_core.delete_namespaced_pod(
                name=browser_id, namespace=self.ns, body=V1DeleteOptions()
            )
            return True
        except Exception:
            return False
