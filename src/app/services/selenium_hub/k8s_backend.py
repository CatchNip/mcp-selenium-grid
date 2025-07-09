import asyncio
import logging
import time
import uuid
from enum import Enum
from os import environ
from subprocess import PIPE, Popen
from threading import Thread
from typing import Any, Awaitable, Callable, Dict, List, Optional, TextIO, override

from kubernetes import watch  # type: ignore
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

HTTP_OK = 200


class ResourceType(Enum):
    """Enum for Kubernetes resource types."""

    POD = "pod"
    DEPLOYMENT = "deployment"
    SERVICE = "service"


class KubernetesConfigManager:
    """Handles Kubernetes configuration loading and cluster detection."""

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self._is_kind = False
        self._load_config()
        self._detect_kind_cluster()

    def _load_config(self) -> None:
        """Load Kubernetes configuration based on the environment."""
        try:
            try:
                load_incluster_config()
            except ConfigException:
                config_file_path: Optional[str] = None
                if self.settings.K8S_KUBECONFIG:
                    config_file_path = str(self.settings.K8S_KUBECONFIG)
                load_kube_config(config_file=config_file_path, context=self.settings.K8S_CONTEXT)
        except Exception as e:
            logging.exception(f"Failed to load Kubernetes configuration: {e}")
            raise

    def _detect_kind_cluster(self) -> None:
        """Detect if running on KinD cluster."""
        try:
            core_api = CoreV1Api()
            nodes = core_api.list_node().items
            self._is_kind = False
            for node in nodes:
                meta: V1ObjectMeta | None = node.metadata
                name: str = getattr(meta, "name", "")
                if name and name.endswith("-control-plane"):
                    self._is_kind = True
                    break
            if self._is_kind:
                logging.info("KinD cluster detected via node name suffix '-control-plane'.")
        except Exception:
            self._is_kind = False

    @property
    def is_kind(self) -> bool:
        return self._is_kind


class KubernetesUrlResolver:
    """Handles URL resolution for different Kubernetes environments."""

    def __init__(self, settings: Any, k8s_core: CoreV1Api, is_kind: bool) -> None:
        self.settings = settings
        self.k8s_core = k8s_core
        self._is_kind = is_kind

    def get_hub_url(self) -> str:
        """Get the appropriate Selenium Hub URL based on environment."""
        fallback_url = f"http://localhost:{self.settings.SELENIUM_HUB_PORT}"

        if "KUBERNETES_SERVICE_HOST" in environ:
            return self._get_in_cluster_url()

        return self._get_nodeport_url(fallback_url)

    def _get_in_cluster_url(self) -> str:
        """Get in-cluster service URL."""
        url = f"http://{self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}.{self.settings.K8S_NAMESPACE}.svc.cluster.local:{self.settings.SELENIUM_HUB_PORT}"
        logging.info(f"Using in-cluster DNS for Selenium Hub URL: {url}")
        return url

    def _get_nodeport_url(self, fallback_url: str) -> str:
        """Get NodePort URL or fallback to localhost."""
        try:
            service = self.k8s_core.read_namespaced_service(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            )

            if service.spec and service.spec.ports:
                for port in service.spec.ports:
                    if port.port == self.settings.SELENIUM_HUB_PORT and port.node_port:
                        url = f"http://localhost:{port.node_port}"
                        logging.info(f"Using NodePort for Selenium Hub URL: {url}")
                        return url

            logging.warning(
                f"Could not determine NodePort for service. Falling back to {fallback_url}."
            )
        except ApiException as e:
            logging.error(
                f"API error fetching NodePort service details: {e}. Falling back to {fallback_url}."
            )
        except Exception:
            logging.exception(
                f"Unexpected error fetching NodePort service details. Falling back to {fallback_url}."
            )

        return fallback_url


