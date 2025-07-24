#!/usr/bin/env python3
"""CLI for deploying Selenium Grid using Helm."""

import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Optional

import typer
from app.core.settings import Settings

from .cli.helm import run_helm_command
from .cli.kubectl import delete_namespace
from .helpers import map_config_to_helm_values, resolve_namespace_context_and_kubeconfig
from .models import HelmChartPath, K8sName


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def create_application() -> typer.Typer:  # noqa: PLR0915
    """Create Typer application for Helm Selenium Grid deployment."""
    app = typer.Typer(
        name="helm-selenium-grid",
        help="Deploy Selenium Grid using Helm",
    )

    @app.command()  # TODO: run deploy and fix namespace already exists after uninstall with --delete-namespace
    def deploy(  # noqa: PLR0913
        chart_path: Path = typer.Option(
            "deployment/helm/selenium-grid",
            help="Path to the Helm chart",
            exists=True,
            dir_okay=True,
            file_okay=False,  # Ensure it's a directory
        ),
        release_name: Optional[str] = typer.Option(
            None,
            help="Name of the Helm release",
        ),
        namespace: str = typer.Option(
            "",
            help="Kubernetes namespace (defaults to value from config.yaml)",
        ),
        context: Optional[str] = typer.Option(
            None,
            help="Kubernetes context to use (e.g. 'k3s'). Overrides context from config.yaml.",
        ),
        kubeconfig: Optional[Path] = typer.Option(
            None,
            "--kubeconfig",
            help="Path to the kubeconfig file. Overrides KUBECONFIG from settings.",
        ),
        debug: bool = typer.Option(
            False,
            help="Enable debug output",
        ),
    ) -> None:
        """Deploy Selenium Grid using Helm CLI."""
        settings = get_settings()

        # Use settings for default release_name if not provided
        effective_release_name = (
            release_name if release_name else settings.kubernetes.SELENIUM_GRID_SERVICE_NAME
        )

        # Validate inputs using Pydantic models
        chart = HelmChartPath(path=chart_path)
        release = K8sName(name=effective_release_name)

        namespace_obj, effective_kube_context, effective_kubeconfig = (
            resolve_namespace_context_and_kubeconfig(
                cli_namespace_arg=namespace,
                cli_kube_context_arg=context,
                cli_kubeconfig_arg=kubeconfig,
                settings=settings,
            )
        )

        if debug:
            typer.echo("--- Debug Information ---")
            typer.echo(f"Chart: {chart.path}")
            typer.echo(f"Release Name: {release}")
            typer.echo(f"Namespace: {namespace_obj}")
            typer.echo(f"Context: {effective_kube_context or 'Default'}")
            typer.echo(f"kubeconfig: {effective_kubeconfig or 'Default'}")
            typer.echo("-------------------------")

        # Get Helm arguments
        set_args, sensitive_values = map_config_to_helm_values(settings)

        values_file_path: str = ""
        if sensitive_values:
            # Create a temporary values file for sensitive data
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as values_file:
                import yaml  # noqa: PLC0415

                yaml.dump(sensitive_values, values_file)
                values_file_path = values_file.name

        try:
            # Build the Helm command
            cmd_args = [
                "helm",
                "upgrade",
                "--install",
                str(release),
                str(chart.path),
                # Use --namespace to ensure release metadata is stored in the same namespace as resources
                # Use --create-namespace to ensure namespace exists before chart creates resources
                "--namespace",
                str(namespace_obj),
                "--create-namespace",
            ]

            # Add sensitive values if any
            if values_file_path:
                cmd_args.extend(["-f", values_file_path])

            # Add kubeconfig if specified
            if effective_kubeconfig:
                cmd_args.extend(["--kubeconfig", effective_kubeconfig])

            # Add context if specified
            if effective_kube_context:
                cmd_args.extend(["--kube-context", effective_kube_context])

            # Add all --set arguments
            for arg in set_args:
                cmd_args.extend(["--set", arg])

            run_helm_command(
                cmd_args=cmd_args,
                kube_context=effective_kube_context,
                kubeconfig=effective_kubeconfig,
                debug=debug,
            )

            typer.echo(
                f"Helm release '{release}' deployed/upgraded successfully in namespace '{namespace_obj}'."
            )
        finally:
            if values_file_path:
                # Clean up the temporary values file
                os.unlink(values_file_path)

    @app.command()
    def uninstall(  # noqa: PLR0913
        release_name: Optional[str] = typer.Option(
            None,
            help="Name of the Helm release to uninstall",
        ),
        namespace: str = typer.Option(
            "",
            help="Kubernetes namespace (defaults to value from config.yaml)",
        ),
        context: Optional[str] = typer.Option(
            None,
            help="Kubernetes context to use. Overrides context from config.yaml.",
        ),
        kubeconfig: Optional[Path] = typer.Option(
            None,
            "--kubeconfig",
            help="Path to the kubeconfig file. Overrides KUBECONFIG from settings.",
        ),
        debug: bool = typer.Option(
            False,
            help="Enable debug output",
        ),
        delete_ns: bool = typer.Option(
            False,
            "--delete-namespace",
            help="Delete the Kubernetes namespace after uninstalling the release.",
        ),
    ) -> None:
        """Uninstall Selenium Grid Helm release."""
        settings = get_settings()
        # Use settings for default release_name if not provided
        effective_release_name = (
            release_name if release_name else settings.kubernetes.SELENIUM_GRID_SERVICE_NAME
        )

        # Validate inputs
        release = K8sName(name=effective_release_name)

        namespace_obj, effective_kube_context, effective_kubeconfig = (
            resolve_namespace_context_and_kubeconfig(
                cli_namespace_arg=namespace,
                cli_kube_context_arg=context,
                cli_kubeconfig_arg=kubeconfig,
                settings=get_settings(),
            )
        )

        if debug:
            typer.echo("--- Debug Information ---")
            typer.echo(f"Release Name: {release}")
            typer.echo(f"Namespace: {namespace_obj}")
            typer.echo(f"Context: {effective_kube_context or 'Default'}")
            typer.echo(f"kubeconfig: {effective_kubeconfig or 'Default'}")
            typer.echo("-------------------------")

        # Build the Helm command
        cmd_args = [
            "helm",
            "uninstall",
            str(release),
            "--namespace",
            str(namespace_obj),
        ]

        if effective_kubeconfig:
            cmd_args.extend(["--kubeconfig", effective_kubeconfig])

        # Add context if specified
        if effective_kube_context:
            cmd_args.extend(["--kube-context", effective_kube_context])

        run_helm_command(
            cmd_args=cmd_args,
            kube_context=effective_kube_context,
            kubeconfig=effective_kubeconfig,
            debug=debug,
        )

        typer.echo(
            f"Helm release '{release}' uninstalled successfully from namespace '{namespace_obj}'."
        )

        if delete_ns:
            delete_namespace(
                str(namespace_obj),
                effective_kube_context,
                effective_kubeconfig,
                debug,
            )

    return app


app = create_application()

if __name__ == "__main__":
    app()
