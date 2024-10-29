from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypeVar
from xmltodict import parse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from actions import get_all_defined_game_actions

#{'ActionProfiles': {'@version': '1', '@optionsVersion': '2', '@rebindVersion': '2', '@profileName': 'default', 'deviceoptions': {...}, 'options': [...], 'modifiers': None, 'actionmap': [...]}}



class Joystick(BaseModel):
    type: str
    instance: int
    product: str


class Rebind(BaseModel):
    # {'@input': 'js2_button25'}
    input: str = Field(..., alias="@input")
    multitap: Optional[int] = Field(default=None, alias="multiTap")
    
    

class Action(BaseModel):
    name: str = Field(..., alias="@name")
    rebinding: Rebind | List[Rebind] = Field(..., alias="rebind")

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
    "[{'@type': 'keyboard', '@instance': '1', '@Product': 'Clavier  {6F1D2B61-D5A0-11CF-BFC7-444553540000}'}]"
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
    

    
    @field_validator('deviceoptions', mode='before')
    @classmethod
    def always_list_device_options(cls, item: TItem | List[TItem]) -> List[TItem]:
        if isinstance(item, list):
            return item
        return [item]
    
    @field_validator('options', mode='before')
    @classmethod
    def always_list_options(cls, item: TItem | List[TItem]) -> List[TItem]:
        if isinstance(item, list):
            return item
        return [item]
    @field_validator('actionmap', mode='before')
    @classmethod
    def always_list_actionmap(cls, item: TItem | List[TItem]) -> List[TItem]:
        if isinstance(item, list):
            return item
        return [item]

class ExportedActionMapsFile(BaseModel):
    version: int = Field(..., alias="@version")
    optionsVersion: int = Field(..., alias="@optionsVersion")
    rebindVersion: int = Field(..., alias="@rebindVersion")
    profileName: str = Field(..., alias="@profileName")
    deviceoptions:  List[DeviceOptions] = Field([])
    options: List[Option] = Field([], alias="options")
    modifiers: Any = Field(..., alias="modifiers")
    actionmap: List[ActionMap] = Field(...)

    @field_validator('deviceoptions', mode='before')
    @classmethod
    def always_list_device_options(cls, item: TItem | List[TItem]) -> List[TItem]:
        if isinstance(item, list):
            return item
        return [item]
    
    @field_validator('options', mode='before')
    @classmethod
    def always_list_options(cls, item: TItem | List[TItem]) -> List[TItem]:
        if isinstance(item, list):
            return item
        return [item]
    @field_validator('actionmap', mode='before')
    @classmethod
    def always_list_actionmap(cls, item: TItem | List[TItem]) -> List[TItem]:
        if isinstance(item, list):
            return item
        return [item]
class ActionMapsFile(BaseModel):
    action_profiles: ActionProfile = Field(..., alias="ActionProfiles")

data_folder = Path(__file__).parent / "data"
action_maps_file_souce = data_folder / "actionmaps.xml"

def get_action_maps_file(source_file: str) -> Dict[str, Any]:
    with open(source_file) as f:
        return parse(f.read())['ActionMaps']
    
 

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


def get_exported_action_map_file(action_maps_file_souce: str) -> ExportedActionMapsFile:
    return ExportedActionMapsFile(**get_action_maps_file(action_maps_file_souce))

def get_action_maps_object(action_maps_file_souce: str) -> ExportedActionMapsFile:
    return ExportedActionMapsFile(**get_action_maps_file(action_maps_file_souce))

if __name__ == "__main__":
    
    
    all_defined_game_actions = get_all_defined_game_actions()
    x = get_action_maps_file()
    name_action_mapping = { action.name: action for action in all_defined_game_actions}
    x = ActionMapsFile(**x)
    for option in x.action_profiles.actionmap:
        for action in option.action:

            if action.name in name_action_mapping:
                print(option.name)
            
        
        print(option)
    print(x)