class KubernetesResourceManager:
    """Handles Kubernetes resource operations with proper error handling."""

    def __init__(self, settings: Any, k8s_core: CoreV1Api, k8s_apps: AppsV1Api) -> None:
        self.settings = settings
        self.k8s_core = k8s_core
        self.k8s_apps = k8s_apps

    def delete_resource(self, resource_type: ResourceType, name: str) -> None:
        self._delete_resource(resource_type, name)

    def read_resource(self, resource_type: ResourceType, name: str) -> Any:
        return self._read_resource(resource_type, name)

    async def sleep(self, attempt: int) -> None:
        """Wait with exponential backoff."""
        delay = self.settings.K8S_RETRY_DELAY_SECONDS * (2**attempt)
        logging.info(f"Retrying in {delay} seconds...", stacklevel=2)
        await asyncio.sleep(delay)

    def _wait_for_resource_deletion(self, resource_type: ResourceType, name: str) -> None:
        """Wait for a specific resource to be deleted."""
        logging.info(f"Waiting for {resource_type.value} {name} to be deleted...")

        for _ in range(self.settings.K8S_MAX_RETRIES):
            try:
                self._read_resource(resource_type, name)
                time.sleep(self.settings.K8S_RETRY_DELAY_SECONDS)
            except ApiException as e:
                if e.status == K8S_NOT_FOUND:
                    logging.info(f"{resource_type.value} {name} deleted successfully.")
                    return
                else:
                    logging.error(f"Error waiting for {resource_type.value} {name} deletion: {e}")
                    raise
            except Exception as e:
                logging.exception(
                    f"Unexpected error while waiting for {resource_type.value} {name} deletion: {e}"
                )
                raise

        logging.warning(f"Timeout waiting for {resource_type.value} {name} to be deleted.")

    def _read_resource(self, resource_type: ResourceType, name: str) -> Any:
        """Read a Kubernetes resource."""
        if resource_type == ResourceType.POD:
            return self.k8s_core.read_namespaced_pod(
                name=name, namespace=self.settings.K8S_NAMESPACE
            )
        elif resource_type == ResourceType.DEPLOYMENT:
            return self.k8s_apps.read_namespaced_deployment(
                name=name, namespace=self.settings.K8S_NAMESPACE
            )
        elif resource_type == ResourceType.SERVICE:
            return self.k8s_core.read_namespaced_service(
                name=name, namespace=self.settings.K8S_NAMESPACE
            )
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")

    def _delete_resource(self, resource_type: ResourceType, name: str) -> None:
        """Delete a Kubernetes resource."""
        try:
            if resource_type == ResourceType.DEPLOYMENT:
                self.k8s_apps.delete_namespaced_deployment(
                    name=name, namespace=self.settings.K8S_NAMESPACE
                )
            elif resource_type == ResourceType.SERVICE:
                self.k8s_core.delete_namespaced_service(
                    name=name, namespace=self.settings.K8S_NAMESPACE
                )
            elif resource_type == ResourceType.POD:
                self.k8s_core.delete_namespaced_pod(
                    name=name, namespace=self.settings.K8S_NAMESPACE, body=V1DeleteOptions()
                )
            self._wait_for_resource_deletion(resource_type, name)
        except ApiException as e:
            if e.status != K8S_NOT_FOUND:
                logging.error(f"Failed to delete {resource_type.value} {name}: {e}")
                raise
            else:
                logging.info(f"{resource_type.value} {name} not found for deletion.")
                # Raise to signal not found to caller
                raise ApiException(
                    status=K8S_NOT_FOUND,
                    reason=f"{resource_type.value} {name} not found for deletion.",
                )
        except Exception as e:
            logging.exception(f"Unexpected error deleting {resource_type.value} {name}: {e}")
            raise


