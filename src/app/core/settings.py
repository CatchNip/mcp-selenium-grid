"""Core settings for MCP Server."""

import os
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicitly load the correct .env file before any settings are read
env_file = ".env.test" if os.getenv("TESTING") else ".env"
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
    DEPLOYMENT_MODE: str = "docker"  # or "kubernetes"
    K8S_NAMESPACE: str = "selenium-grid"

    # Security Settings
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:8000"],
        json_schema_extra={"env_names": ["ALLOWED_ORIGINS"]},
    )

    # API Token
    API_TOKEN: str = os.getenv("API_TOKEN", "CHANGE_ME")

    @classmethod
    def get_cors_origins(cls, v=None) -> List[str]:
        """Get CORS origins from environment variable."""
        if v is None:
            v = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000")
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v or []


settings = Settings()
