from app.models.joystick import JoyAction, JoyStickButton, JoystickConfig



    
joy_action_1 = JoyAction(name="joy1", input="button1", modifier=False, multitap=False, hold=False, category="Test", sub_category="SubTest", button=JoyStickButton(name="button1", sc_config_name="v_toggle_power", coord_x_left={ 'left' : 0, 'right': 0 }, coord_y_top=0))


joy_1 = JoystickConfig(side="left", configured_actions={"joy1": JoyAction(name="joy1", key="a", modifier="ctrl", hold_time=0.5)})


def test_export_xml_simple():
    # Test the export of a simple XML file
    
