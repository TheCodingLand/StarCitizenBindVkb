

from typing import List, Literal, Optional, Dict

from pydantic import BaseModel, Field



class JoyStickButton(BaseModel):
    name: str  # example: button 3
    sc_config_name: str # simplified name that sc uses like js1_2, where 2 is the button number 2
    coord_x_left: Dict[Literal["left", "right"],int] # x coordinate of the button on the left image
    coord_y_top: int # y coordinate of the button on the left image
    visible: bool = True # whether the button is visible or not, will changed based on different modifiers
    actions: List[str] = [] # the action that is mapped to the button
    modifier: bool = False # the action that is mapped to the button when the modifier is enabled
    


class Joystick(BaseModel):
    buttons: Dict[str, JoyStickButton] = Field(...)
    side: Literal["left", "right"] # left or right joystick

    def clear_mapping(self, label: str, modifier: bool = False) -> None:
        """Clear the action mapping for a specific button."""
        if modifier:
            self.buttons[f"{label}_mod"].actions = []
        else:
            self.buttons[label].actions = []

    def set_mapping(self, label: str, action: str, modifier: bool = False) -> None:
        """Set the action mapping for a specific button."""
        
        if modifier:
            self.buttons[f"{label}_mod"].actions.append(action)
        else:
            self.buttons[label].actions.append(action)
        
        

    def get_mapping(self, label: str, modifier: bool) -> List[str]:
        """Get the action mapping for a specific button."""
        if modifier:
            return self.buttons[f"{label}_mod"].actions
        return self.buttons[label].actions 

    def clear_mappings(self) -> None:
        """Clear all mappings."""
        for mapping in self.buttons.values():
            mapping.actions = []

    def __repr__(self) -> str:
        return f"JoystickConfigModel(buttons={self.buttons})"
    
