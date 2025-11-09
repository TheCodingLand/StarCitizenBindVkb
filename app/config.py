import json
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings

APP_PATH = Path(__file__).parent    


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

    def save(self):
        with open(APP_PATH.parent / "config.json", "w") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def get_config(cls) -> "Config":
        if not (APP_PATH.parent / "config.json").exists():
            with open(APP_PATH.parent / "config.json", "w") as f:
                f.write(cls().model_dump_json(indent=4))
        with open(APP_PATH.parent / "config.json", "r") as f: # should be next to the executable
            config_data = json.load(f)
        return cls(**config_data)