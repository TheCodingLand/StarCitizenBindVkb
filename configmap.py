from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from xmltodict import parse
from pydantic import BaseModel, Field

#{'ActionProfiles': {'@version': '1', '@optionsVersion': '2', '@rebindVersion': '2', '@profileName': 'default', 'deviceoptions': {...}, 'options': [...], 'modifiers': None, 'actionmap': [...]}}



class Joystick(BaseModel):
    type: str
    instance: int
    product: str
"""
64 validation errors for ActionMapsFile
ActionProfiles.actionmap.0.@name.[key]
  Input should be a valid dictionary or instance of Action [type=model_type, input_value='@name', input_type=str]
    For further information visit https://errors.pydantic.dev/2.9/v/model_type
""" 

class Rebind(BaseModel):
    # {'@input': 'js2_button25'}
    input: str = Field(..., alias="@input")
    multitap: Optional[int] = Field(default=None, alias="multiTap")
    
    

class Action(BaseModel):
    name: str = Field(..., alias="@name")
    rebinding: Rebind | List[Rebind] = Field(..., alias="rebind")


class ActionMap(BaseModel):
    name : str = Field(..., alias="@name")
    action: List[Action] | Action = Field(..., alias="action")


class Option(BaseModel):
    "[{'@type': 'keyboard', '@instance': '1', '@Product': 'Clavier  {6F1D2B61-D5A0-11CF-BFC7-444553540000}'}]"
    type: str = Field(..., alias="@type")
    instance: int = Field(..., alias="@instance")
    product: str= Field(default=None, alias="@Product")

class DeviceOption(BaseModel):
    input: str = Field(..., alias="@input")
    deadzone: Decimal = Field(..., alias="@deadzone")

class DeviceOptions(BaseModel):
    #{'@name': ' VKBsim Gladiator EVO R    {0200231D-0000-0000-0000-504944564944}', 'option': [{...}, {...}, {...}, {...}, {...}]}
    name : str = Field(..., alias="@name")  
    option: List[DeviceOption] = Field(..., alias="option")

class ActionProfile(BaseModel):
    version: int = Field(..., alias="@version")
    optionsVersion: int = Field(..., alias="@optionsVersion")
    rebindVersion: int = Field(..., alias="@rebindVersion")
    profileName: str = Field(..., alias="@profileName")
    deviceoptions: DeviceOptions = Field(..., alias="deviceoptions")
    options: List[Option] = Field(..., alias="options")
    modifiers: Any = Field(..., alias="modifiers")
    actionmap: List[ActionMap] = Field(..., alias="actionmap")



class ActionMapsFile(BaseModel):
    action_profiles: ActionProfile = Field(..., alias="ActionProfiles")

data_folder = Path(__file__).parent / "data"
action_maps_file_souce = data_folder / "actionmaps.xml"

def get_action_maps_file() -> Dict[str, Any]:
    with open(action_maps_file_souce) as f:
        return parse(f.read())['ActionMaps']
    
def datamodel_generate():
    action_maps_file = get_action_maps_file()
    print(action_maps_file)    



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


if __name__ == "__main__":
    
    x = get_action_maps_file()
    x = ActionMapsFile(**x)
    for option in x.action_profiles.actionmap:
        print(option)
    print(x)