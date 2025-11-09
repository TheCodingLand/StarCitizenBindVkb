from typing import Any, Dict, List
from pydantic import BaseModel, Field, field_validator

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



