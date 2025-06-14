import subprocess

from typer import Exit, echo

from .helpers import ensure_cli_installed


def check_kubernetes_cluster(
    kube_context: str | None = None, kubeconfig: str | None = None
) -> None:
    """Check if Kubernetes cluster is reachable.

    Raises:
        typer.Exit: If Kubernetes cluster is not reachable.
    """
    kubectl_path = ensure_cli_installed(
        "kubectl", "Please install kubectl from https://kubernetes.io/docs/tasks/tools/"
    )

    cmd = [kubectl_path, "cluster-info"]

    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])

    if kube_context:
        cmd.extend(["--context", kube_context])

    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        # Extract the last line of stderr which usually contains the most relevant error
        error_msg = result.stderr.strip().split("\n")[-1] if result.stderr else "Unknown error"
        echo(
            "Error: Kubernetes cluster is not reachable.\n"
            "Please ensure:\n"
            "1. You have a running Kubernetes cluster\n"
            "2. Your kubeconfig is properly configured\n"
            "3. You have the necessary permissions\n"
            f"\nDetails: {error_msg}",
            err=True,
        )
        raise Exit(code=1)


def delete_namespace(
    namespace: str,
    kube_context: str | None = None,
    kubeconfig: str | None = None,
    debug: bool = False,
) -> None:
    """Delete Kubernetes namespace using kubectl.

    Args:
        namespace: The name of the namespace to delete.
        kube_context: Optional Kubernetes context to use.
        kubeconfig_path: Optional path to the kubeconfig file.
        debug: Whether to enable debug output.

    Raises:
        typer.Exit: If kubectl is not found or the command fails.
    """
    kubectl_path = ensure_cli_installed(
        "kubectl", "Please install kubectl from https://kubernetes.io/docs/tasks/tools/"
    )
    cmd = [kubectl_path, "delete", "namespace", namespace]
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    if kube_context:
        cmd.extend(["--context", kube_context])

    action_msg = f"Deleting namespace '{namespace}'"
    echo(
        f"Debug: {action_msg} with command: {' '.join(cmd)}"
        if debug
        else f"Attempting: {action_msg}..."
    )

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603

    if proc.returncode == 0:
        echo(f"Namespace '{namespace}' deleted successfully or was already gone.")
    elif "not found" in proc.stderr.lower():
        echo(f"Namespace '{namespace}' not found, nothing to delete.")
    else:
        echo(
            f"Error: Failed to delete namespace '{namespace}'.\nSTDOUT: {proc.stdout.strip()}\nSTDERR: {proc.stderr.strip()}",
            err=True,
        )
        raise Exit(code=proc.returncode)
