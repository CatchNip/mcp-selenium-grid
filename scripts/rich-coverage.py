#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "coverage",
#     "rich",
#     "typer",
# ]
# ///
# https://docs.astral.sh/uv/guides/scripts/#using-a-shebang-to-create-an-executable-file
"""
Runner script for rich_coverage module.

This script exists to provide a convenient way to run the rich_coverage
module during development without including it in the project's build artifacts.

It uses uv's script functionality to manage dependencies automatically and
adds the scripts directory to Python's path to enable module imports.

Usage:
    uv run scripts/rich-coverage.py
    uv run ./scripts/rich-coverage.py --format=html

Lock dependencies (automatic with pre-commit hook):
    uv lock --script scripts/rich-coverage.py

"""

from rich_coverage import rich_coverage_cli

if __name__ == "__main__":
    rich_coverage_cli()
