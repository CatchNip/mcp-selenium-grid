from os import getcwd
from pathlib import Path
from tomllib import load
from typing import Any

ROOT_DIR = Path(getcwd()).resolve()


def load_value_from_toml(
    keys: list[str], file_path: Path = ROOT_DIR / "pyproject.toml", default: Any = None
) -> Any:
    """
    Load a nested value from a TOML file.

    Args:
        keys: List of nested keys to traverse.
        file_path: Path to the TOML file.
        default: Value to return if keys not found.

    Returns:
        The value from the TOML file.

    Raises:
        FileNotFoundError: If the file doesn't exist and no default is provided.
        ValueError: If the keys are missing and no default is provided.
    """
    if not file_path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"{file_path} not found")

    try:
        with file_path.open("rb") as f:
            data = load(f)
        for key in keys:
            data = data[key]
        return data
    except KeyError:
        if default is not None:
            return default
        raise ValueError(f"Keys {'.'.join(keys)} not found in {file_path}")
    except Exception as e:
        raise ValueError(f"Error reading {file_path}: {e}") from e
