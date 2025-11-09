from typing import Any, Dict, List, Literal, Protocol, TypeVar
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator
from scdatatools.sc import StarCitizen # type ignore # requries scdatatools in PYTHONPATH
import json
from typing import Literal, Union
from pathlib import Path
import os
from app.models.full_game_control_options import GameActionMap

current_folder = Path(__file__).parent.parent

EmbeddedDictOrListType = Union[dict[str, "EmbeddedDictOrListType"], list["EmbeddedDictOrListType"], str, int, float, bool, None]

class Profile(Protocol):
    json: dict[str, EmbeddedDictOrListType]
   
class StarCitizenType(Protocol):
    default_profile: Profile
    version_label: str
   



def gen_actionmap(self: "Profile") -> dict[str, Dict[str, Any]]:
    m = {}
    
    for am in self.json["profile"]["actionmap"]:
        
        gam = GameActionMap(**am)
        m.update({gam.name: gam.model_dump()})
    return m


if __name__ == "__main__":
    sc_folder= "f:/Star Citizen/StarCitizen"
    #sc_folder = f"{current_folder}/app/data"
    for version in ["PTU", "LIVE"]:
        sc : StarCitizenType = StarCitizen(f'{sc_folder}/{version}')
        profile = sc.default_profile
        v_label: str  = sc.version_label
        output_folder = f"{current_folder}/data/{version}/{v_label}"
        os.makedirs(output_folder, exist_ok=True)    
        action_map = gen_actionmap(profile)
        with open(f"{output_folder}/actionmap.json", "w") as f:
            f.write(json.dumps(action_map, indent=4))# type: ignore