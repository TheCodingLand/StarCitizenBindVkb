import json
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import ValidationError
from pydantic_settings import BaseSettings

APP_PATH = Path(__file__).parent
DEFAULT_CONFIG_PATH = APP_PATH.parent / "config.json"

_config_path = DEFAULT_CONFIG_PATH

_config_cache: Optional["Config"] = None


def _ensure_config_dir() -> None:
    get_config_path().parent.mkdir(parents=True, exist_ok=True)


def set_config_path(new_path: Union[str, Path]) -> None:
    """Update the configuration file path and clear the in-memory cache."""
    global _config_path, _config_cache
    _config_path = Path(new_path)
    _config_cache = None


def get_config_path() -> Path:
    return _config_path


class Config(BaseSettings):
    installation_path: str = "C:/Program Files/Roberts Space Industries/StarCitizen"
    install_type: Literal["LIVE", "PTU", "EPTU"] = "LIVE"
    joystick_left_name_filter: str = "VKBsim Gladiator EVO L"
    joystick_right_name_filter: str = "VKBsim Gladiator EVO R"
    joystick_type_left: str = "VKBsim Gladiator EVO"
    joystick_type_right: str = "VKBsim Gladiator EVO"
    joystick_instance_left: int = 1
    joystick_instance_right: int = 2
    joystick_side_identifier_left: str = "L"
    joystick_side_identifier_right: str = "R"
    modifier_key: str = "rctrl"

    def save(self) -> None:
        _ensure_config_dir()
        get_config_path().write_text(self.model_dump_json(indent=4))
        self._cache_self()

    def _cache_self(self) -> None:
        global _config_cache
        _config_cache = self

    @classmethod
    def get_config(cls, force_reload: bool = False) -> "Config":
        global _config_cache
        if not force_reload and _config_cache is not None:
            return _config_cache

        config_path = get_config_path()

        if not config_path.exists():
            config = cls()
            _ensure_config_dir()
            config_path.write_text(config.model_dump_json(indent=4))
            config._cache_self()
            return config

        try:
            data = config_path.read_text()
            config_data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid configuration file: {config_path}") from exc

        try:
            config = cls(**config_data)
        except ValidationError as exc:
            raise ValueError(f"Configuration file contains invalid values: {config_path}") from exc

        config._cache_self()
        return config
