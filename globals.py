
import os
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, Field

InstallationTypes = 'PTU', 'LIVE'

class StarCitizenInstallation(BaseModel):
    path: str
    version: str
    exported_control_maps:  List[str]
    type: Literal['PTU', 'LIVE']

SC_FOLDER = "F:/Star Citizen/StarCitizen"

APP_PATH = Path(__file__).parent

def get_installation(installation_type: Literal["PTU", "LIVE"]) -> StarCitizenInstallation | None:
    installation_path = os.path.join(SC_FOLDER, installation_type)
    if os.path.exists(installation_path) and os.path.isfile(f"{installation_path}/Data.p4k"):
        exported_control_maps = user_exported_control_mappings(installation_path)
        return StarCitizenInstallation(path=installation_path, version=os.path.basename(installation_path), exported_control_maps=exported_control_maps, type=installation_type)


def user_exported_control_mappings(installation: str) -> List[str]:
    #F:/Star Citizen/StarCitizen/PTU/user/client/0/controls/mappings
    exported_control_path = os.path.join(installation, 'user', 'client', '0', 'controls', 'mappings')
    # find each xml file, and return the paths
    paths : List[str] =  []
    for root, _, files in os.walk(exported_control_path):
        for file in files:
            if file.endswith('.xml'):
                paths.append(os.path.join(root, file))
    return paths
    
        
