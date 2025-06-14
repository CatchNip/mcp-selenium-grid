"""Models for Helm Selenium Grid deployment."""

import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class K8sName(BaseModel):
    """Kubernetes resource name with validation."""

    name: str = Field(..., description="Kubernetes resource name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate Kubernetes resource name format."""
        K8S_NAME_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
        MAX_NAME_LENGTH = 63

        if not re.match(K8S_NAME_PATTERN, v):
            raise ValueError(f"Invalid name: {v}")
        if len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"Name too long (max {MAX_NAME_LENGTH} characters)")
        return v

    def __str__(self) -> str:
        return self.name


class HelmChartPath(BaseModel):
    """Helm chart path with validation."""

    path: Path = Field(..., description="Path to the Helm chart")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: Path) -> Path:
        """Validate Helm chart path exists and is within project directory."""
        if not v.is_absolute():
            v = v.resolve()

        project_root = Path(__file__).parent.parent.parent
        try:
            v.relative_to(project_root)
        except ValueError:
            raise ValueError(f"Helm chart path {v} is outside project directory")

        if not v.exists():
            raise FileNotFoundError(f"Helm chart directory not found at {v}")
        return v
