from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path
from tomllib import load
from typing import Any, Iterator


@contextmanager
def find_pyproject_toml() -> Iterator[Path]:
    """
    Finds the pyproject.toml file and yields its Path.
    Uses a context manager to handle temporary files created by as_file().
    """
    try:
        # Get the Traversable object for the pyproject.toml file.
        resource_path = files(__package__).joinpath("pyproject.toml")
        if resource_path.is_file():
            # Use as_file() to get a Path object to the resource.
            # This is done within a context manager for proper cleanup.
            with as_file(resource_path) as file_path:
                yield file_path
            return
    except (ImportError, TypeError, AttributeError):
        # Fallback for non-packaged or single-script scenarios.
        pass

    # Fallback logic
    current_dir = Path(__file__).resolve()
    for parent in current_dir.parents:
        potential_path = parent / "pyproject.toml"
        if potential_path.is_file():
            yield potential_path
            return

    raise FileNotFoundError("Could not find pyproject.toml")


def load_value_from_toml(keys: list[str], default: Any = None) -> Any:
    """
    Load a nested value from a TOML file.
    """
    with find_pyproject_toml() as file_path:
        with file_path.open("rb") as f:
            data = load(f)

        try:
            for key in keys:
                data = data[key]
            return data
        except KeyError:
            if default is not None:
                return default
            raise ValueError(f"Keys {'.'.join(keys)} not found in {file_path}")
        except Exception as e:
            raise ValueError(f"Error reading {file_path}: {e}") from e
