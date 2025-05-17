import logging
from typing import Any
from kubernetes.client.rest import ApiException
from .backend import HubBackend

K8S_NOT_FOUND = 404


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
        from kubernetes import client, config

        self.settings = settings
        try:
            config.load_incluster_config()
            logging.info("Loaded in-cluster Kubernetes config.")
        except Exception as e:
            logging.warning(f"In-cluster config failed: {e}. Trying kube config.")
            config.load_kube_config()
            logging.info("Loaded kube config from default location.")
        self.k8s_core = client.CoreV1Api()
        self.k8s_apps = client.AppsV1Api()
        self.ns = settings.K8S_NAMESPACE

    def cleanup(self) -> None:
        """
        Clean up all Selenium Hub-related resources in the configured namespace.
        Deletes all selenium-node pods, the selenium-hub deployment, and the selenium-hub service.
        """
        # Delete selenium-node pods (all pods labeled as browser nodes)
        try:
            pods = self.k8s_core.list_namespaced_pod(
                namespace=self.ns, label_selector="app=selenium-node"
            )
            for pod in pods.items:
                pod_name = pod.metadata.name
                try:
                    self.k8s_core.delete_namespaced_pod(name=pod_name, namespace=self.ns)
                    logging.info(f"Deleted pod: {pod_name} in namespace {self.ns}")
                except ApiException as api_exc:
                    if api_exc.status != K8S_NOT_FOUND:
                        logging.error(f"Failed to delete pod {pod_name}: {api_exc}")
                except Exception as exc:
                    logging.error(f"Unexpected error deleting pod {pod_name}: {exc}")
        except ApiException as api_exc:
            logging.error(f"Error listing selenium-node pods: {api_exc}")
        except Exception as exc:
            logging.error(f"Unexpected error listing selenium-node pods: {exc}")

        # Delete selenium-hub deployment
        try:
            self.k8s_apps.delete_namespaced_deployment(name="selenium-hub", namespace=self.ns)
            logging.info(f"Deleted deployment: selenium-hub in namespace {self.ns}")
        except ApiException as api_exc:
            if api_exc.status != K8S_NOT_FOUND:
                logging.error(f"Failed to delete deployment selenium-hub: {api_exc}")
        except Exception as exc:
            logging.error(f"Unexpected error deleting deployment selenium-hub: {exc}")

        # Delete selenium-hub service
        try:
            self.k8s_core.delete_namespaced_service(name="selenium-hub", namespace=self.ns)
            logging.info(f"Deleted service: selenium-hub in namespace {self.ns}")
        except ApiException as api_exc:
            if api_exc.status != K8S_NOT_FOUND:
                logging.error(f"Failed to delete service selenium-hub: {api_exc}")
        except Exception as exc:
            logging.error(f"Unexpected error deleting service selenium-hub: {exc}")

    async def ensure_hub_running(self, browser_configs: dict) -> bool:
        """
        Ensure the Selenium Hub deployment and service exist in the namespace.
        If not, create them. Also creates the namespace if missing.
        """
        from kubernetes import client

        try:
            try:
                self.k8s_core.read_namespace(self.ns)
            except ApiException:
                ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=self.ns))
                self.k8s_core.create_namespace(ns)
            try:
                self.k8s_apps.read_namespaced_deployment(name="selenium-hub", namespace=self.ns)
            except ApiException:
                deployment = self._create_hub_deployment()
                self.k8s_apps.create_namespaced_deployment(namespace=self.ns, body=deployment)
            try:
                self.k8s_core.read_namespaced_service(name="selenium-hub", namespace=self.ns)
            except ApiException:
                service = self._create_hub_service()
                self.k8s_core.create_namespaced_service(namespace=self.ns, body=service)
            return True
        except Exception as e:
            logging.error(f"Error ensuring K8s hub: {e}")
            return False

    async def create_browsers(self, count: int, browser_type: str, browser_configs: dict) -> list:
        """
        Create the requested number of Selenium browser pods of the given type.
        Returns a list of pod names (browser IDs).
        """
        from kubernetes import client

        browser_ids = []
        config = browser_configs[browser_type]
        for _ in range(count):
            # Pod name is unique per request, using object id hash
            pod_name = f"selenium-node-{browser_type}-" + hex(hash(str(id(self))))[2:10]
            pod = client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name=pod_name, labels={"app": "selenium-node", "browser": browser_type}
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name=f"selenium-{browser_type}",
                            image=config["image"],
                            env=[
                                client.V1EnvVar(name="SE_EVENT_BUS_HOST", value="selenium-hub"),
                                client.V1EnvVar(name="SE_EVENT_BUS_PUBLISH_PORT", value="4442"),
                                client.V1EnvVar(name="SE_EVENT_BUS_SUBSCRIBE_PORT", value="4443"),
                                client.V1EnvVar(name="SE_NODE_MAX_SESSIONS", value="1"),
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
                        )
                    ]
                ),
            )
            self.k8s_core.create_namespaced_pod(namespace=self.ns, body=pod)
            browser_ids.append(pod_name)
        return browser_ids

    def _create_hub_deployment(self):
        """
        Return a Kubernetes Deployment object for the Selenium Hub.
        """
        from kubernetes import client

        return client.V1Deployment(
            metadata=client.V1ObjectMeta(name="selenium-hub"),
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
        from kubernetes import client

        return client.V1Service(
            metadata=client.V1ObjectMeta(name="selenium-hub"),
            spec=client.V1ServiceSpec(
                selector={"app": "selenium-hub"},
                ports=[client.V1ServicePort(port=4444, target_port=4444)],
            ),
        )
