
from typing import Dict, List, Literal

from pydantic import BaseModel, RootModel
from app.utils.devices import get_controller_devices
from app.models.exported_configmap_xml import ExportedActionMapsFile, Rebind, Option, get_action_maps_object
from app.models.full_game_control_options import get_all_subcategories_actions, GameAction, get_all_defined_game_actions

MODIFIER_KEY = "rctrl"

categories: List[str]= list(get_all_subcategories_actions().root.keys())
modifiers: List[str] = ["tap", 'hold', 'double_tap', 'modifier_key']

def match_device_instance(device_name: str, device_guid: str, configmap_options: List[Option]) -> Option | None:
    for option in configmap_options:
        if option.type != "joystick":
            continue
        if option.product is None:
            continue
        if device_name in option.product:
            return option
    
def map_plugged_in_joy_with_xml_configmap(file_path: str) -> None:
    """Map the plugged in joystick with the xml configmap"""
    devices = get_controller_devices()
    action_maps = get_action_maps_object(file_path)
    device_match_instances : Dict[int, Option] = {}

    for device in devices:
        match = match_device_instance(device.name, device.product_guid, action_maps.options)
        if match is not None:
            device_match_instances[device.instance] = match

    print(device_match_instances)


class UiJoystickButtonInfo(BaseModel):
    side: str # left or right joystick
    height: int = 50 # default size of the button
    width: int = 50 # default size of the button


class JoyMappingData(BaseModel):
    """mapping of the data to an internal data structure used to display and edit bindings"""
    usage_category: str
    input: str
    game_action: GameAction
    rebind: Rebind | None = None

    def button_name_from_input(self) -> str:
        if '+' in self.input:
            x = self.input.split("+")[-1]
        else:
            x = self.input
        return x.split("_")[-1]

    def is_tap_modfier(self) -> bool:
        return not self.is_hold_modifier()

    def is_hold_modifier(self) -> bool:
        return self.game_action.activation_mode == "delayed_press"
    
    def is_multitap_modifier(self) -> bool:
        if self.rebind is None:
            return False
        return self.rebind.multitap == 2
    
    def is_key_modifier(self) -> bool:
        if self.rebind is None:
            return False
        return MODIFIER_KEY in self.rebind.input
    
    @property
    def key(self) -> str:
        return f"{self.button_name_from_input()}-{self.usage_category}-{self.is_tap_modfier()}-{self.is_multitap_modifier()}-{self.is_hold_modifier()}-{self.is_key_modifier()}"
    
    

class JoyButton(BaseModel):
    mappings: Dict[str, JoyMappingData] = {} # key is calculated based on modfiers and action name, value is the mapping data
    name: str  # example: button 3
    x: int # x coordinate of the button on the left image
    y: int # y coordinate of the button on the left image
    def get_all_unique_actions(self) -> List[GameAction]:
        return list(set([mapping.game_action for mapping in self.mappings.values()]))

class JoystickBindingData(BaseModel):
    name: str
    side: Literal["left", "right"] 
    configmap_instance: int
    device_instance: int
    displaymode: Literal["half", "full"] # splits view by side, or shows all buttons
    background_image: str
    image_height: int
    image_width: int
    buttons: Dict[str, JoyButton] = {} # button name to button object
    
class DevicesJoyStickMapping(BaseModel):
    devices: Dict[int, JoystickBindingData] = {} # side to joystick binding data


    def set_mapping(self, device_instance: int, button_key: str, game_action: GameAction) -> None:
        device= self.devices[device_instance]
        button = device.buttons[button_key]
        mapping = JoyMappingData(usage_category="test", input="test", game_action=game_action)
        button.mappings[mapping.key] = mapping


SupportedDevicesRootModel = RootModel[Dict[str, DevicesJoyStickMapping]]

def get_supported_devices(file_path: str) -> SupportedDevicesRootModel:
    with open(file_path) as f:
        return SupportedDevicesRootModel.model_validate_json(f.read())

def update_joymapping_for_exported_action(mapping: Dict[str, JoyMappingData], device_instance: int,  configured_action: GameAction, button: JoyButton, exported_mapping_file: ExportedActionMapsFile) -> JoyMappingData |  None:
    for actionmap in exported_mapping_file.actionmap:
        for action in actionmap.action:
            if action.name == configured_action.name:
                for rebind in action.rebind:
                    #TODO: handle the default mapping config where the js_device_instance is not present
                    if f"js{device_instance}_" in rebind.input:
                        joy_mapping_data = JoyMappingData(usage_category=actionmap.name, input=rebind.input, game_action=configured_action, rebind=rebind)
                        if joy_mapping_data.button_name_from_input() == button.name:
                            mapping[joy_mapping_data.key] = joy_mapping_data
                

def fill_in_joy_mappings(all_actions_map: Dict[str, List[GameAction]], exported_mapping_file: ExportedActionMapsFile, devices: Dict[int, JoystickBindingData]) -> None:
    
    for device_instance, joy_data in devices.items():
        for button in joy_data.buttons.values():
            for name, game_action in all_actions_map.items():
                for action in game_action:
                    update_joymapping_for_exported_action(button.mappings, device_instance, action, button, exported_mapping_file)       
                    


def export_config_json(devices_config: SupportedDevicesRootModel) -> None:
    with open("app/data/vkb_new_test_export.json", "w") as f:
        f.write(devices_config.model_dump_json(indent=4))

def generate_config_from_xml_file(file_path: str = "app/data/layout_3_24_2_final_exported.xml"):
    mapped_devices_buttons= map_plugged_in_joy_with_xml_configmap(file_path)
    devices = get_supported_devices("app/data/vkb_new.json")
    print(devices)
    exported_mapping_file = get_action_maps_object(file_path)
    all_actions_map = get_all_defined_game_actions()
    fill_in_joy_mappings(all_actions_map, exported_mapping_file, devices.root["VKB"].devices)
    print(devices)
    export_config_json(devices)

if __name__ == "__main__":
    generate_config_from_xml_file()
    generate_config_from_xml_file("app/data/SCBindsDefault.xml")

