import os
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel

from app.localization import LocalizationFile

InstallationTypes = "PTU", "LIVE", "EPTU"

SC_FOLDER = "F:/Star Citizen/StarCitizen"


class StarCitizenInstallation(BaseModel):
    path: str
    version: str
    exported_control_maps: List[str]
    type: Literal["PTU", "LIVE", "EPTU"]


APP_PATH = Path(__file__).parent
localization_file_path = APP_PATH / "data" / "Localization" / "english" / "global.ini"
localization_file = LocalizationFile.from_file(localization_file_path)


def get_installation(
    sc_folder: str, installation_type: Literal["PTU", "LIVE", "EPTU"]
) -> StarCitizenInstallation | None:
    installation_path = os.path.join(sc_folder, installation_type)
    if os.path.exists(installation_path) and is_valid_star_citizen_installation(
        Path(installation_path)
    ):
        exported_control_maps = user_exported_control_mappings(installation_path)
        return StarCitizenInstallation(
            path=installation_path,
            version=os.path.basename(installation_path),
            exported_control_maps=exported_control_maps,
            type=installation_type,
        )
    return None


def user_exported_control_mappings(installation: str) -> List[str]:
    # F:/Star Citizen/StarCitizen/PTU/user/client/0/controls/mappings
    exported_control_path = os.path.join(
        installation, "user", "client", "0", "controls", "mappings"
    )
    # find each xml file, and return the paths
    paths: List[str] = []
    for root, _, files in os.walk(exported_control_path):
        for file in files:
            if file.endswith(".xml"):
                paths.append(os.path.join(root, file))
    return paths


def is_valid_star_citizen_installation(path: Path) -> bool:
    # Implement logic to verify if the directory is a valid installation
    # For example, check for specific files or folders

    if not (path / "Data.p4k").exists():
        return False
    return True
