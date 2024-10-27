
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from rich import inspect
current_path= Path(__file__).parent
actionmaps_path = current_path / 'data' / 'actionmap.json'
actionmaps = json.loads(actionmaps_path.read_text())
from pydantic import BaseModel, Field, field_validator
#{'Emergency Exit Seat': {'activationmode': 'tap', 'keyboard': 'u+lshift', 'joystick': ' ', 'uidescription': 'Press LShift + H to engage emergency exit'}, 'Eject': {'activationmode': 'press', 'keyboard': 'ralt+y', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_ciejectdesc', 'category': 'playeractions'}, 'Look behind': {'activationmode': 'delayed_hold_no_retrigger', 'keyboard': 'comma', 'joystick': ' ', 'gamepad': 'shoulderl+a', 'uidescription': '@ui_cilookbehinddesc'}, '@ui_ciminingmode': {'activationmode': 'press', 'keyboard': 'm', 'gamepad': ' ', 'joystick': ' ', 'uidescription': 'Mining Mode Toggle', 'category': 'shipsystems'}, '@ui_cisalvagemode': {'activationmode': 'press', 'keyboard': 'm', 'gamepad': ' ', 'joystick': ' ', 'uidescription': 'Activate salvage mode when seated.', 'category': 'shipsystems'}, '@ui_ciscanningmode': {'activationmode': 'press', 'keyboard': 'v', 'gamepad': 'dpad_right', 'joystick': ' ', 'uidescription': '@ui_ciscanningmodedesc', 'category': 'shipsystems'}, '@ui_ciquantumtravelsystemtoggle': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_ciquantumtravelsystemtoggledesc', 'category': 'shipsystems'}, '@ui_cimissilemode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_cimissilemodedesc', 'category': 'shipsystems'}, '@ui_v_toggle_guns_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_toggle_guns_mode_desc', 'category': 'shipsystems'}, '@ui_v_toggle_flight_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_toggle_flight_mode_desc', 'category': 'shipsystems'}, '@ui_v_set_mining_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_set_mining_mode_desc'}, '@ui_v_set_salvage_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_set_salvage_mode_desc'}, '@ui_v_set_scan_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_set_scan_mode_desc'}, '@ui_v_set_quantum_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_set_quantum_mode_desc'}, '@ui_v_set_missile_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_set_missile_mode_desc'}, '@ui_v_set_guns_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_set_guns_mode_desc'}, '@ui_v_set_flight_mode': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_set_flight_mode_desc'}, 'Enter Remote Turret 1': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ ', 'category': 'remoteturret'}, 'Enter Remote Turret 2': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ ', 'category': 'remoteturret'}, 'Enter Remote Turret 3': {'activationmode': 'press', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ ', 'category': 'remoteturret'}, 'Next Operator Mode': {'activationmode': 'tap', 'keyboard': 'mouse3', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_operator_mode_toggle_next_desc', 'category': 'shipsystems'}, 'Previous Operator Mode': {'activationmode': 'tap', 'keyboard': ' ', 'gamepad': ' ', 'joystick': ' ', 'uidescription': '@ui_v_operator_mode_toggle_prev_desc', 'category': 'shipsystems'}}class 

def get_localization_string(string: str ) -> str:
    return string


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
    states: Dict[str, Any] | None = None
    activationmode: str | None = None
    keyboard: InputData | str | None = None
    mouse: InputData | str | None = None
    gamepad: InputData | str | None = None
    joystick: JoyInputValue | str | None = None
    uidescription: str | None = None
    category: str | None = None

    

    @field_validator('name')
    @classmethod
    def localization_validator(cls, value: str):
        if value.startswith('@'):
            value = get_localization_string(value)
            return value
        return value

    @field_validator('gamepad', mode='before')
    @classmethod
    def gamepad_validator(cls, value: str) -> str:
        if isinstance(value, dict):
            if '@input' in value:
                value = value['@input']
            
           
            return value
        return value

possible_actions :List[Action]= []

for main_category, sub_categories in actionmaps.items():
    for sub_category, actions in sub_categories.items():
        for action_label, action in actions.items():
            action = Action(name=action_label,**action)
            possible_actions.append(action)
for action in possible_actions:
    if isinstance(action.joystick, JoyInputValue):
        inspect(action)
    if isinstance(action.joystick, str) and action.joystick not in [' ', None, '']:
        inspect(action)
#inspect(possible_actions)