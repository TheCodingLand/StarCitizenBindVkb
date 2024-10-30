
import json
from pathlib import Path
from typing import Any, Dict, List
from rich import inspect

from globals import APP_PATH
from localization import LocalizationFile

from pydantic import BaseModel, Field, field_validator



SC = "LIVE"
SC_VERSION = "sc-alpha-3.24.2-9381373"
sc_actionmaps_path = APP_PATH / 'data' / 'LIVE' /SC_VERSION / f"actionmap.json"
actionmaps = json.loads(sc_actionmaps_path.read_text())

localization_file_path = APP_PATH / 'data' / 'Localization' / 'english'/ 'global.ini'
localization_file = LocalizationFile.from_file(localization_file_path)


class Input(BaseModel):
     input: str = Field(..., alias='@input')

class InputData(BaseModel):     
    inputdata: Input | List[Input] | None = None 
    activationmode: str | None = Field(None, alias='@activationMode')
    input: str = Field(None, alias='@input')


class JoyInputValue(BaseModel):

    #{'@activationMode': 'press', '@input': ' '}
    activationmode: str | None = Field(None, alias='@activationMode')
    input: str = Field(None, alias='@input')

class Action(BaseModel):    
    name: str
    states: Dict[str, Any] | None = Field(None, alias='@states')
    activationmode: str | None = Field(None, alias='@activationMode')
    keyboard: InputData | str | None = Field(None, alias='@keyboard')
    mouse: InputData | str | None = Field(None, alias='@mouse')
    gamepad: InputData | str | None = Field(None, alias='@gamepad')
    joystick: JoyInputValue | str | None = Field(None, alias='@joystick')
    uidescription: str | None = Field(None, alias='@UIDescription')
    category: str | None = Field(None, alias='@Category')
    ui_label: str | None = Field(None, alias='@UILabel')
    main_category: str = Field(...)
    sub_category: str = Field(...)

    
    @field_validator('name')
    @classmethod
    def localization_validator(cls, value: str):
        if value.startswith('@'):
            #value = localization_file.get_localization_string(value)
            return value[1:]
        return value

    @field_validator('gamepad', mode='before')
    @classmethod
    def gamepad_validator(cls, value: str |  Dict[str, Any]) -> str | Dict[str, Any]:
        if isinstance(value, dict):
            if '@input' in value:
                value = value['@input']
            return value
        return value




def get_all_defined_game_actions() -> Dict[str, Action]:
    possible_actions: List[Action]= []

    for main_category, sub_categories in actionmaps.items():
        for sub_category, actions in sub_categories.items():
            for action_label, action in actions.items():
                action = Action(name=action_label, main_category=main_category, sub_category=sub_category,**action,)
                possible_actions.append(action)
    return {action.name: action for action in possible_actions}


def get_all_subcategories_actions() -> Dict[str, Any]:
    subcat_actions= {}
    for main_category, sub_categories in actionmaps.items():
        for sub_category, actions in sub_categories.items():
            subcat_actions[sub_category] = actions
    return subcat_actions
    


if __name__ == "__main__":
    x= get_all_defined_game_actions()
    print (x)
    for action in x.values():
        if action.joystick and action.joystick not in [' ', '',None]:
            print (action.name)
            print(action.joystick)