def get_joystick_buttons() -> Dict[str, JoyStickButton]:
    buttons = [ 
        JoyStickButton(name="hat1_up", sc_config_name="hat1_up", coord_x_left={"left" :265, "right": 1565}, coord_y_top=52),
        JoyStickButton(name="hat1_up_right", sc_config_name="hat1_up_right", coord_x_left={"left" :457, "right": 1755}, coord_y_top=52),
        JoyStickButton(name='hat1_up_left', sc_config_name="hat1_up_left", coord_x_left={"left" :71, "right": 1371}, coord_y_top=52),
        
        JoyStickButton(name="hat1_left", sc_config_name="hat1_left", coord_x_left={"left" :71, "right": 1371}, coord_y_top=87),
        JoyStickButton(name="hat1_right", sc_config_name="hat1_right", coord_x_left={"left" :457, "right": 1755}, coord_y_top=87),
        JoyStickButton(name="hat1_down_left", sc_config_name="hat1_down_left", coord_x_left={"left" :71, "right": 1371}, coord_y_top=122),
        JoyStickButton(name="hat1_down", sc_config_name="hat1_down", coord_x_left={"left" :265, "right": 1565}, coord_y_top=122),
        JoyStickButton(name="hat1_down_right", sc_config_name="hat1_down_right", coord_x_left={"left" :457,"right": 1755}, coord_y_top=122),
        # trigger
        JoyStickButton(name="button1", sc_config_name="button1", coord_x_left={"left": 1545, "right": 278}, coord_y_top=334),
        JoyStickButton(name="button2", sc_config_name="button2", coord_x_left={"left": 1545, "right": 278}, coord_y_top=365),

        # red button
        JoyStickButton(name="button3", sc_config_name="button3", coord_x_left={"left": 457, "right": 1370}, coord_y_top=260),

        # external button
        JoyStickButton(name="button4", sc_config_name="button4", coord_x_left={"left": 1545, "right": 278}, coord_y_top=190),

        # base_button
        JoyStickButton(name="button5", sc_config_name="button5", coord_x_left={"left": 1545, "right": 278}, coord_y_top=419),

        #cross button
        JoyStickButton(name="button6", sc_config_name="button6", coord_x_left={"left": 265, "right": 1562}, coord_y_top=524),
        JoyStickButton(name="button7", sc_config_name="button7", coord_x_left={"left": 457, "right": 1756}, coord_y_top=560),
        JoyStickButton(name="button8", sc_config_name="button8", coord_x_left={"left": 265, "right": 1562}, coord_y_top=592),
        JoyStickButton(name="button9", sc_config_name="button9", coord_x_left={"left": 71, "right": 1370}, coord_y_top=560),
        JoyStickButton(name="button10", sc_config_name="button10", coord_x_left={"left": 265, "right": 1562}, coord_y_top=560),

        # top buttons
        JoyStickButton(name="button11", sc_config_name="button11", coord_x_left={"left": 265,"right": 1562}, coord_y_top=367),
        JoyStickButton(name="button12", sc_config_name="button12", coord_x_left={"left": 457, "right": 1756}, coord_y_top=402),
        JoyStickButton(name="button13", sc_config_name="button13", coord_x_left={"left": 265, "right": 1562}, coord_y_top=437),
        JoyStickButton(name="button14", sc_config_name="button14", coord_x_left={"left": 71, "right": 1370}, coord_y_top=402),
        JoyStickButton(name="button15", sc_config_name="button15", coord_x_left={"left": 265, "right": 1562}, coord_y_top=402),

        # thumb buttons
        JoyStickButton(name="button16", sc_config_name="button16", coord_x_left={"left": 265, "right": 1562}, coord_y_top=683),
        JoyStickButton(name="button17", sc_config_name="button17", coord_x_left={"left": 457, "right": 1756}, coord_y_top=718),
        JoyStickButton(name="button18", sc_config_name="button18", coord_x_left={"left": 265, "right": 1562}, coord_y_top=752),
        JoyStickButton(name="button19", sc_config_name="button19", coord_x_left={"left": 71, "right": 1370}, coord_y_top=718),
        JoyStickButton(name="button20", sc_config_name="button20", coord_x_left={"left": 265, "right": 1562}, coord_y_top=718),

        # upper trigger
        JoyStickButton(name="button21", sc_config_name="button21", coord_x_left={"left": 1545, "right": 278}, coord_y_top=243),
        JoyStickButton(name="button22", sc_config_name="button22", coord_x_left={"left": 1545, "right": 278}, coord_y_top=278),

        # encoders 1
        JoyStickButton(name="button23", sc_config_name="button23", coord_x_left={"left": 1389, "right": 123}, coord_y_top=614),
        JoyStickButton(name="button24", sc_config_name="button24", coord_x_left={"left": 1389, "right": 123}, coord_y_top=648),
        # encoder 2
        JoyStickButton(name="button25", sc_config_name="button25", coord_x_left={"left": 1740, "right": 471}, coord_y_top=614),
        JoyStickButton(name="button26", sc_config_name="button26", coord_x_left={"left": 1740, "right": 471}, coord_y_top=648),
        # base buttons
        JoyStickButton(name="button27", sc_config_name="button27", coord_x_left={"left": 1354, "right": 85}, coord_y_top=505),
        JoyStickButton(name="button28", sc_config_name="button28", coord_x_left={"left": 1545, "right": 278}, coord_y_top=505),
        JoyStickButton(name="button29", sc_config_name="button29", coord_x_left={"left": 1740, "right": 471}, coord_y_top=505),

        # base axis
        JoyStickButton(name="z", sc_config_name="z", coord_x_left={"left": 1545, "right": 278}, coord_y_top=719),
        #JoyStickButton(name="Throttle Axis", sc_config_name="axis_z", coord_x_left={"left": 1545, "right": 278}, coord_y_top=505),

        JoyStickButton(name="x", sc_config_name="x", coord_x_left={"left": 950, "right": 875}, coord_y_top=86),
        
        JoyStickButton(name="y", sc_config_name="y", coord_x_left={"left": 950, "right": 875}, coord_y_top=122),
        
        JoyStickButton(name="rotz", sc_config_name="rotz", coord_x_left={"left": 950, "right": 875}, coord_y_top=155),
        # to troubleshoot  seem to be  when mode is switched for POV hat
        JoyStickButton(name="rotx", sc_config_name="rotx", coord_x_left={"left": 71, "right": 1755}, coord_y_top=262),
        JoyStickButton(name="roty", sc_config_name="roty", coord_x_left={"left": 71, "right": 1755}, coord_y_top=295),
        

    ]
    buttons_dict = {button.name: button.model_copy() for button in buttons}
    modified_buttons_dict = {}
    for button in buttons_dict.values():
        modified_buttons_dict[f"{button.name}_mod"] = button.model_copy(update={"modifier": True, "visible": False})
    buttons_dict.update(modified_buttons_dict)
    return buttons_dict


