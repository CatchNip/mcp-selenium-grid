#!/usr/bin/env python3
"""CLI for deploying Selenium Grid using Helm."""

import os
import tempfile
from functools import lru_cache
from pathlib import Path

import typer

from app.core.settings import Settings

from ..constants import CLI_TITLE
from .cli.helm import run_helm_command
from .cli.kubectl import delete_namespace
from .constants import HELM_CLI_DESC, HELM_SHORT_HELP
from .helpers import map_config_to_helm_values


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def create_application() -> typer.Typer:  # noqa: PLR0915
    """Create Typer application for Helm Selenium Grid deployment."""
    app = typer.Typer(
        name="helm-selenium-grid",
        help=f"{CLI_TITLE} - {HELM_SHORT_HELP}\n{HELM_CLI_DESC}",
        short_help=HELM_SHORT_HELP,
    )
    settings = get_settings()

    @app.command()  # TODO: run deploy and fix namespace already exists after uninstall with --delete-namespace
    def deploy(  # noqa: PLR0913
        chart_path: Path = typer.Option(
            "deployment/helm/selenium-grid",
            help="Path to the Helm chart",
            exists=True,
            dir_okay=True,
            file_okay=False,  # Ensure it's a directory
            readable=True,
        ),
        release_name: str = typer.Option(
            settings.kubernetes.SELENIUM_GRID_SERVICE_NAME,
            help="Name of the Helm release",
        ),
        namespace: str = typer.Option(
            settings.kubernetes.NAMESPACE,
            help="Kubernetes namespace",
        ),
        context: str = typer.Option(
            settings.kubernetes.CONTEXT,
            help="Kubernetes context to use",
        ),
        kubeconfig: Path = typer.Option(
            settings.kubernetes.KUBECONFIG,
            "--kubeconfig",
            help="Path to the kubeconfig file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
        debug: bool = typer.Option(
            False,
            help="Enable debug output",
        ),
    ) -> None:
        """Deploy Selenium Grid using Helm CLI."""
        kubeconfig_expanduser_str = str(kubeconfig.expanduser())

        if debug:
            typer.echo("--- Debug Information ---")
            typer.echo(f"Chart: {chart_path}")
            typer.echo(f"Release Name: {release_name}")
            typer.echo(f"Namespace: {namespace}")
            typer.echo(f"Context: {context or 'Default'}")
            typer.echo(f"kubeconfig: {kubeconfig_expanduser_str or 'Default'}")
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
                str(release_name),
                str(chart_path),
                # Use --namespace to ensure release metadata is stored in the same namespace as resources
                # Use --create-namespace to ensure namespace exists before chart creates resources
                "--namespace",
                str(namespace),
                "--create-namespace",
            ]

            # Add sensitive values if any
            if values_file_path:
                cmd_args.extend(["-f", values_file_path])

            # Add kubeconfig if specified
            if kubeconfig_expanduser_str:
                cmd_args.extend(["--kubeconfig", kubeconfig_expanduser_str])

            # Add context if specified
            if context:
                cmd_args.extend(["--kube-context", context])

            # Add all --set arguments
            for arg in set_args:
                cmd_args.extend(["--set", arg])

            run_helm_command(
                cmd_args=cmd_args,
                kube_context=context,
                kubeconfig=kubeconfig_expanduser_str,
                debug=debug,
            )

            typer.echo(
                f"Helm release '{release_name}' deployed/upgraded successfully in namespace '{namespace}'."
            )
        finally:
            if values_file_path:
                # Clean up the temporary values file
                os.unlink(values_file_path)

    @app.command()
    def uninstall(  # noqa: PLR0913
        release_name: str = typer.Option(
            settings.kubernetes.SELENIUM_GRID_SERVICE_NAME,
            help="Name of the Helm release to uninstall",
        ),
        namespace: str = typer.Option(
            settings.kubernetes.NAMESPACE,
            help="Kubernetes namespace",
        ),
        context: str = typer.Option(
            settings.kubernetes.CONTEXT,
            help="Kubernetes context to use.",
        ),
        kubeconfig: Path = typer.Option(
            settings.kubernetes.KUBECONFIG,
            "--kubeconfig",
            help="Path to the kubeconfig file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
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
        kubeconfig_expanduser_str = str(kubeconfig.expanduser())

        if debug:
            typer.echo("--- Debug Information ---")
            typer.echo(f"Release Name: {release_name}")
            typer.echo(f"Namespace: {namespace}")
            typer.echo(f"Context: {context or 'Default'}")
            typer.echo(f"kubeconfig: {kubeconfig_expanduser_str or 'Default'}")
            typer.echo("-------------------------")

        # Build the Helm command
        cmd_args = [
            "helm",
            "uninstall",
            str(release_name),
            "--namespace",
            str(namespace),
        ]

        if kubeconfig_expanduser_str:
            cmd_args.extend(["--kubeconfig", kubeconfig_expanduser_str])

        # Add context if specified
        if context:
            cmd_args.extend(["--kube-context", context])

        run_helm_command(
            cmd_args=cmd_args,
            kube_context=context,
            kubeconfig=kubeconfig_expanduser_str,
            debug=debug,
        )

        typer.echo(
            f"Helm release '{release_name}' uninstalled successfully from namespace '{namespace}'."
        )

        if delete_ns:
            delete_namespace(
                str(namespace),
                context,
                kubeconfig_expanduser_str,
                debug,
            )

    return app


app = create_application()

if __name__ == "__main__":
    app()
