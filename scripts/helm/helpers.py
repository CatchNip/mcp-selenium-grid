from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.settings import Settings
from kubernetes.utils import parse_quantity  # type: ignore

from .models import K8sName


def resolve_namespace_context_and_kubeconfig(
    cli_namespace_arg: str,
    cli_kube_context_arg: Optional[str],
    cli_kubeconfig_arg: Optional[Path],
    settings: Settings,
) -> Tuple[K8sName, Optional[str], Optional[str]]:
    """Resolves the effective namespace and Kubernetes context."""
    namespace_name = cli_namespace_arg or settings.K8S_NAMESPACE
    namespace_obj = K8sName(name=namespace_name)
    effective_kube_context = (
        cli_kube_context_arg if cli_kube_context_arg is not None else settings.K8S_CONTEXT
    )

    resolved_kubeconfig_str: Optional[str] = None
    if cli_kubeconfig_arg is not None:
        # Typer converts the CLI argument to a Path object.
        resolved_kubeconfig_str = str(cli_kubeconfig_arg.expanduser())
    elif settings.K8S_KUBECONFIG:
        # settings.K8S_KUBECONFIG is a Path from the config file.
        resolved_kubeconfig_str = str(settings.K8S_KUBECONFIG.expanduser())

    return namespace_obj, effective_kube_context, resolved_kubeconfig_str


def format_memory(bytes_val: Decimal) -> str:
    # Using binary (Mi, Gi, Ti, …)
    # Coefficients in bytes
    units = [
        (1024**4, "Ti"),
        (1024**3, "Gi"),
        (1024**2, "Mi"),
        (1024**1, "Ki"),
        (1, "B"),
    ]
    for size, suffix in units:
        if bytes_val >= size:
            val = (bytes_val / size).quantize(Decimal("0.01"))
            return f"{val}{suffix}"
    return f"{bytes_val}B"


def map_config_to_helm_values(settings: Settings) -> Tuple[List[str], Dict[str, str]]:
    """Convert Settings values to Helm arguments.

    Args:
        settings: Application settings containing configuration values.

    Returns:
        Tuple of (list of --set arguments, dict of sensitive values).

    Raises:
        ValueError: If no browser configurations are found in settings.
    """
    if not settings.BROWSER_CONFIGS:
        raise ValueError("No browser configurations found in settings")

    first_browser = next(iter(settings.BROWSER_CONFIGS.values()))

    limit_pods = settings.MAX_BROWSER_INSTANCES + 1  # Browsers + Hub

    memory = parse_quantity(first_browser.resources.memory)

    cpu_decimal = Decimal(first_browser.resources.cpu)

    # Build the --set arguments with only non-sensitive values
    set_args = [
        f"namespace={settings.K8S_NAMESPACE}",
        f"resources.limits.cpu={cpu_decimal * limit_pods * 2}",
        f"resources.limits.memory={format_memory(memory * limit_pods * 2)}",
        f"resources.limits.pods={limit_pods}",
        f"resources.requests.cpu={cpu_decimal * limit_pods}",
        f"resources.requests.memory={format_memory(memory * limit_pods)}",
        f"resources.podLimits.cpu={cpu_decimal * 2}",
        f"resources.podLimits.memory={format_memory(memory * 2)}",
        f"resources.podRequests.cpu={cpu_decimal}",
        f"resources.podRequests.memory={format_memory(memory)}",
    ]

    # Store sensitive values separately
    sensitive_values: Dict[str, str] = {}

    if settings.BACKEND_CORS_ORIGINS:
        # Add network policy settings
        set_args.append("networkPolicy.enabled=true")

        # Add ingress rules
        for i, origin in enumerate(settings.BACKEND_CORS_ORIGINS):
            # Convert origin to CIDR format
            # For localhost, use 127.0.0.1/32
            if origin.startswith(("http://localhost", "https://localhost")):
                cidr = "127.0.0.1/32"
            else:
                # For other origins, extract the host and use /32 to specify a single IP
                host = origin.removeprefix("http://").removeprefix("https://").rstrip("/")
                if ":" in host:  # Remove port if present
                    host = host.split(":")[0]
                cidr = f"{host}/32"
            set_args.append(f"networkPolicy.ingress[{i}].from[0].ipBlock.cidr={cidr}")

    return set_args, sensitive_values