class PortForwardManager:
    # TODO: Too many arguments in __init__. Consider refactoring to use a config object or dataclass if more are added.
    def __init__(  # noqa: PLR0913
        self,
        service_name: str,
        namespace: str,
        local_port: int,
        remote_port: int,
        check_health: Callable[[], Awaitable[bool]],
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
        max_retries: int = 5,
        health_timeout: int = 30,
    ) -> None:
        self.service_name = service_name
        self.namespace = namespace
        self.local_port = local_port
        self.remote_port = remote_port
        self.kubeconfig = kubeconfig
        self.context = context
        self.check_health = check_health
        self.max_retries = max_retries
        self.health_timeout = health_timeout
        self.process: Optional[Popen[str]] = None

    def _stream_reader(self, stream: TextIO, log_func: Callable[[str], None], prefix: str) -> None:
        try:
            for line in iter(stream.readline, ""):
                if line:
                    log_func(f"{prefix}: {line.strip()}")
        except Exception as e:
            logging.warning(f"Exception in port-forward stream reader: {e}")

    def _start_port_forward(self) -> Optional[Popen[str]]:
        cmd = [
            "kubectl",
            "port-forward",
            f"service/{self.service_name}",
            f"{self.local_port}:{self.remote_port}",
            "-n",
            self.namespace,
        ]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", str(self.kubeconfig)])
        if self.context:
            cmd.extend(["--context", self.context])
        try:
            process = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)  # noqa: S603
            logging.info("Started kubectl service port-forward.")
            if process.stdout is not None:
                Thread(
                    target=self._stream_reader,
                    args=(process.stdout, logging.info, "kubectl port-forward stdout"),
                    daemon=True,
                ).start()
            if process.stderr is not None:
                Thread(
                    target=self._stream_reader,
                    args=(process.stderr, logging.error, "kubectl port-forward stderr"),
                    daemon=True,
                ).start()
            return process
        except FileNotFoundError:
            logging.error("kubectl not found! Please ensure kubectl is installed and in your PATH.")
            return None
        except Exception as e:
            logging.error(f"Unexpected error starting kubectl port-forward: {e}")
            return None

    async def start(self) -> bool:
        for attempt in range(1, self.max_retries + 1):
            logging.info(f"Attempt {attempt} to start port-forward and health check...")
            self.process = self._start_port_forward()
            if not self.process:
                await asyncio.sleep(2)
                continue
            await asyncio.sleep(2)  # Give port-forward a moment to start
            if self.process.poll() is not None:
                out, err = self.process.communicate(timeout=2)
                if out:
                    logging.info(f"kubectl port-forward stdout (early exit): {out.strip()}")
                if err:
                    logging.error(f"kubectl port-forward process exited early: {err.strip()}")
                self.process = None
                await asyncio.sleep(2)
                continue
            if await self.check_health():
                logging.info("Port-forward and health check succeeded.")
                return True
            # Health check failed, kill process and retry
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except Exception:
                    self.process.kill()
                self.process = None
            await asyncio.sleep(2)
        logging.error("Failed to start port-forward and connect to service after retries.")
        return False

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None


