
import json
from typing import Any, Dict, List
from app.globals import APP_PATH

from pydantic import BaseModel, Field, field_validator
from app.models.game_control_map import  AllActionMaps, GameAction

SC = "LIVE"
SC_VERSION = "sc-alpha-3.24.2-9381373"
sc_actionmaps_path = APP_PATH / 'data' / 'LIVE' /SC_VERSION / f"actionmap.json"

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


def get_all_defined_game_actions() -> Dict[str, List[GameAction]]:
    # returns action names str, adds main_category and sub_category to the actionmap
    output= {}

    actionmaps: Dict[str, Dict[str, Dict[str, str]]] = json.loads(sc_actionmaps_path.read_text())
    aam = AllActionMaps.model_validate(actionmaps)
    for main_cat, actionmap in aam.root.items():
        sub_category = actionmap.name
        for action in actionmap.action:
            if action.name not in output:
                output[action.name] = []
            output[action.name].append(GameAction(main_category=main_cat, sub_category=sub_category, **action.model_dump(exclude_none=True)))
    return output


def get_all_subcategories_actions() -> AllActionMaps:
    actionmaps: Dict[str, Dict[str, Dict[str, str]]] = json.loads(sc_actionmaps_path.read_text())
    aam = AllActionMaps.model_validate(actionmaps)
    return aam


    # for main_category, controlmap in actionmaps.items():
    #     for cm in controlmap.actions:
    #         subcat_actions[sub_category] = {}
    #         for action_label, action in actions.items():
    #             subcat_actions[sub_category][action_label] = Action(name=action_label, main_category=main_category, sub_category=sub_category,**action)
    # return subcat_actions
    


if __name__ == "__main__":
    x= get_all_defined_game_actions()
    print (x)
    for action in x.values():
        if action.joystick and action.joystick not in [' ', '',None]:
            print (action.name)
            print(action.joystick)
