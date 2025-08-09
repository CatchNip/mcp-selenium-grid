from pathlib import Path
from tomllib import load
from typing import Any


def find_pyproject_toml() -> Path:
    """
    Walks up the directory tree to find the project root
    by looking for a pyproject.toml file.
    """
    project_root = None

    current_dir = Path(__file__).resolve()
    for parent in current_dir.parents:
        if (parent / "pyproject.toml").is_file(follow_symlinks=False):
            project_root = parent
            break

    if project_root:
        return project_root / "pyproject.toml"
    return Path()


def load_value_from_toml(keys: list[str], default: str = "") -> Any:
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
    file_path = find_pyproject_toml()

    if not file_path.is_file(follow_symlinks=False):
        if default:
            return default
        raise FileNotFoundError("File pyproject.toml not found")

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
