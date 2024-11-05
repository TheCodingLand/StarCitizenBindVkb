from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypeVar
from xmltodict import parse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.actions import get_all_defined_game_actions

#{'ActionProfiles': {'@version': '1', '@optionsVersion': '2', '@rebindVersion': '2', '@profileName': 'default', 'deviceoptions': {...}, 'options': [...], 'modifiers': None, 'actionmap': [...]}}



class Joystick(BaseModel):
    type: str
    instance: int
    product: str


class Rebind(BaseModel):
    model_config = ConfigDict(extra='allow', populate_by_name=True)
    # {'@input': 'js2_button25'}
    input: str = Field(..., alias="@input")
    multitap: Optional[int] = Field(default=None, alias="@multiTap")


class Action(BaseModel):
    name: str = Field(..., alias="@name")
    title: Optional[str] = Field(None, alias="@title")
    rebind: List[Rebind] = Field([])

TItem = TypeVar("TItem")
class ActionMap(BaseModel):
    name : str = Field(..., alias="@name")
    action: List[Action] = Field(..., alias="action")
    
    @field_validator('action', mode='before')
    @classmethod
    def always_list(cls, item: TItem | List[TItem]) -> List[TItem]:
        if isinstance(item, list):
            return item
        return [item]


class Option(BaseModel):
    model_config = ConfigDict(extra='allow')
    type: str = Field(..., alias="@type")
    instance: int = Field(..., alias="@instance")
    product: str | None = Field(default=None, alias="@Product")


class DeviceOption(BaseModel):
    input: str = Field(..., alias="@input")
    deadzone: Optional[Decimal] = Field(None, alias="@deadzone")

class DeviceOptions(BaseModel):
    #{'@name': ' VKBsim Gladiator EVO R    {0200231D-0000-0000-0000-504944564944}', 'option': [{...}, {...}, {...}, {...}, {...}]}
    name : str = Field(..., alias="@name")  
    option: List[DeviceOption] = Field(..., alias="option")

class ActionProfile(BaseModel):
    version: int = Field(..., alias="@version")
    optionsVersion: int = Field(..., alias="@optionsVersion")
    rebindVersion: int = Field(..., alias="@rebindVersion")
    profileName: str = Field(..., alias="@profileName")
    deviceoptions: List[ DeviceOptions] = Field([], alias="deviceoptions")
    options: List[Option] = Field(..., alias="options")
    modifiers: Any = Field(..., alias="modifiers")
    actionmap: List[ActionMap] = Field(..., alias="actionmap")

class ExportedActionMapsFile(BaseModel):
    version: int = Field(..., alias="@version")
    optionsVersion: int = Field(..., alias="@optionsVersion")
    rebindVersion: int = Field(..., alias="@rebindVersion")
    profileName: str = Field(..., alias="@profileName")
    deviceoptions:  List[DeviceOptions] = Field([])
    options: List[Option] = Field([], alias="options")
    modifiers: Any = Field(..., alias="modifiers")
    actionmap: List[ActionMap] = Field(...)

class ActionMapsFile(BaseModel):
    action_profiles: List[ActionProfile] = Field(..., alias="ActionProfiles")

data_folder = Path(__file__).parent / "data"
action_maps_file_souce = data_folder / "actionmaps.xml"

def get_action_maps_file(source_file: str) -> Dict[str, Any]:
    with open(source_file) as f:
        return parse(f.read(), force_list=True)['ActionMaps'][0]
    
 
class JoystickBind(BaseModel):   
    axis_or_button: str
    modifier_str: Optional[str] = Field(default=None)
    modifier: Literal[None, "HOLD", "DOUBLE_TAP", "MODIFIER"]
    action: str 
    @classmethod
    def from_rebind(cls, bind: Rebind) -> "JoystickBind":
        # ex : 'js2_button8'}
        """
        </action>
        <action name="v_afterburner">
            <rebind input="js2_button3"/>
        </action>
        <action name="v_atc_loading_area_request">
            <rebind input="js2_button4" multiTap="2"/>
        </action>
        <rebind input="js1_rctrl+button10"/>
        <action name=v_target_toggle_pin_index_1_hold>
            <rebind input="js1_button10"/>
        </action>
        """
        if "+" in bind.input:
            modifier_str, action = bind.input.split("+")
            modifier = "MODIFIER"
        else:
            modifier_str = None
            action = bind.input
            modifier = None
        return cls(axis_or_button=bind.input, modifier_str=modifier_str, modifier=modifier, action=action)


def get_exported_action_map_file(action_maps_file_source: str) -> ExportedActionMapsFile:
    return ExportedActionMapsFile(**get_action_maps_file(action_maps_file_source))

def get_action_maps_object(action_maps_file_source: str) -> ExportedActionMapsFile:
    return ExportedActionMapsFile(**get_action_maps_file(action_maps_file_source))

if __name__ == "__main__":
    
    
    all_defined_game_actions = get_all_defined_game_actions()
    x = get_action_maps_file(action_maps_file_souce)
    name_action_mapping = { action.name: action for action in all_defined_game_actions.values()}
    x = ActionMapsFile(**x)
    for option in x.action_profiles[0].actionmap:
        for action in option.action:

            if action.name in name_action_mapping:
                print(option.name)
            
        
        print(option)
    print(x)