from shutil import which


def which_or_raise(name: str) -> str:
    path: str | None = which(name)
    if path is None:
        raise FileNotFoundError(f"Executable '{name}' not found in PATH")
    return path
