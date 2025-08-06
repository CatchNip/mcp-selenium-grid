from shutil import which

from typer import Exit, echo


def ensure_cli_installed(cli_name: str, install_instructions: str) -> str:
    """Check if a CLI tool is installed and return its path.

    Raises:
        typer.Exit: If the CLI tool is not installed or not in PATH.
    """
    cli_path: str | None = which(cli_name)
    if not cli_path:
        echo(
            f"Error: {cli_name.capitalize()} CLI is not installed or not in PATH.\n"
            f"{install_instructions}",
            err=True,
        )
        raise Exit(code=1)
    return cli_path
