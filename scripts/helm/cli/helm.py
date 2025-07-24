"""Utility functions for Helm operations."""

import subprocess
from typing import Optional

import typer

from .helpers import ensure_cli_installed
from .kubectl import check_kubernetes_cluster


def check_helm_installed() -> str:
    """Check if Helm CLI is installed and return its path."""
    return ensure_cli_installed(
        "helm", "Please install Helm from https://helm.sh/docs/intro/install/"
    )


def run_helm_command(
    cmd_args: list[str],
    kube_context: Optional[str] = None,
    kubeconfig: Optional[str] = None,
    debug: bool = False,
) -> None:
    """Run the Helm command.

    Args:
        cmd_args: List of command arguments to pass to Helm.
        debug: Whether to enable debug output.
        kube_context: Optional Kubernetes context to use.
        kubeconfig_path: Optional path to the kubeconfig file for cluster check.

    Raises:
        typer.Exit: If the command fails or encounters an error.
    """
    # Check prerequisites before proceeding
    helm_path = check_helm_installed()
    check_kubernetes_cluster(kube_context, kubeconfig)

    # Replace 'helm' with absolute path in cmd_args
    cmd_args[0] = helm_path

    # Use Typer's echo for command output
    if debug:
        typer.echo(f"Debug: Running command: {' '.join(cmd_args)}")
    else:
        typer.echo(f"Running: {' '.join(cmd_args)}")

    # Execute the command using subprocess
    result = subprocess.run(  # noqa: S603
        cmd_args,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        if debug:
            typer.echo(
                f"Debug: Command failed with output:\n{result.stdout}\n{result.stderr}",
                err=True,
            )
        typer.echo(f"Error: {result.stderr}", err=True)
        raise typer.Exit(code=result.returncode)  # No generic success message here
