import asyncio
import logging
import time  # Import time for waiting
import uuid  # Import uuid for pod naming
from os import environ
from typing import Any, Dict, List, Optional

from kubernetes.client import (
    AppsV1Api,
    CoreV1Api,
    V1Capabilities,
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
    V1PodSecurityContext,
    V1PodSpec,
    V1PodTemplateSpec,
    V1ResourceRequirements,
    V1SeccompProfile,
    V1SecurityContext,
    V1Service,
    V1ServicePort,
    V1ServiceSpec,
)
from kubernetes.config.config_exception import ConfigException
from kubernetes.config.incluster_config import load_incluster_config
from kubernetes.config.kube_config import load_kube_config

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

        self._load_k8s_config()

        self.k8s_core = CoreV1Api()
        self.k8s_apps = AppsV1Api()

    @property
    def URL(self) -> str:
        """
        Gets the Selenium Hub URL.
        - If in K8s, uses in-cluster service DNS.
        - If on host managing K8s, determines NodePort for localhost access.
        - Falls back to SELENIUM_HUB_PORT on localhost if NodePort cannot be found.
        """
        if "KUBERNETES_SERVICE_HOST" in environ:
            # App is in K8s, use in-cluster service DNS
            return f"http://{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}.{self.settings.K8S_NAMESPACE}.svc.cluster.local:{self.settings.SELENIUM_HUB_PORT}"
        else:
            # App is on host, managing K8s Hub. Attempt to find the NodePort.
            try:
                service = self.k8s_core.read_namespaced_service(
                    name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                    namespace=self.settings.K8S_NAMESPACE,
                )
                if service.spec and service.spec.ports:
                    for p in service.spec.ports:
                        # Assuming SELENIUM_HUB_PORT is the target port for the NodePort
                        if p.port == self.settings.SELENIUM_HUB_PORT and p.node_port:
                            return f"http://localhost:{p.node_port}"
                logging.warning(
                    f"Could not determine NodePort for service '{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}' "
                    f"in namespace '{self.settings.K8S_NAMESPACE}' for target port {self.settings.SELENIUM_HUB_PORT}. "
                    f"Falling back to http://localhost:{self.settings.SELENIUM_HUB_PORT}."
                )
            except ApiException as e:
                logging.error(f"API error fetching service details for URL: {e}. Falling back.")
            except Exception:
                logging.exception(
                    "Unexpected error fetching service details for URL. Falling back."
                )
            return f"http://localhost:{self.settings.SELENIUM_HUB_PORT}"

    def _load_k8s_config(self) -> None:
        """
        Load Kubernetes configuration based on the environment.
        If running inside a pod, use in-cluster config; otherwise, load from kubeconfig file.
        """
        try:
            # Load Kubernetes configuration
            try:
                # Try to load in-cluster config first
                load_incluster_config()
            except ConfigException:
                # If not in cluster, try to load from kubeconfig
                config_file_path: Optional[str] = None
                if self.settings.K8S_KUBECONFIG:
                    config_file_path = str(self.settings.K8S_KUBECONFIG)

                load_kube_config(config_file=config_file_path, context=self.settings.K8S_CONTEXT)

        except Exception as e:
            logging.exception(f"An unexpected error occurred during K8s config loading: {e}")
            raise e

    async def _sleep(self, attempt: int) -> None:
        """
        Wait for a specified delay before retrying an operation.
        This is used to handle transient errors in Kubernetes operations.
        """
        delay = self.settings.K8S_RETRY_DELAY_SECONDS * (2**attempt)  # Exponential backoff
        logging.info(f"Retrying in {delay} seconds...", stacklevel=2)
        await asyncio.sleep(delay)

    def _wait_for_resource_deletion(self, resource_type: str, name: str) -> None:
        """Waits for a specific resource to be deleted."""
        logging.info(
            f"Waiting for {resource_type} {name} to be deleted in namespace {self.settings.K8S_NAMESPACE}..."
        )
        for i in range(self.settings.K8S_MAX_RETRIES):
            try:
                if resource_type == "pod":
                    self.k8s_core.read_namespaced_pod(
                        name=name, namespace=self.settings.K8S_NAMESPACE
                    )
                elif resource_type == "deployment":
                    self.k8s_apps.read_namespaced_deployment(
                        name=name, namespace=self.settings.K8S_NAMESPACE
                    )
                elif resource_type == "service":
                    self.k8s_core.read_namespaced_service(
                        name=name, namespace=self.settings.K8S_NAMESPACE
                    )
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

    def cleanup_hub(self) -> None:
        """Clean up Selenium Hub deployment and service."""
        # Delete selenium-hub deployment
        try:
            logging.info(
                f"Deleting {self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} deployment in namespace {self.settings.K8S_NAMESPACE}..."
            )
            self.k8s_apps.delete_namespaced_deployment(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            )
            self._wait_for_resource_deletion(
                "deployment", self.settings.K8S_SELENIUM_GRID_SERVICE_NAME
            )
        except ApiException as api_exc:
            if api_exc.status != K8S_NOT_FOUND:
                logging.error(
                    f"Failed to delete deployment {self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}: {api_exc}"
                )
            else:
                logging.info(
                    f"{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} deployment not found for deletion."
                )
        except Exception as exc:
            logging.exception(
                f"Unexpected error deleting deployment {self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}: {exc}"
            )

        # Delete selenium-hub service
        try:
            logging.info(
                f"Deleting {self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} service in namespace {self.settings.K8S_NAMESPACE}..."
            )
            self.k8s_core.delete_namespaced_service(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            )
            self._wait_for_resource_deletion(
                "service", self.settings.K8S_SELENIUM_GRID_SERVICE_NAME
            )
        except ApiException as api_exc:
            if api_exc.status != K8S_NOT_FOUND:
                logging.error(
                    f"Failed to delete service {self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}: {api_exc}"
                )
            else:
                logging.info(
                    f"{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} service not found for deletion."
                )
        except Exception as exc:
            logging.exception(
                f"Unexpected error deleting service {self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}: {exc}"
            )

    def cleanup_browsers(self) -> None:
        """Clean up all browser pods."""
        try:
            logging.info(
                f"Deleting {self.NODE_LABEL} pods in namespace {self.settings.K8S_NAMESPACE}..."
            )
            self.k8s_core.delete_collection_namespaced_pod(
                namespace=self.settings.K8S_NAMESPACE, label_selector=f"app={self.NODE_LABEL}"
            )
            logging.info(f"{self.NODE_LABEL} pods delete request sent.")
        except ApiException as api_exc:
            if api_exc.status != K8S_NOT_FOUND:
                logging.error(f"Failed to delete {self.NODE_LABEL} pods: {api_exc}")
            else:
                logging.info(f"No {self.NODE_LABEL} pods found for deletion.")
        except Exception as exc:
            logging.exception(f"Unexpected error deleting {self.NODE_LABEL} pods: {exc}")

    def cleanup(self) -> None:
        """Clean up all resources by first cleaning up browsers then the hub."""
        super().cleanup()

    def _validate_deployment_config(self, deployment: V1Deployment) -> bool:
        """Validate deployment configuration."""
        try:
            if (
                not deployment.spec
                or not deployment.spec.template
                or not deployment.spec.template.spec
            ):
                logging.warning("Invalid deployment spec structure")
                return False

            # Check resource limits
            for container in deployment.spec.template.spec.containers:
                if not container.resources or not container.resources.limits:
                    logging.warning("Deployment missing resource limits")
                    return False

                # Validate CPU and memory limits
                if not all(key in container.resources.limits for key in ["cpu", "memory"]):
                    logging.warning("Deployment missing required resource limits")
                    return False

            # Check security context
            if not deployment.spec.template.spec.security_context:
                logging.warning("Deployment missing security context")
                return False

            return True
        except Exception as e:
            logging.error(f"Error validating deployment: {e}")
            return False

    def _validate_service_config(self, service: V1Service) -> bool:
        """Validate service configuration."""
        try:
            if not service.spec:
                logging.warning("Invalid service spec structure")
                return False

            # Check service type
            if service.spec.type not in ["ClusterIP", "LoadBalancer"]:
                logging.warning("Invalid service type")
                return False

            # Check port configuration
            if not service.spec.ports:
                logging.warning("Service missing port configuration")
                return False

            # Validate port settings
            for port in service.spec.ports:
                if not all(hasattr(port, attr) for attr in ["port", "target_port"]):
                    logging.warning("Service port missing required attributes")
                    return False

            return True
        except Exception as e:
            logging.error(f"Error validating service: {e}")
            return False

    async def _ensure_deployment_exists(self) -> None:
        """Ensure the Selenium Hub deployment exists."""
        try:
            # Check if deployment exists
            self.k8s_apps.read_namespaced_deployment(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            )
            logging.info(
                f"{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} deployment already exists."
            )
        except ApiException as e:
            if e.status == K8S_NOT_FOUND:
                logging.info(
                    f"{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} deployment not found, creating..."
                )
                deployment = self._create_hub_deployment()

                # Add validation for deployment configuration
                if not self._validate_deployment_config(deployment):
                    raise ValueError("Invalid deployment configuration")

                self.k8s_apps.create_namespaced_deployment(
                    namespace=self.settings.K8S_NAMESPACE, body=deployment
                )
                logging.info(f"{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} deployment created.")
            else:
                logging.error(
                    f"Error reading deployment {self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}: {e}"
                )
                raise

    async def _ensure_service_exists(self) -> None:
        """Ensure the Selenium Hub service exists."""
        try:
            # Check if service exists
            self.k8s_core.read_namespaced_service(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            )
            logging.info(f"{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} service already exists.")
        except ApiException as e:
            if e.status == K8S_NOT_FOUND:
                logging.info(
                    f"{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} service not found, creating..."
                )
                service = self._create_hub_service()

                # Add validation for service configuration
                if not self._validate_service_config(service):
                    raise ValueError("Invalid service configuration")

                self.k8s_core.create_namespaced_service(
                    namespace=self.settings.K8S_NAMESPACE, body=service
                )
                logging.info(f"{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME} service created.")
            else:
                logging.error(
                    f"Error reading service {self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}: {e}"
                )
                raise

    async def _ensure_namespace_exists(self) -> None:
        """Ensure the Kubernetes namespace exists."""
        try:
            self.k8s_core.read_namespace(name=self.settings.K8S_NAMESPACE)
            logging.info(f"Namespace '{self.settings.K8S_NAMESPACE}' already exists.")
        except ApiException as e:
            if e.status == K8S_NOT_FOUND:
                logging.info(f"Namespace '{self.settings.K8S_NAMESPACE}' not found, creating...")
                namespace_body = V1Namespace(
                    metadata=V1ObjectMeta(name=self.settings.K8S_NAMESPACE)
                )
                self.k8s_core.create_namespace(body=namespace_body)
                logging.info(f"Namespace '{self.settings.K8S_NAMESPACE}' created.")
            else:
                logging.error(
                    f"Error checking/creating namespace '{self.settings.K8S_NAMESPACE}': {e}"
                )
                raise
        except Exception as e:
            logging.exception(
                f"Unexpected error ensuring namespace '{self.settings.K8S_NAMESPACE}' exists: {e}"
            )
            raise

    async def ensure_hub_running(self) -> bool:
        """
        Ensure the Selenium Hub deployment and service exist in the namespace.
        """
        for i in range(self.settings.K8S_MAX_RETRIES):
            try:
                await self._ensure_namespace_exists()
                # Run deployment and service checks/creations concurrently
                await asyncio.gather(
                    self._ensure_deployment_exists(), self._ensure_service_exists()
                )
                return True
            except Exception as e:
                logging.exception(f"Attempt {i + 1} to ensure K8s hub failed: {e}")
                if i < self.settings.K8S_MAX_RETRIES - 1:
                    await self._sleep(i)
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
                    pod_name = f"{self.NODE_LABEL}-{browser_type}-{uuid.uuid4().hex[:8]}"
                    pod = V1Pod(
                        metadata=V1ObjectMeta(
                            name=pod_name,
                            labels={"app": self.NODE_LABEL, self.BROWSER_LABEL: browser_type},
                        ),
                        spec=V1PodSpec(
                            containers=[
                                V1Container(
                                    name=f"{self.NODE_LABEL}-{browser_type}",
                                    image=config.image,
                                    ports=[V1ContainerPort(container_port=config.port)],
                                    env=[
                                        V1EnvVar(
                                            name="SE_EVENT_BUS_HOST",
                                            value=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                                        ),
                                        V1EnvVar(
                                            name="SE_VNC_NO_PASSWORD",
                                            value=self.settings.SELENIUM_HUB_VNC_PASSWORD.get_secret_value(),
                                        ),
                                        V1EnvVar(
                                            name="SE_OPTS",
                                            value=f"--username {self.settings.SELENIUM_HUB_USER.get_secret_value()} \
                                                --password {self.settings.SELENIUM_HUB_PASSWORD.get_secret_value()}",
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
                    self.k8s_core.create_namespaced_pod(
                        namespace=self.settings.K8S_NAMESPACE, body=pod
                    )
                    logging.info(f"Pod {pod_name} created.")
                    browser_ids.append(pod_name)
                    break  # Exit retry loop on success
                except ApiException as e:
                    logging.error(f"Attempt {i + 1} to create browser pod failed: {e}")
                    if e.status == K8S_CONFLICT:
                        logging.warning("Pod name conflict, retrying with a new name.")
                        continue
                    if i < self.settings.K8S_MAX_RETRIES - 1:
                        await self._sleep(i)
                    else:
                        logging.exception("Max retries reached for creating browser pod.")
                except Exception as e:
                    logging.exception(f"Unexpected error creating browser pod: {e}")
                    if i < self.settings.K8S_MAX_RETRIES - 1:
                        await self._sleep(i)
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
        # Define PodSecurityContext
        pod_security_context = V1PodSecurityContext(
            run_as_non_root=True,
            run_as_user=1001,  # Ensure your selenium/hub image supports this UID
            fs_group=1001,  # Ensure your selenium/hub image supports this GID
            seccomp_profile=V1SeccompProfile(type="RuntimeDefault"),
        )

        # Define ContainerSecurityContext
        container_security_context = V1SecurityContext(
            allow_privilege_escalation=False,
            capabilities=V1Capabilities(drop=["ALL"]),
            run_as_non_root=True,
            run_as_user=1001,  # Must match pod or be a different non-root user
            seccomp_profile=V1SeccompProfile(type="RuntimeDefault"),
        )

        # Define the deployment
        container = V1Container(
            name=self.HUB_NAME,
            image="selenium/hub:4.18.1",  # Use a specific version
            ports=[V1ContainerPort(container_port=self.settings.SELENIUM_HUB_PORT)],
            env=[
                V1EnvVar(
                    name="SE_EVENT_BUS_HOST", value=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME
                ),
                V1EnvVar(
                    name="SE_PORT", value=str(self.settings.SELENIUM_HUB_PORT)
                ),  # Configure Hub's listening port
                V1EnvVar(name="SE_EVENT_BUS_PUBLISH_PORT", value="4442"),
                V1EnvVar(name="SE_EVENT_BUS_SUBSCRIBE_PORT", value="4443"),
                V1EnvVar(
                    name="SE_OPTS",
                    value=f"--username {self.settings.SELENIUM_HUB_USER.get_secret_value()} \
                        --password {self.settings.SELENIUM_HUB_PASSWORD.get_secret_value()}",
                ),
                V1EnvVar(
                    name="SE_VNC_NO_PASSWORD",
                    value=self.settings.SE_VNC_NO_PASSWORD,
                ),
                V1EnvVar(
                    name="SE_VNC_PASSWORD",
                    value=self.settings.SELENIUM_HUB_VNC_PASSWORD.get_secret_value(),
                ),
                V1EnvVar(name="SE_VNC_VIEW_ONLY", value=self.settings.SELENIUM_HUB_VNC_VIEW_ONLY),
            ],
            resources=V1ResourceRequirements(
                requests={"cpu": "0.5", "memory": "256Mi"},
                limits={"cpu": "1", "memory": "500Mi"},
            ),
            security_context=container_security_context,
        )

        template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels={"app": self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}),
            spec=V1PodSpec(
                containers=[container],
                security_context=pod_security_context,
            ),
        )

        spec = V1DeploymentSpec(
            replicas=1,  # Ensure only one hub instance
            template=template,
            selector=V1LabelSelector(
                match_labels={"app": self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}
            ),
        )

        deployment = V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=V1ObjectMeta(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            ),
            spec=spec,
        )

        return deployment

    def _create_hub_service(self) -> V1Service:
        """
        Create a Kubernetes Service object for the Selenium Hub.
        """
        # Define the service
        spec = V1ServiceSpec(
            selector={"app": self.settings.K8S_SELENIUM_GRID_SERVICE_NAME},
            ports=[
                V1ServicePort(
                    port=self.settings.SELENIUM_HUB_PORT,
                    target_port=self.settings.SELENIUM_HUB_PORT,
                )
            ],  # Expose port
            type="LoadBalancer",  # Use LoadBalancer for external access
        )

        service = V1Service(
            api_version="v1",
            kind="Service",
            metadata=V1ObjectMeta(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            ),
            spec=spec,
        )

        return service

    async def delete_browser(self, browser_id: str) -> bool:
        """Delete a specific browser pod by its ID (pod name). Returns True if deleted, False otherwise."""
        try:
            self.k8s_core.delete_namespaced_pod(
                name=browser_id, namespace=self.settings.K8S_NAMESPACE, body=V1DeleteOptions()
            )
            return True
        except Exception:
            return False
