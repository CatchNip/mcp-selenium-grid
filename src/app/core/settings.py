"""Core settings for MCP Server."""

from os import getenv
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.env_helpers import getenv_as_bool

if getenv_as_bool("TESTING"):
    # If we are testing, variables are already loaded using pyproject.toml
    env_file = ""
else:
    # Explicitly load the correct .env file before any settings are read
    env_file = ".env.dev" if getenv_as_bool("DEVELOPMENT") else ".env"
    load_dotenv(dotenv_path=env_file, override=False)


class Settings(BaseSettings):
    """MCP Server settings."""

    model_config = SettingsConfigDict(env_file=env_file, case_sensitive=True, extra="ignore")

    def __init__(self, **data):
        super().__init__(**data)
        self.BACKEND_CORS_ORIGINS = self.get_cors_origins()

    # API Settings
    PROJECT_NAME: str = "MCP Selenium Server"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Selenium Settings
    SELENIUM_HUB_PORT: int = 4444
    SELENIUM_HUB_BASE_URL: str = f"http://localhost:{SELENIUM_HUB_PORT}"
    MAX_BROWSER_INSTANCES: Optional[int] = None

    # Deployment Settings
    # If the server is running in Docker, we can't use docker to manage the hub
    # and nodes, so we need to use Kubernetes instead.
    if getenv_as_bool("IS_RUNNING_IN_DOCKER"):
        DEPLOYMENT_MODE: str = "kubernetes"
    else:
        DEPLOYMENT_MODE: str = "docker"

    K8S_NAMESPACE: str = "selenium-grid"

    # Security Settings
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:8000"],
        json_schema_extra={"env_names": ["ALLOWED_ORIGINS"]},
    )

    # API Token
    API_TOKEN: str = getenv("API_TOKEN", "CHANGE_ME")

    @classmethod
    def get_cors_origins(cls, v=None) -> List[str]:
        """Get CORS origins from environment variable."""
        if v is None:
            v = getenv("ALLOWED_ORIGINS", "http://localhost:8000")
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v or []


settings = Settings()