class KubernetesHubBackend(HubBackend):
    """
    Backend for managing Selenium Hub on Kubernetes.
    Handles cleanup and resource management for Selenium Hub deployments.
    """

    _port_forward_process: Optional[Popen[str]]
    _port_forward_manager: Optional[PortForwardManager]

    def __init__(self, settings: Any) -> None:
        """Initialize the KubernetesHubBackend with the given settings."""
        self.settings = settings

        # Initialize components
        self.config_manager = KubernetesConfigManager(settings)
        self.k8s_core = CoreV1Api()
        self.k8s_apps = AppsV1Api()
        self.resource_manager = KubernetesResourceManager(settings, self.k8s_core, self.k8s_apps)
        self.url_resolver = KubernetesUrlResolver(
            settings, self.k8s_core, self.config_manager.is_kind
        )

        # Port-forwarding for KinD
        self._port_forward_process = None
        self._port_forward_manager = None

    @property
    def URL(self) -> str:
        """Get the Selenium Hub URL."""
        return self.url_resolver.get_hub_url()

    def cleanup_hub(self) -> None:
        """Clean up Selenium Hub deployment and service."""
        try:
            self.resource_manager.delete_resource(
                ResourceType.DEPLOYMENT, self.settings.K8S_SELENIUM_GRID_SERVICE_NAME
            )
        except Exception as e:
            logging.exception(f"Exception during deletion of deployment: {e}")

        try:
            self.resource_manager.delete_resource(
                ResourceType.SERVICE, self.settings.K8S_SELENIUM_GRID_SERVICE_NAME
            )
        except Exception as e:
            logging.exception(f"Exception during deletion of service: {e}")

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

    @override
    def cleanup(self) -> None:
        """Clean up all resources by first cleaning up browsers then the hub."""
        if self._port_forward_process:
            self._port_forward_process.terminate()
            self._port_forward_process.wait()
            self._port_forward_process = None
            logging.info("Stopped kubectl service port-forward for KinD.")

        super().cleanup()

    def _validate_deployment_config(self, deployment: V1Deployment) -> bool:
        """Validate deployment configuration."""
        try:
            if not self._has_valid_spec_structure(deployment):
                return False

            if not self._has_valid_resource_limits(deployment):
                return False

            if (
                deployment.spec is None
                or deployment.spec.template is None
                or deployment.spec.template.spec is None
                or not deployment.spec.template.spec.security_context
            ):
                logging.warning("Deployment missing security context")
                return False

            return True
        except Exception as e:
            logging.error(f"Error validating deployment: {e}")
            return False

    def _has_valid_spec_structure(self, deployment: V1Deployment) -> bool:
        """Check if deployment has valid spec structure."""
        if (
            deployment.spec is None
            or deployment.spec.template is None
            or deployment.spec.template.spec is None
        ):
            logging.warning("Invalid deployment spec structure")
            return False
        return True

    def _has_valid_resource_limits(self, deployment: V1Deployment) -> bool:
        """Check if deployment has valid resource limits."""
        if (
            deployment.spec is None
            or deployment.spec.template is None
            or deployment.spec.template.spec is None
            or deployment.spec.template.spec.containers is None
        ):
            logging.warning("Invalid deployment spec structure for resource limits")
            return False
        for container in deployment.spec.template.spec.containers:
            if not container.resources or not container.resources.limits:
                logging.warning("Deployment missing resource limits")
                return False

            required_limits = ["cpu", "memory"]
            if not all(key in container.resources.limits for key in required_limits):
                logging.warning("Deployment missing required resource limits")
                return False
        return True

    def _validate_service_config(self, service: V1Service) -> bool:
        """Validate service configuration."""
        try:
            if not service.spec:
                logging.warning("Invalid service spec structure")
                return False

            if service.spec.type not in ["ClusterIP", "NodePort"]:
                logging.warning("Invalid service type")
                return False

            if not service.spec.ports:
                logging.warning("Service missing port configuration")
                return False

            required_attrs = ["port", "target_port"]
            for port in service.spec.ports:
                if not all(hasattr(port, attr) for attr in required_attrs):
                    logging.warning("Service port missing required attributes")
                    return False

            return True
        except Exception as e:
            logging.error(f"Error validating service: {e}")
            return False

    def ensure_resource_exists(
        self,
        resource_type: ResourceType,
        name: str,
        create_func: Callable[..., Any],
        validate_func: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Generic method to ensure a resource exists."""
        try:
            self.resource_manager.read_resource(resource_type, name)
            logging.info(f"{name} {resource_type.value} already exists.")
        except ApiException as e:
            if e.status == K8S_NOT_FOUND:
                logging.info(f"{name} {resource_type.value} not found, creating...")
                resource = create_func()

                if validate_func and not validate_func(resource):
                    raise ValueError(f"Invalid {resource_type.value} configuration")

                if resource_type == ResourceType.DEPLOYMENT:
                    self.k8s_apps.create_namespaced_deployment(
                        namespace=self.settings.K8S_NAMESPACE, body=resource
                    )
                elif resource_type == ResourceType.SERVICE:
                    self.k8s_core.create_namespaced_service(
                        namespace=self.settings.K8S_NAMESPACE, body=resource
                    )

                logging.info(f"{name} {resource_type.value} created.")
            else:
                logging.error(f"Error reading {resource_type.value} {name}: {e}")
                raise

    async def _ensure_deployment_exists(self) -> None:
        """Ensure the Selenium Hub deployment exists."""
        self.ensure_resource_exists(
            ResourceType.DEPLOYMENT,
            self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
            self._create_hub_deployment,
            self._validate_deployment_config,
        )

    async def _ensure_service_exists(self) -> None:
        """Ensure the Selenium Hub service exists."""
        self.ensure_resource_exists(
            ResourceType.SERVICE,
            self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
            self._create_hub_service,
            self._validate_service_config,
        )

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
        """Ensure the Selenium Hub deployment and service exist in the namespace."""
        for i in range(self.settings.K8S_MAX_RETRIES):
            try:
                await self._ensure_namespace_exists()

                # First ensure deployment exists (this creates pods)
                await self._ensure_deployment_exists()

                # Then ensure service exists (this exposes the pods)
                await self._ensure_service_exists()

                if self.config_manager.is_kind and not self._port_forward_process:
                    self._wait_for_hub_pod_ready()
                    self._start_service_port_forward()

                return True
            except Exception as e:
                logging.exception(f"Attempt {i + 1} to ensure K8s hub failed: {e}")
                if i < self.settings.K8S_MAX_RETRIES - 1:
                    await self.resource_manager.sleep(i)
                else:
                    logging.exception("Max retries reached for ensuring K8s hub.")
                    return False

        return False

    def _wait_for_hub_pod_ready(self, timeout: int = 60) -> None:
        """Wait until the Selenium Hub pod is running and ready using the Watch API."""

        label_selector = f"app={self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}"
        start = time.time()
        w = watch.Watch()
        logging.info(
            f"Waiting for Selenium Hub pod to be ready (timeout: {timeout}s) using Watch API..."
        )
        try:
            for event in w.stream(
                self.k8s_core.list_namespaced_pod,
                namespace=self.settings.K8S_NAMESPACE,
                label_selector=label_selector,
                timeout_seconds=timeout,
            ):
                pod = event["object"]
                if not pod.status or not pod.metadata or not pod.metadata.name:
                    continue
                pod_name = pod.metadata.name
                if pod.status.phase == "Running":
                    if pod.status.container_statuses and all(
                        cs.ready for cs in pod.status.container_statuses
                    ):
                        logging.info(f"Selenium Hub pod {pod_name} is ready.")
                        w.stop()
                        return
                elif pod.status.phase == "Failed":
                    logging.error(f"Pod {pod_name} failed to start.")
                    w.stop()
                    raise RuntimeError(f"Pod {pod_name} failed to start.")
                # Pending and other phases: just keep watching
                if time.time() - start > timeout:
                    w.stop()
                    break
            raise TimeoutError(
                f"Timed out waiting for Selenium Hub pod to be running and ready after {timeout} seconds."
            )
        except Exception as e:
            logging.warning(f"Error while watching pod status: {e}")
            raise

    async def create_browsers(
        self, count: int, browser_type: str, browser_configs: Dict[str, BrowserConfig]
    ) -> List[str]:
        """Create the requested number of Selenium browser pods of the given type."""
        browser_ids = []
        config: BrowserConfig = browser_configs[browser_type]

        for _ in range(count):
            for i in range(self.settings.K8S_MAX_RETRIES):
                try:
                    pod_name = f"{self.NODE_LABEL}-{browser_type}-{uuid.uuid4().hex[:8]}"
                    pod = self._create_browser_pod(pod_name, browser_type, config)

                    self.k8s_core.create_namespaced_pod(
                        namespace=self.settings.K8S_NAMESPACE, body=pod
                    )
                    logging.info(f"Pod {pod_name} created.")
                    browser_ids.append(pod_name)
                    break
                except ApiException as e:
                    logging.error(f"Attempt {i + 1} to create browser pod failed: {e}")
                    if e.status == K8S_CONFLICT:
                        logging.warning("Pod name conflict, retrying with a new name.")
                        continue
                    if i < self.settings.K8S_MAX_RETRIES - 1:
                        await self.resource_manager.sleep(i)
                    else:
                        logging.exception("Max retries reached for creating browser pod.")
                except Exception as e:
                    logging.exception(f"Unexpected error creating browser pod: {e}")
                    if i < self.settings.K8S_MAX_RETRIES - 1:
                        await self.resource_manager.sleep(i)
                    else:
                        logging.exception(
                            "Max retries reached for creating browser pod due to unexpected error."
                        )
            else:
                logging.error("Failed to create browser pod after all retries.")

        return browser_ids

    def _create_browser_pod(self, pod_name: str, browser_type: str, config: BrowserConfig) -> V1Pod:
        """Create a browser pod configuration."""
        return V1Pod(
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
                        env=self._get_browser_env_vars(),
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

    def _get_browser_env_vars(self) -> List[V1EnvVar]:
        """Get environment variables for browser containers."""
        return [
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
        ]

    def _create_hub_deployment(self) -> V1Deployment:
        """Create a Kubernetes Deployment object for the Selenium Hub."""
        pod_security_context = V1PodSecurityContext(
            run_as_non_root=True,
            run_as_user=1001,
            fs_group=1001,
            seccomp_profile=V1SeccompProfile(type="RuntimeDefault"),
        )

        container_security_context = V1SecurityContext(
            allow_privilege_escalation=False,
            capabilities=V1Capabilities(drop=["ALL"]),
            run_as_non_root=True,
            run_as_user=1001,
            seccomp_profile=V1SeccompProfile(type="RuntimeDefault"),
        )

        container = V1Container(
            name=self.HUB_NAME,
            image="selenium/hub:4.18.1",
            ports=[V1ContainerPort(container_port=self.settings.SELENIUM_HUB_PORT)],
            env=self._get_hub_env_vars(),
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
            replicas=1,
            template=template,
            selector=V1LabelSelector(
                match_labels={"app": self.settings.K8S_SELENIUM_GRID_SERVICE_NAME}
            ),
        )

        return V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=V1ObjectMeta(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            ),
            spec=spec,
        )

    def _get_hub_env_vars(self) -> List[V1EnvVar]:
        """Get environment variables for hub container."""
        return [
            V1EnvVar(name="SE_EVENT_BUS_HOST", value=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME),
            V1EnvVar(name="SE_PORT", value=str(self.settings.SELENIUM_HUB_PORT)),
            V1EnvVar(name="SE_EVENT_BUS_PUBLISH_PORT", value="4442"),
            V1EnvVar(name="SE_EVENT_BUS_SUBSCRIBE_PORT", value="4443"),
            V1EnvVar(
                name="SE_OPTS",
                value=f"--username {self.settings.SELENIUM_HUB_USER.get_secret_value()} \
                    --password {self.settings.SELENIUM_HUB_PASSWORD.get_secret_value()}",
            ),
            V1EnvVar(name="SE_VNC_NO_PASSWORD", value=self.settings.SE_VNC_NO_PASSWORD),
            V1EnvVar(
                name="SE_VNC_PASSWORD",
                value=self.settings.SELENIUM_HUB_VNC_PASSWORD.get_secret_value(),
            ),
            V1EnvVar(name="SE_VNC_VIEW_ONLY", value=self.settings.SELENIUM_HUB_VNC_VIEW_ONLY),
        ]

    def _create_hub_service(self) -> V1Service:
        """Create a Kubernetes Service object for the Selenium Hub."""
        service_type = "ClusterIP" if "KUBERNETES_SERVICE_HOST" in environ else "NodePort"

        spec = V1ServiceSpec(
            selector={"app": self.settings.K8S_SELENIUM_GRID_SERVICE_NAME},
            ports=[
                V1ServicePort(
                    port=self.settings.SELENIUM_HUB_PORT,
                    target_port=self.settings.SELENIUM_HUB_PORT,
                )
            ],
            type=service_type,
        )

        return V1Service(
            api_version="v1",
            kind="Service",
            metadata=V1ObjectMeta(
                name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
                namespace=self.settings.K8S_NAMESPACE,
            ),
            spec=spec,
        )

    async def delete_browser(self, browser_id: str) -> bool:
        """Delete a specific browser pod by its ID (pod name)."""
        try:
            self.resource_manager.delete_resource(ResourceType.POD, browser_id)
            return True
        except Exception:
            return False

    def _start_service_port_forward(self) -> None:
        """Start kubectl port-forward for the Selenium Hub service (KinD only), with health check and retries."""
        if not self.config_manager.is_kind or self._port_forward_process:
            return
        pfm = PortForwardManager(
            service_name=self.settings.K8S_SELENIUM_GRID_SERVICE_NAME,
            namespace=self.settings.K8S_NAMESPACE,
            local_port=self.settings.SELENIUM_HUB_PORT,
            remote_port=self.settings.SELENIUM_HUB_PORT,
            kubeconfig=getattr(self.settings, "K8S_KUBECONFIG", None),
            context=getattr(self.settings, "K8S_CONTEXT", None),
            check_health=self.check_hub_health,
            max_retries=5,
            health_timeout=30,
        )
        if pfm.start():
            self._port_forward_process = pfm.process
            self._port_forward_manager = pfm  # Optionally keep reference for later stop
        else:
            self._port_forward_process = None
            self._port_forward_manager = None
            raise RuntimeError("Failed to start port-forward and connect to Selenium Hub.")

    def stop_service_port_forward(self) -> None:
        if hasattr(self, "_port_forward_manager") and self._port_forward_manager:
            self._port_forward_manager.stop()
            self._port_forward_manager = None
        self._port_forward_process = None

    @override
    async def check_hub_health(
        self, username: str | None = None, password: str | None = None
    ) -> bool:
        result = await super().check_hub_health(
            username=username or self.settings.SELENIUM_HUB_USER.get_secret_value(),
            password=password or self.settings.SELENIUM_HUB_PASSWORD.get_secret_value(),
        )
        if result:
            logging.info("KubernetesHubBackend: Hub health check succeeded.")
        else:
            logging.error("KubernetesHubBackend: Hub health check failed.")
        return result
