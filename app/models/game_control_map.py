from typing import  Dict, List, TypeVar
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

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
    #{'states': {'state': [...]}, '@name': 'v_toggle_all_doors', '@activationMode': 'press', '@keyboard': ' ', '@gamepad': ' ', '@joystick': ' ', '@UILabel': '@ui_CICockpitDoorsToggleAll', '@UIDescription': '@ui_CICockpitDoorsToggleAllDesc', '@Category': 'VehicleActions'}
 
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
    
