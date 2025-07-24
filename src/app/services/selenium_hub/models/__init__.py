"""
Core models and base settings for the Selenium Hub service.

This module defines the deployment mode enumeration and the base settings class
used throughout the Selenium Hub configuration system.
"""

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, PrivateAttr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class DeploymentMode(str, Enum):
    """
    Enum representing the deployment mode for the Selenium Hub service.

    Used to distinguish between Docker and Kubernetes deployment environments.
    """

    DOCKER = "docker"
    KUBERNETES = "kubernetes"


class YamlConfigSettingsSourceWithAliases(YamlConfigSettingsSource):
    """
    This class extends the YamlConfigSettingsSource to support key aliasing
    and preserving original keys in the configuration.
    """

    keep_original_keys: list[str]
    _alias_generator: Callable[[str], str]

    def __init__(self, keep_original_keys: list[str] = [], *args: Any, **kwargs: Any) -> None:
        self.keep_original_keys = keep_original_keys
        self._alias_generator = str.upper
        super().__init__(*args, **kwargs)

    def _transform_keys(self, obj: Any, depth: int = 0, max_depth: int = 2) -> dict[str, Any]:
        if depth >= max_depth:
            # Return the object as-is (or wrap in "value" if needed)
            return obj if isinstance(obj, dict) else {"value": obj}

        match obj:
            case dict():
                result: dict[str, Any] = {}
                for key, value in obj.items():
                    key_str = str(key)
                    if isinstance(value, dict):
                        if key_str in self.keep_original_keys:
                            result[key_str] = self._transform_keys(value, depth + 1, max_depth)
                        else:
                            result[self._alias_generator(key_str)] = self._transform_keys(
                                value, depth + 1, max_depth
                            )
                    else:
                        result[self._alias_generator(key_str)] = value
                return result

            case list():
                return {
                    "items": [
                        self._transform_keys(item, depth + 1, max_depth)
                        if isinstance(item, (dict, list))
                        else {"value": item}
                        for item in obj
                    ]
                }

            case _:
                return {"value": obj}

    def _read_file(self, file_path: Path) -> dict[str, Any]:
        return self._transform_keys(super()._read_file(file_path))


class CustomBaseSettings(BaseSettings):
    _keep_original_keys: list[str] = PrivateAttr(default_factory=list[str])

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        case_sensitive=False,
        # alias_generator=lambda name: name.lower(),
        nested_model_default_partial_update=True,
        extra="ignore",
        env_prefix="",
        env_nested_delimiter="__",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        YamlConfigSettingsSourceWithAliases,
    ]:
        # Make init_settings and env_settings higher priority than YAML
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            YamlConfigSettingsSourceWithAliases(
                settings_cls=settings_cls,
                keep_original_keys=cls._keep_original_keys.get_default(),  # type: ignore
            ),
        )


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        extra="ignore",
    )
