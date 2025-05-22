import asyncio
import logging
import time  # Import time for waiting
import uuid  # Import uuid for pod naming
from typing import Any

from kubernetes import client, config  # Import client and config here
from kubernetes.client.rest import ApiException

from .backend import HubBackend

K8S_NOT_FOUND = 404
# Define a short delay and a maximum number of retries for API calls
RETRY_DELAY_SECONDS = 2
MAX_RETRIES = 5


class KubernetesHubBackend(HubBackend):
    """
    Backend for managing Selenium Hub on Kubernetes.
    Handles cleanup and resource management for Selenium Hub deployments.
    """

    def __init__(self, settings: Any) -> None:
        """
        Initialize the KubernetesHubBackend with the given settings.
        Loads Kubernetes configuration (in-cluster or from kubeconfig).
        """
        self.settings = settings
        try:
            config.load_incluster_config()
            logging.info("Loaded in-cluster Kubernetes config.")
        except config.ConfigException as e:  # More specific exception
            logging.warning(f"In-cluster config failed: {e}. Trying kube config.")
            try:
                config.load_kube_config()
                logging.info("Loaded kube config from default location.")
            except config.ConfigException as e:  # More specific exception
                logging.error(f"Failed to load kube config: {e}")
                # Depending on requirements, might re-raise or handle differently
                raise RuntimeError("Failed to load Kubernetes configuration") from e
        except Exception as e:  # Catch any other unexpected exceptions during config loading
            logging.exception(f"An unexpected error occurred during K8s config loading: {e}")
            raise RuntimeError("Unexpected error during Kubernetes configuration") from e

        self.k8s_core = client.CoreV1Api()
        self.k8s_apps = client.AppsV1Api()
        self.ns = settings.K8S_NAMESPACE

    def _wait_for_resource_deletion(self, resource_type: str, name: str):
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
                ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=self.ns))
                self.k8s_core.create_namespace(ns)
                logging.info(f"Namespace {self.ns} created.")
            else:
                logging.error(f"Error reading namespace {self.ns}: {e}")
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

    async def ensure_hub_running(self, browser_configs: dict) -> bool:
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
                    await asyncio.sleep(
                        self.settings.K8S_RETRY_DELAY_SECONDS * (2**i)
                    )  # Exponential backoff
                else:
                    logging.exception("Max retries reached for ensuring K8s hub.")
                    return False  # Failed after retries

        return False  # Explicitly return False after loop if max retries reached

    async def create_browsers(self, count: int, browser_type: str, browser_configs: dict) -> list:
        """
        Create the requested number of Selenium browser pods of the given type.
        Returns a list of pod names (browser IDs).
        """
        browser_ids = []
        config = browser_configs[browser_type]

        for _ in range(count):
            pod_name = None  # Initialize pod_name outside retry loop
            for i in range(self.settings.K8S_MAX_RETRIES):
                try:
                    # Pod name using UUID for better uniqueness
                    pod_name = f"selenium-node-{browser_type}-{uuid.uuid4().hex[:8]}"
                    pod = client.V1Pod(
                        metadata=client.V1ObjectMeta(
                            name=pod_name, labels={"app": "selenium-node", "browser": browser_type}
                        ),
                        spec=client.V1PodSpec(
                            containers=[
                                client.V1Container(
                                    name=f"selenium-{browser_type}",
                                    image=config["image"],
                                    ports=[
                                        client.V1ContainerPort(container_port=4444)
                                    ],  # Assuming 4444 is the default port for nodes
                                    env=[
                                        client.V1EnvVar(
                                            name="SE_EVENT_BUS_HOST", value="selenium-hub"
                                        ),
                                        client.V1EnvVar(
                                            name="SE_EVENT_BUS_PUBLISH_PORT", value="4442"
                                        ),
                                        client.V1EnvVar(
                                            name="SE_EVENT_BUS_SUBSCRIBE_PORT", value="4443"
                                        ),
                                        client.V1EnvVar(
                                            name="SE_NODE_MAX_SESSIONS",
                                            value=str(self.settings.SE_NODE_MAX_SESSIONS or 1),
                                        ),
                                        client.V1EnvVar(
                                            name="SE_NODE_OVERRIDE_MAX_SESSIONS", value="true"
                                        ),
                                    ],
                                    resources=client.V1ResourceRequirements(
                                        requests={
                                            "memory": config["resources"]["memory"],
                                            "cpu": config["resources"]["cpu"],
                                        },
                                        limits={
                                            "memory": config["resources"]["memory"],
                                            "cpu": config["resources"]["cpu"],
                                        },
                                    ),
                                    readiness_probe=client.V1Probe(
                                        http_get=client.V1HTTPGetAction(
                                            path="/readyz",  # Common Selenium node readiness path
                                            port=4444,
                                        ),
                                        initial_delay_seconds=10,
                                        period_seconds=5,
                                    ),
                                    liveness_probe=client.V1Probe(
                                        http_get=client.V1HTTPGetAction(
                                            path="/livez",  # Common Selenium node liveness path
                                            port=4444,
                                        ),
                                        initial_delay_seconds=15,
                                        period_seconds=20,
                                    ),
                                    image_pull_policy="IfNotPresent",  # Set image pull policy
                                )
                            ]
                        ),
                    )
                    # Attempt to create the pod after definition
                    self.k8s_core.create_namespaced_pod(namespace=self.ns, body=pod)
                    logging.info(f"Created pod: {pod_name} in namespace {self.ns}")
                    browser_ids.append(pod_name)
                    break  # Break from retry loop on success
                except ApiException as e:
                    logging.error(f"Attempt {i + 1} to create pod failed: {e}")
                    if i < self.settings.K8S_MAX_RETRIES - 1:
                        await asyncio.sleep(self.settings.K8S_RETRY_DELAY_SECONDS * (2**i))
                    else:
                        logging.error("Max retries reached for creating pod.")
                        raise RuntimeError("Failed to create pod after multiple retries") from e
                except Exception as e:
                    logging.exception(f"Unexpected error creating pod: {e}")
                    raise RuntimeError(f"Unexpected error creating pod: {e}") from e

        return browser_ids

    def _create_hub_deployment(self):
        """
        Return a Kubernetes Deployment object for the Selenium Hub.
        """
        return client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name="selenium-hub", labels={"app": "selenium-hub"}
            ),  # Added label for clarity
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(match_labels={"app": "selenium-hub"}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": "selenium-hub"}),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="selenium-hub",
                                image="selenium/hub:4.18.1",
                                ports=[client.V1ContainerPort(container_port=4444)],
                                env=[
                                    client.V1EnvVar(
                                        name="SE_NODE_MAX_SESSIONS",
                                        value=str(self.settings.MAX_BROWSER_INSTANCES or 10),
                                    ),
                                    client.V1EnvVar(
                                        name="SE_NODE_OVERRIDE_MAX_SESSIONS",
                                        value="true",
                                    ),
                                ],
                                # Add Readiness and Liveness probes for the Hub
                                readiness_probe=client.V1Probe(
                                    http_get=client.V1HTTPGetAction(
                                        path="/readyz",  # Common Selenium hub readiness path
                                        port=4444,
                                    ),
                                    initial_delay_seconds=10,
                                    period_seconds=5,
                                ),
                                liveness_probe=client.V1Probe(
                                    http_get=client.V1HTTPGetAction(
                                        path="/livez",  # Common Selenium hub liveness path
                                        port=4444,
                                    ),
                                    initial_delay_seconds=15,
                                    period_seconds=20,
                                ),
                                image_pull_policy="IfNotPresent",  # Set image pull policy
                            )
                        ]
                    ),
                ),
            ),
        )

    def _create_hub_service(self):
        """
        Return a Kubernetes Service object for the Selenium Hub.
        """
        return client.V1Service(
            metadata=client.V1ObjectMeta(name="selenium-hub"),
            spec=client.V1ServiceSpec(
                selector={"app": "selenium-hub"},
                ports=[client.V1ServicePort(port=4444, target_port=4444)],
                type="ClusterIP",  # Default to ClusterIP for internal communication
            ),
        )
