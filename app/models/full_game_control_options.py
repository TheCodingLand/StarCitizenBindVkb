import json
from pathlib import Path
from typing import  Dict, List, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator
from typing import Dict, List
from app.globals import APP_PATH


# control map models imported from star citizen

TItem = TypeVar("TItem")    


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

class Input(CustomBaseModel):
    input: str = Field(..., alias="@input")

class DeviceActivation(CustomBaseModel):
    activationmode: str | None = Field(None, alias="@activationMode")
    input: str |None = Field(None, alias="@input")
    no_modifiers: str | None = Field(None, alias="@noModifiers")
    on_hold: str | None = Field(None, alias="@onHold")
    inputdata: List[Input] | None = Field(None, alias="@inputdata")
    on_press: str | None = Field(None, alias="@onPress")
    on_release: str | None = Field(None, alias="@onRelease")

    @field_validator('inputdata', mode='before')
    @classmethod
    def enforce_list(cls, value: TItem |list[TItem]) -> list[TItem]:
        if isinstance(value, list):
            return value # type: ignore
        if value:
            return [value]
    

class State(CustomBaseModel):    
    name: str = Field(..., alias="@name")
    ui_label: str | None = Field(None, alias="@UILabel")
    
    
class States(CustomBaseModel):
    state: List[State] = Field(...)

class GameAction(CustomBaseModel):  
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    name: str = Field(..., alias="@name")
    activation_mode: None |str = Field(None, alias="@activationMode")

    keyboard: DeviceActivation | str | None = Field(None)
    mouse: DeviceActivation | str | None = Field(None)
    gamepad: DeviceActivation | str | None = Field(None)
    joystick: DeviceActivation | str | None = Field(None)
    states: States | None = Field(None)

    ui_category: str | None = Field(None, alias="@UICategory")
    ui_description: str | None = Field(None, alias="@UIDescription")
    ui_label: str | None = Field(None, alias="@UILabel")
    category: str | None = Field(None, alias="@Category")

    on_press: str | None = Field(None, alias="@onPress")
    on_hold: str | None = Field(None, alias="@onHold")
    on_release: str | None = Field(None, alias="@onRelease")
    hold_trigger_delay: str | None = Field(None, alias="@holdTriggerDelay")
    hold_repead_delay: str | None = Field(None, alias="@holdRepeatDelay")
    retriggerable : str | None = Field(None, alias="@retriggerable")
    use_analog_compare: str | None = Field(None, alias="@useAnalogCompare")
    analog_compare_val: str | None = Field(None, alias="@analogCompareVal")
    analog_compare_op: str | None = Field(None, alias="@analogCompareOp")
    no_modifiers: str | None = Field(None, alias="@noModifiers")

    option_group : str | None = Field(None, alias="@optionGroup")
    always: str | None = Field(None, alias="@always")

    # fields not in schema, added for convenience
    main_category: str | None = Field(None)
    sub_category: str | None = Field(None)

    

    @model_validator(mode='before')
    @classmethod
    def check_xml_errors(cls, data):
        if "@ActivationMode" in data:
            data['@activationMode'] = data.pop("@ActivationMode") # bugs in xml
        if "@activationmode" in data:
            data['@activationMode'] = data.pop("@activationmode") # bugs in xml
        if "@gamepad" in data:
            data['gamepad'] = data.pop("@gamepad")
        if "@joystick" in data:
            data['joystick'] = data.pop("@joystick")
        if "@keyboard" in data:
            data['keyboard'] = data.pop("@keyboard")
        if "@mouse" in data:
            data['mouse'] = data.pop("@mouse")

        return data
    
class GameActionMap(CustomBaseModel):
   
    name: str = Field(..., alias="@name")
    action: List[GameAction] = Field(..., alias="action")
    ui_label: str | None = Field(None, alias="@UILabel")
    ui_category: str | None = Field(None, alias="@UICategory")
    ui_description: str | None = Field(None, alias="@UIDescription")
    version: int  | str | None = Field(None, alias="@version")
    
    #text: str | None = Field(None, alias="#text") # looks like a bug in the xml

    @field_validator('action', mode='before')
    @classmethod
    def enforce_list(cls, value: TItem |list[TItem]) -> list[TItem]:
        if isinstance(value, list):
            return value # type: ignore
        return [value]

    @model_validator(mode='before')
    @classmethod
    def check_xml_errors(cls, data):
        if "@UILable" in data:
            data['@UILabel'] = data.pop("@UILable") # bugs in xml
        if "#text" in data:
            del data["#text"]
        return data
        
AllActionMaps = RootModel[Dict[str, GameActionMap]]
    

def get_sc_actionmaps_path(install_type: Literal['LIVE', 'PTU', 'EPTU']= 'LIVE', sc_version: str = "sc-alpha-3.24.2-9381373") -> Path:
    return APP_PATH / 'data' / install_type / sc_version / f"actionmap.json"


def get_all_defined_game_actions(sc_actionmaps_path: Path = get_sc_actionmaps_path()) -> Dict[str, List[GameAction]]:
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


def get_all_subcategories_actions(sc_actionmaps_path: Path = get_sc_actionmaps_path()) -> AllActionMaps:
    actionmaps: Dict[str, Dict[str, Dict[str, str]]] = json.loads(sc_actionmaps_path.read_text())
    aam = AllActionMaps.model_validate(actionmaps)
    return aam



if __name__ == "__main__":
    x= get_all_defined_game_actions()
    print (x)
    for action in x.values():
        if action.joystick and action.joystick not in [' ', '',None]:
            print (action.name)
            print(action.joystick)
