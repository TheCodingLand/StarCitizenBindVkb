from typing import Literal, Protocol
from scdatatools.sc import StarCitizen # type ignore # requries scdatatools in PYTHONPATH
import json
from typing import Literal, Union
from pathlib import Path
import os


current_folder = Path(__file__).parent.parent

EmbeddedDictOrListType = Union[dict[str, "EmbeddedDictOrListType"], list["EmbeddedDictOrListType"], str, int, float, bool, None]

class Profile(Protocol):
    json: dict[str, EmbeddedDictOrListType]
   

class StarCitizenType(Protocol):
    default_profile: Profile
    version_label: str
   

def gen_actionmap(self: "Profile", language: Literal["fr", "en"] | None = None) -> dict[str, dict[str, dict[str, dict[str, str | dict[str, str]]]]]:
    m = {}
    for am in self.json["profile"]["actionmap"]:
        category = (
            am["@UICategory"] if "@UICategory" in am else "Other"
        )
        
        if "@UILabel" in am and am["@UILabel"] is not None:
            label = am["@UILabel"]
        else:
            label = am["@name"]

        if category not in m:
            m[category] = {}

        if label not in m[category]:
            m[category][label] = {}

        if "action" not in am:
            continue

        if not isinstance(am["action"], list):
            am["action"] = [am["action"]]

        for a in am["action"]:
            
            al = (
                a["@name"] if "@UILabel" in a and a["@UILabel"] is not None else a["@name"]
            )
            
            m[category][label][al] = a
          
    return m




for version in ["PTU", "LIVE"]:
    sc : StarCitizenType = StarCitizen(f'{sc_folder}/{version}')
    profile = sc.default_profile
    v_label: str  = sc.version_label
    output_folder = f"{current_folder}/data/{version}/{v_label}"
    os.makedirs(output_folder, exist_ok=True)    
    with open(f"{output_folder}/actionmap.json", "w") as f:
        f.write(json.dumps(gen_actionmap(profile), indent=4)) # type: ignore